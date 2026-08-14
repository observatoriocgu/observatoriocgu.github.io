#!/usr/bin/env python3
"""
Camada de acesso ao Diário Oficial da União, compartilhada pelos crawlers.

Este módulo NÃO é executável: é a biblioteca que `dou_saidas_affc.py` (card
"dias sem perder um Auditor", Fase 2.5), `enriquecer_saidas.py` (motivo e destino
de cada saída, Fase 2) e `concurso.py` (resultado final do concurso, D17) usam.

Quase tudo aqui foi extraído do `dou_saidas_affc.py`, onde já tinha sido validado
ato a ato em 13/08/2026. Duas coisas são novas, e as duas resolvem defeitos reais
daquele script:

  - PAUSA entre requisições. O crawler original não tinha nenhuma: batia no
    in.gov.br o mais rápido que a rede deixasse. Com 268 nomes para varrer isso
    deixa de ser aceitável.
  - CACHE em disco. Página de ato publicado é imutável, então baixar duas vezes
    é desperdício puro. Sem cache, refazer o backfill custaria os mesmos ~50
    minutos toda vez.

Como a busca do DOU se comporta (verificado em 13 e 14/08/2026):
  - endpoint público, sem autenticação: /consulta/-/buscar/dou
  - o JSON dos resultados vem embutido num <script id="..._BuscaDouPortlet_params">
  - aceita UMA frase entre aspas; frase + termo solto devolve ZERO resultados,
    e termos soltos viram OU (centenas de milhares de resultados). Não dá para
    pedir "NOME DA PESSOA E Auditor Federal": o recorte tem de ser feito depois,
    sobre o resultado.
  - `delta` funciona até 50; acima disso o servidor volta a 20
  - não há parâmetro de paginação que funcione (currentPage/pagina/_cur foram
    testados e devolvem sempre a primeira página)
  => varredura ampla exige JANELAS DE DATA. Busca por nome não precisa: um nome
     sozinho não chega perto do teto de 50 (o caso testado devolveu 20 atos na
     vida inteira). Ver `busca_estourou_teto`.
  - a busca ignora acento e gênero, o que ajuda ("Auditor" acha "Auditora") e
    atrapalha (homônimos casam) — daí a guarda de matrícula em `siape_compativel`.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_CACHE = RAIZ / "data" / "cache_dou"

BASE_BUSCA = "https://www.in.gov.br/consulta/-/buscar/dou"
BASE_ATO = "https://www.in.gov.br/web/dou/-/"

ORGAO_CGU = "CONTROLADORIA-GERAL DA UNIAO"

# Teto de resultados por resposta. Pedir mais faz o servidor voltar a 20.
DELTA_MAXIMO = 50

# Segundos entre duas requisições de rede. Acerto de cache não conta.
PAUSA_SEGUNDOS = 1.0

_ultima_requisicao = 0.0


# ---------------------------------------------------------------- normalização

def normalizar(texto: str) -> str:
    """Caixa alta, sem acentos, espaços colapsados — para comparar com segurança."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


# ------------------------------------------------------------------ rede/cache

def _caminho_cache(url: str) -> Path:
    return DIR_CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html")


def _respeitar_pausa() -> None:
    global _ultima_requisicao
    espera = PAUSA_SEGUNDOS - (time.monotonic() - _ultima_requisicao)
    if espera > 0:
        time.sleep(espera)
    _ultima_requisicao = time.monotonic()


def baixar(url: str, timeout: int = 90, usar_cache: bool = True) -> str:
    """
    Baixa uma URL como texto, com cache em disco e pausa entre requisições.

    Tenta urllib e cai para o curl se levar 403 — alguns proxies bloqueiam o
    User-Agent do urllib mas deixam o curl passar. Este fallback não é
    decorativo: sem ele a busca do DOU responde 403 nesta máquina.
    """
    cache = _caminho_cache(url)
    if usar_cache and cache.is_file():
        return cache.read_text(encoding="utf-8")

    cabecalhos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    _respeitar_pausa()
    conteudo = ""
    try:
        req = urllib.request.Request(url, headers=cabecalhos)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            conteudo = resp.read().decode("utf-8", errors="replace")
    except Exception:
        try:
            proc = subprocess.run(
                ["curl", "-sS", "-m", str(timeout), "-A", cabecalhos["User-Agent"], url],
                capture_output=True,
                check=True,
            )
            conteudo = proc.stdout.decode("utf-8", errors="replace")
        except Exception as erro:
            print(f"    ! falha ao baixar {url[:80]}: {erro}", file=sys.stderr)
            return ""

    # Só grava resposta não-vazia: cachear "" transformaria uma falha de rede
    # momentânea em ausência permanente de resultado.
    if usar_cache and conteudo:
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(conteudo, encoding="utf-8")
    return conteudo


def buscar(
    q: str,
    inicio: date | None = None,
    fim: date | None = None,
    secao: str = "todos",
    usar_cache: bool = True,
) -> list[dict]:
    """
    Resultados da busca do DOU, do mais recente para o mais antigo.

    `q` vai como está — quem chama é responsável pelas aspas da frase exata.
    Sem `inicio`/`fim`, busca em todo o período disponível.

    `secao='todos'` é o padrão de propósito: atos de pessoal (nomeação,
    exoneração, vacância, aposentadoria) saem na Seção 2, e buscar só na Seção 1
    não devolve nenhum deles.
    """
    parametros = {
        "q": q,
        "s": secao,
        "sortType": "0",
        "delta": str(DELTA_MAXIMO),
    }
    if inicio and fim:
        parametros["exactDate"] = "personalizado"
        parametros["publishFrom"] = inicio.strftime("%d-%m-%Y")
        parametros["publishTo"] = fim.strftime("%d-%m-%Y")
    else:
        parametros["exactDate"] = "all"

    pagina = baixar(BASE_BUSCA + "?" + urllib.parse.urlencode(parametros), usar_cache=usar_cache)
    if not pagina:
        return []

    achado = re.search(r'BuscaDouPortlet_params"[^>]*>(.*?)</script>', pagina, re.S)
    if not achado:
        return []

    try:
        dados = json.loads(html_mod.unescape(achado.group(1).strip()))
    except json.JSONDecodeError:
        return []

    return dados.get("jsonArray", []) or []


def busca_estourou_teto(resultados: list[dict]) -> bool:
    """
    True quando a resposta veio cheia — e portanto pode estar truncada.

    Como não há paginação, o único jeito honesto de ver o resto é refazer a
    busca em janelas de data menores.
    """
    return len(resultados) >= DELTA_MAXIMO


def e_do_orgao(resultado: dict, orgao_normalizado: str) -> bool:
    hierarquia = resultado.get("hierarchyList") or []
    return any(orgao_normalizado in normalizar(nivel) for nivel in hierarquia)


def e_da_cgu(resultado: dict) -> bool:
    return e_do_orgao(resultado, ORGAO_CGU)


def extrair_texto(pagina_html: str) -> str:
    """
    Texto corrido do ato, a partir da div .texto-dou da página do DOU.

    Devolve `""` quando a div não existe. A versão anterior caía para a PÁGINA
    INTEIRA nesse caso, e isso é pior que não ter texto: algumas URLs do DOU são
    página-índice (um sumário com várias matérias do dia), sem `.texto-dou`, e o
    fallback entregava ~27 mil caracteres de JavaScript de analytics que
    seguiam adiante como se fossem o ato. Dois "destinos" foram atribuídos a
    pessoas reais com base nesse lixo. Medido: das 1.618 páginas de ato no
    cache, ZERO dependem do fallback — ele só cobria as páginas erradas.
    """
    achado = re.search(
        r'<div[^>]*class="[^"]*texto-dou[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</section|</article)',
        pagina_html,
        re.S,
    )
    if not achado:
        return ""
    sem_tag = re.sub(r"<[^>]+>", " ", achado.group(1))
    return " ".join(html_mod.unescape(sem_tag).split())


def baixar_ato(url_title: str, timeout: int = 60, usar_cache: bool = True) -> tuple[str, str]:
    """Devolve (html, texto) da página de um ato. `('', '')` se falhar."""
    pagina = baixar(BASE_ATO + url_title, timeout=timeout, usar_cache=usar_cache)
    if not pagina:
        return "", ""
    return pagina, extrair_texto(pagina)


# Primeiros níveis da hierarquia que são guarda-chuva, não órgão. Para eles, quem
# identifica o destino é o nível seguinte: "Poder Legislativo/Senado Federal" só
# informa alguma coisa a partir de "Senado Federal". Publicar "foi para o Poder
# Judiciário" é verdadeiro e inútil.
#
# "Presidência da República" está aqui porque a AGU pendura debaixo dela: quem
# foi nomeado Procurador Federal aparecia como "foi para a Presidência da
# República", o que induz a erro. Com o nível seguinte sai "Advocacia-Geral da
# União" — e quem realmente foi para a Presidência continua identificado, pelo
# órgão de dentro dela (Casa Civil, e assim por diante).
NIVEIS_GENERICOS = (
    "PODER LEGISLATIVO",
    "PODER JUDICIARIO",
    "PODER EXECUTIVO FEDERAL",
    "PRESIDENCIA DA REPUBLICA",
)


def orgao_do_ato(resultado: dict) -> str:
    """Nome utilizável do órgão que publicou o ato, a partir do `hierarchyStr`."""
    niveis = [n.strip() for n in (resultado.get("hierarchyStr") or "").split("/") if n.strip()]
    if not niveis:
        return ""
    if normalizar(niveis[0]) in NIVEIS_GENERICOS and len(niveis) > 1:
        return niveis[1]
    return niveis[0]


def data_iso(resultado: dict) -> str:
    """`pubDate` (DD/MM/AAAA) em AAAA-MM-DD. String vazia se não der."""
    try:
        return datetime.strptime(resultado["pubDate"], "%d/%m/%Y").strftime("%Y-%m-%d")
    except (KeyError, ValueError):
        return ""


# ------------------------------------------------------- classificação de atos
#
# TODOS os padrões abaixo já estão na forma normalizada (caixa alta, sem acento).
# ATENÇÃO: NÃO passar nenhum deles por `normalizar()` — o `.upper()` converteria
# `\s` em `\S` e o padrão nunca casaria. Esse foi um bug real, e silencioso: o
# crawler achava zero saídas em 161 atos da CGU.

# Ordem de teste. Importa: os atos se sobrepõem no vocabulário, e o mais
# específico tem de ser testado primeiro. Um ato de aposentadoria termina com
# "declarar vago o referido cargo"; um de falecimento também.
TIPOS_SAIDA = ("falecimento", "demissao", "vacancia", "aposentadoria", "exoneracao")

ROTULOS = {
    "falecimento": "Falecimento",
    "demissao": "Demissão",
    "vacancia": "Vacância (posse em outro cargo)",
    "aposentadoria": "Aposentadoria",
    "exoneracao": "Exoneração",
}

# Situação correspondente na coluna SITUACAO do dados.csv.
SITUACAO_POR_TIPO = {
    "falecimento": "FALECIDO",
    "demissao": "DEMITIDO",
    "vacancia": "VACÂNCIA",
    "aposentadoria": "APOSENTADO",
    "exoneracao": "EXONERADO",
}

# DECISÃO EDITORIAL (usuário, 14/08/2026): a demissão NÃO vai ao ar.
#
# Demissão é penalidade de processo disciplinar. O ato é público no DOU, mas o
# observatório existe para medir evasão — quem é demitido não escolheu sair —, e
# repetir a penalidade numa página que agrega e ranqueia pessoas nomeadas é outra
# coisa, com outro efeito sobre a vida de alguém.
#
# O tipo continua sendo RECONHECIDO pelo classificador, de propósito: sem isso a
# pessoa cairia em "saída sem ato identificado", o crawler tentaria de novo todo
# mês, e o site afirmaria não saber uma coisa que sabe. O que muda é o que se
# GRAVA: situação neutra, sem motivo detalhado e sem link para o ato.
MOTIVOS_NAO_PUBLICADOS = frozenset({"demissao"})

SITUACAO_NAO_PUBLICADA = "DESLIGADO"
ROTULO_NAO_PUBLICADO = "Desligamento"

# Exoneração de cargo em comissão / função não é saída da CGU: o servidor deixa
# a chefia e continua Auditor. Sem este recorte, contaria troca de chefia como
# evasão — foi um falso positivo real na validação de 13/08/2026:
# "EXONERAR [...], Auditor Federal de Finanças e Controle, do Cargo Comissionado
#  Executivo de Chefe de Setor, código CCE 1.02".
PADROES_NAO_E_SAIDA = (
    r"CARGO\s+EM\s+COMISS",
    r"CARGO\s+COMISSIONADO",
    r"FUN[CG][AO]O\s+COMISSIONADA",
    r"FUNCAO\s+DE\s+CONFIAN",
    r"\bFCPE\b",
    r"\bCCE\b",
    r"\bFCE\b",
    r"\bCCE\s*\d",
    r"\bDAS[\s-]?\d",
    r"CODIGO\s+DAS",
)

# Não basta ausência de marcador de chefia: a exoneração precisa ser DO CARGO de
# AFFC. Um ato que só cita o cargo de passagem ("Fulano, Auditor Federal...,
# exonerado de X") não conta.
PADRAO_EXONERACAO_EFETIVA = (
    r"EXONERA(?:R|CAO)[^.]{0,200}?"
    r"DO\s+CARGO(?:\s+EFETIVO)?\s+DE\s+AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCAS\s+E\s+CONTROLE"
)

# Vacância: o DOU NÃO usa a palavra "vacância" nesses atos. A redação real é
# "Declarar vago o cargo de Auditor Federal [...] por motivo de posse em outro
# cargo inacumulável" (art. 33, VIII, da Lei 8.112/90). Procurar por "VACANCIA"
# fazia o crawler perder todos eles em silêncio.
PADROES = {
    "falecimento": (r"\bFALECIMENTO\b", r"\bFALECID[OA]\b"),
    # Demissão é penalidade de processo disciplinar (art. 132 da Lei 8.112/90),
    # não exoneração. O ato costuma NÃO citar o cargo — diz só "aplicar a
    # penalidade de demissão ao servidor Fulano, matrícula SIAPE nº ..." —, e é
    # por isso que `classificar` aceita dispensar a prova do cargo quando a
    # identidade já foi provada pela matrícula. Padrão exige a forma de
    # penalidade para não casar com menção solta à palavra.
    "demissao": (r"PENALIDADE\s+DE\s+DEMISSAO", r"\bDEMITIR\b", r"APLICAR[^.]{0,80}DEMISSAO"),
    "vacancia": (
        r"DECLARAR\s+VAG[OA]",
        r"DECLARAR\s+A\s+VACANCIA",
        r"VACANCIA\s+DO\s+CARGO",
    ),
    "aposentadoria": (r"APOSENTADORIA", r"\bAPOSENTAR\b"),
    "exoneracao": (r"EXONERACAO", r"\bEXONERAR\b"),
}

# A vacância só conta como saída quando o motivo é posse em outro cargo — que é
# o recorte pedido. O art. 33 lista outros motivos (promoção, readaptação) que
# são movimentação interna, não saída da CGU.
#
# Este é também o desempate contra a exoneração a pedido, cuja redação traz
# "ficando vago o cargo que atualmente ocupa" — texto que casaria com um padrão
# frouxo tipo "VAGO O CARGO", mas não com "DECLARAR VAGO".
PADRAO_VACANCIA_MOTIVO = r"POSSE\s+EM\s+OUTRO\s+CARGO"

# Só conta se o ato realmente falar do cargo efetivo de AFFC.
PADRAO_CARGO = r"AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCAS\s+E\s+CONTROLE"

# Nomeação/posse — usado para achar o DESTINO de quem saiu.
PADROES_NOMEACAO = (
    r"\bNOMEAR\b",
    r"\bNOMEACAO\b",
    r"\bEMPOSSAR\b",
    r"\bTOMAR\s+POSSE\b",
    r"\bTOMOU\s+POSSE\b",
)

# O contrário: o emprego ANTERIOR liberando a pessoa. Um ato assim NUNCA é
# destino. Sem esta guarda, o Observatório publicaria "foi para o TRE-MG em
# 2025" para alguém cujo único ato do TRE em 2025 é a baixa do cargo que ele
# deixou lá em 2022, antes de entrar na CGU — afirmação falsa sobre pessoa real.
PADROES_NAO_E_DESTINO = (
    r"DECLARAR\s+VAG[OA]",
    r"VACANCIA",
    r"\bDISPENSAR\b",
    r"\bEXONERAR\b",
    r"\bEXONERACAO\b",
    r"\bREDISTRIBUIR\b",
)

PADRAO_SIAPE = r"SIAPE\s*(?:N?[O°º.]*\s*)?(\d{6,8})"


def classificar(texto: str, exigir_cargo: bool = True) -> str | None:
    """
    Diz se o ato é uma saída de AFFC e de que tipo. `None` quando não é.

    A ordem de `TIPOS_SAIDA` importa: vacância e aposentadoria costumam trazer
    também a palavra "exoneração" no mesmo ato, então a exoneração é a última
    hipótese testada.
    """
    normalizado = normalizar(texto)

    if exigir_cargo and not re.search(PADRAO_CARGO, normalizado):
        return None

    # IMPORTANTE: quando um tipo é descartado, o certo é `continue` — testar os
    # demais —, nunca `return None`. Os atos se sobrepõem no vocabulário: um ato
    # de aposentadoria termina com "declarar vago o referido cargo", e um
    # `return` no teste de vacância engolia a aposentadoria inteira.
    for tipo in TIPOS_SAIDA:
        if not any(re.search(p, normalizado) for p in PADROES[tipo]):
            continue

        if tipo == "vacancia" and not re.search(PADRAO_VACANCIA_MOTIVO, normalizado):
            continue  # "declarar vago" sem posse em outro cargo: ver se é outro tipo

        if tipo == "exoneracao":
            # Exoneração exige as duas provas: nenhum marcador de chefia no ato,
            # e a exoneração ser explicitamente DO CARGO de AFFC.
            if any(re.search(p, normalizado) for p in PADROES_NAO_E_SAIDA):
                continue
            if not re.search(PADRAO_EXONERACAO_EFETIVA, normalizado):
                continue

        return tipo

    return None


# Assinatura de TABELA DE RESULTADO: "<inscrição>, <NOME>, <nota>" repetido.
#
# Foi um falso positivo real: um resultado de concurso com dezenas de nomes e
# notas casava o verbo "NOMEAR" num canto e o nome da pessoa em outro, e virava
# "destino: Poder Judiciário" para alguém que só constava da lista.
#
# A primeira tentativa de barrar isso mediu a DISTÂNCIA entre o verbo e o nome.
# Era o instrumento errado: medindo os 85 destinos válidos, a mediana dá 802
# caracteres e não há corte limpo — atos de nomeação legítimos são longos e
# trazem o nome bem depois do verbo. Um corte em 400 derrubava 63 destinos
# corretos. O que distingue os dois casos não é distância, é a FORMA do ato.
PADRAO_LINHA_DE_RESULTADO = r"\d{4,10},\s*[A-Z][A-Z\s]{5,60},\s*\d+[.,]\d{1,2}\b"
MIN_LINHAS_PARA_SER_TABELA = 5


def e_tabela_de_resultado(texto_normalizado: str) -> bool:
    """True se o ato é uma tabela de classificação, não um ato sobre uma pessoa."""
    return len(re.findall(PADRAO_LINHA_DE_RESULTADO, texto_normalizado)) >= MIN_LINHAS_PARA_SER_TABELA


# Listas de classificação e listas de nomeação são parecidas — as duas são
# sequências de nomes — e a diferença decide se o observatório afirma ou não
# que alguém "foi para" um órgão. O que separa as duas é o que acompanha o nome:
#
#   classificação : "BRENO HONORATO NASCIMENTO 346.35 9 PCD"   <- NOTA (decimal)
#   nomeação      : "JAIDIR ALVES COSTA DOS SANTOS 388260521 DRF - RIO BRANCO"
#                                                    ^matrícula  ^lotação
#
# Estar classificado num concurso não é ter sido nomeado nele. Três auditores
# receberam destino errado por esse encaixe.
PADRAO_NOTA_APOS_NOME = r"[\s,]+\d{1,3}[.,]\d{2}\b"
PADRAO_COTA_ENTRE_PARENTESES = r"\(\s*(?:AMPLA|NEGROS?|PCD|PPP|DEFICIENTE)\s*\)"
PADRAO_CABECALHO_CLASSIFICACAO = r"CLASSIFICACAO\s+CANDIDATO"


def e_lista_de_classificacao(texto_normalizado: str, nome: str) -> bool:
    """True se o nome aparece como classificado, não como nomeado."""
    alvo = re.escape(normalizar(nome))
    if re.search(PADRAO_CABECALHO_CLASSIFICACAO, texto_normalizado):
        return True
    if re.search(alvo + PADRAO_NOTA_APOS_NOME, texto_normalizado):
        return True
    # "10 (AMPLA) FULANO DE TAL 14 (AMPLA)" — cercado por marcação de cota.
    return bool(re.search(PADRAO_COTA_ENTRE_PARENTESES + r"\s*" + alvo, texto_normalizado))


# "Decorrente da posse de X" é ambíguo e precisa do nome para desempatar:
#   "...cargo VAGO EM DECORRENCIA DA POSSE DE HYAGO ... EM OUTRO CARGO"
#        -> é o emprego ANTERIOR de Hyago dando baixa. NÃO é destino.
#   "...NOMEAR ANDRE ..., EM CARGO VAGO DECORRENTE DA POSSE DE (outra pessoa)"
#        -> André está sendo nomeado na vaga que outro deixou. É destino.
# O que decide é se o nome da pessoa vem logo DEPOIS de "posse de".
PADROES_SAIDA_DA_PESSOA = (
    r"POSSE\s+DE\s+{nome}",
    r"OCUPAD[OA]\s+PEL[OA]\s+SERVIDOR[A]?\s+{nome}",
    r"DECLARAR\s+VAG[OA][^.]{{0,120}}{nome}",
    r"\bEXONERAR\b[^.]{{0,120}}{nome}",
    r"\bDISPENSAR\b[^.]{{0,120}}{nome}",
    # "...em vaga originária da vacância do cargo ANTERIORMENTE OCUPADO POR
    # Fulano" — quem está sendo nomeado é outra pessoa; Fulano é o que saiu.
    r"ANTERIORMENTE\s+OCUPAD[OA]\s+(?:POR|PEL[OA])\s+{nome}",
    # Desistência: o ato diz justamente que a pessoa NÃO foi para lá. Publicá-lo
    # como destino inverteria o fato. Duas redações reais:
    #   "INTERESSADA: Fulana  ASSUNTO: CONCURSO PUBLICO. DESISTENCIA"
    #   "...DESISTENCIA DE NOMEACAO OU POSSE FORMULADOS PELOS CANDIDATOS: ..., Fulano, ..."
    r"INTERESSAD[OA]:\s*{nome}[\s\S]{{0,200}}DESISTENCIA",
    r"DESISTENCIA[\s\S]{{0,300}}{nome}",
    # "...em vaga decorrente da VACANCIA DO CARGO DE Fulano" — de novo, Fulano é
    # quem vagou; quem está sendo nomeado é outro.
    r"VACANCIA\s+DO\s+CARGO\s+(?:DE\s+)?{nome}",
    # "TORNAR SEM EFEITO A NOMEACAO DE Fulano" — a nomeação foi anulada. O ato
    # diz o oposto de "foi para lá".
    r"TORNAR\s+SEM\s+EFEITO[\s\S]{{0,160}}{nome}",
)


def descreve_saida_da_pessoa(texto_normalizado: str, nome: str) -> bool:
    """True se o ato trata do desligamento DESTA pessoa — nunca um destino."""
    alvo = re.escape(normalizar(nome))
    return any(re.search(p.format(nome=alvo), texto_normalizado) for p in PADROES_SAIDA_DA_PESSOA)


def e_ato_de_nomeacao(texto: str, nome: str = "") -> bool:
    """
    True se o ato nomeia/empossa a pessoa para um cargo efetivo.

    Cinco exclusões, cada uma vinda de um falso positivo observado:
      - o ato descreve o desligamento DESTA pessoa (o emprego anterior dando
        baixa) — desempatado pelo nome, ver `descreve_saida_da_pessoa`;
      - nomeação para cargo em comissão / função (CCE, DAS, FCPE) — quem assume
        chefia em outro órgão não "foi para" aquele órgão como servidor;
      - tabela de resultado de concurso;
      - o nome aparece como classificado, não como nomeado;
      - o ato não cita a pessoa.
    """
    normalizado = normalizar(texto)
    if not normalizado:
        return False
    if nome and normalizar(nome) not in normalizado:
        return False
    if nome and descreve_saida_da_pessoa(normalizado, nome):
        return False
    if any(re.search(p, normalizado) for p in PADROES_NAO_E_SAIDA):
        return False
    if e_tabela_de_resultado(normalizado):
        return False
    if nome and e_lista_de_classificacao(normalizado, nome):
        return False

    return any(re.search(p, normalizado) for p in PADROES_NOMEACAO)


def cita_nome(texto: str, nome: str) -> bool:
    """
    True se o ato cita exatamente esta pessoa.

    LIMITAÇÃO CONHECIDA — nome é prefixo de nome. "LUIZ CARLOS DE ALMEIDA" está
    contido em "LUIZ CARLOS DE ALMEIDA SOUZA", que é outra pessoa, e foi assim
    que uma lista de concurso do Judiciário virou "destino" de um auditor.

    Exigir palavra inteira NÃO resolve: o texto do DOU vem todo em caixa alta, e
    aí "ALMEIDA SOUZA" (outra pessoa) e "OLIVEIRA DO CARGO" (a pessoa certa)
    ficam indistinguíveis pelo delimitador. Quem trata esse caso de verdade é o
    conjunto: `e_tabela_de_resultado` (o falso positivo observado estava numa
    tabela de classificação), a guarda de matrícula e a janela de datas.
    """
    alvo = normalizar(nome)
    if not alvo:
        return False
    return alvo in normalizar(texto)


def siape_compativel(texto: str, matricula_mascarada: str) -> bool | None:
    """
    Confere a matrícula do ato contra a do Portal, que vem mascarada (`166****`).

    Os 3 primeiros dígitos ficam visíveis, e os atos do DOU escrevem o SIAPE por
    extenso ("matrícula SIAPE nº 2576295"). Dá para eliminar homônimo de graça.

    ATENÇÃO AO ZERO À ESQUERDA. A máscara do Portal tem 7 posições e preserva os
    zeros (`014****`), mas o DOU escreve o número sem eles (`149262`). Comparar
    cru daria conflito para todo mundo cujo SIAPE começa com zero — e o ato certo
    seria descartado em silêncio. Foi um bug real: a aposentadoria de uma auditora
    com SIAPE 0149262 sumiu por isso. Por isso os dois lados vão a 7 dígitos.

    Devolve `None` quando não há como decidir (ato sem matrícula, ou máscara sem
    dígito visível) — quem chama decide o que fazer com a dúvida.
    """
    prefixo = re.sub(r"\D", "", matricula_mascarada or "")
    if not prefixo:
        return None

    achados = re.findall(PADRAO_SIAPE, normalizar(texto))
    if not achados:
        return None

    return any(s.zfill(7).startswith(prefixo) for s in achados)


# ------------------------------------------------------------ arquivamento HTML

def nome_arquivo(resultado: dict, prefixo: str) -> str:
    data = data_iso(resultado) or "sem-data"
    fatia = re.sub(r"[^a-z0-9]+", "-", resultado.get("urlTitle", "").lower())[:70].strip("-")
    return f"{data}_{prefixo}_{fatia}.html"


def salvar_ato(resultado: dict, tipo: str, texto: str, destino: Path) -> str:
    """Grava uma cópia legível do ato e devolve o nome do arquivo."""
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / nome_arquivo(resultado, tipo)
    url_original = BASE_ATO + resultado.get("urlTitle", "")
    rotulo = ROTULOS.get(tipo, tipo)

    documento = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_mod.escape(resultado.get('title', ''))} — DOU</title>
<style>
 body {{ font-family: Georgia, serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
        line-height: 1.6; color: #111; background: #fff; }}
 header {{ border-bottom: 2px solid #111; padding-bottom: .75rem; margin-bottom: 1.5rem; }}
 h1 {{ font-size: 1.15rem; margin: 0 0 .5rem; }}
 dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .15rem .75rem;
       font-family: system-ui, sans-serif; font-size: .82rem; color: #444; margin: 0; }}
 dt {{ font-weight: 600; }}
 .texto {{ white-space: pre-wrap; }}
 footer {{ margin-top: 2rem; border-top: 1px solid #ccc; padding-top: .75rem;
           font-family: system-ui, sans-serif; font-size: .78rem; color: #555; }}
</style>
</head>
<body>
<header>
<h1>{html_mod.escape(resultado.get('title', ''))}</h1>
<dl>
<dt>Tipo</dt><dd>{html_mod.escape(rotulo)}</dd>
<dt>Publicado em</dt><dd>{html_mod.escape(str(resultado.get('pubDate', '')))}</dd>
<dt>Seção</dt><dd>{html_mod.escape(str(resultado.get('pubName', '')))}</dd>
<dt>Edição</dt><dd>{html_mod.escape(str(resultado.get('editionNumber', '')))}</dd>
<dt>Página</dt><dd>{html_mod.escape(str(resultado.get('numberPage', '')))}</dd>
<dt>Órgão</dt><dd>{html_mod.escape(str(resultado.get('hierarchyStr', '')))}</dd>
</dl>
</header>
<div class="texto">{html_mod.escape(texto)}</div>
<footer>
Cópia do ato publicado no Diário Oficial da União, arquivada pelo Observatório
das Evasões — CGU. Original:
<a href="{html_mod.escape(url_original)}">{html_mod.escape(url_original)}</a>
</footer>
</body>
</html>
"""
    arquivo.write_text(documento, encoding="utf-8")
    return arquivo.name
