#!/usr/bin/env python3
"""
Camada de acesso ao Diário Oficial da União, compartilhada pelos crawlers.

Este módulo NÃO é executável: é a biblioteca que `varrer_dou.py` (varredura por
FRASE), `enriquecer_saidas.py` (motivo e destino de cada saída, por NOME),
`atos.py` (o índice único) e `concurso.py` (resultado final do concurso, D17)
usam.

Quase tudo aqui foi extraído do `dou_saidas_affc.py` — o crawler do card, que a
D19 aposentou em 15/08/2026 e cujo sucessor é o `varrer_dou.py` —, onde já tinha
sido validado ato a ato em 13/08/2026. Duas coisas são novas, e as duas resolvem
defeitos reais daquele script:

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

import gzip
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

# VALIDADE DO CACHE — a distinção que faltava, e que fazia o observatório não
# enxergar movimentação nova.
#
# Página de ATO publicado é imutável: uma vez baixada, vale para sempre, e é daí
# que vem a economia dos ~50 minutos de backfill.
#
# Resposta de BUSCA não é imutável. Uma janela que alcança o presente ganha atos
# a cada dia que passa, e uma busca sem janela (`exactDate=all`, que é como se
# busca por nome) nunca fecha. Cacheá-las para sempre congela a varredura no dia
# em que ela rodou pela primeira vez: o crawler segue respondendo, sem erro
# nenhum, com o resultado da semana passada.
#
# A janela só é considerada FECHADA — e o cache dela, eterno — quando termina há
# mais de 30 dias. O DOU republica e reindexa ato com atraso de alguns dias; a
# folga de 30 é a margem para isso.
DIAS_PARA_JANELA_FECHADA = 30
VALIDADE_BUSCA_ABERTA_HORAS = 6.0

_ultima_requisicao = 0.0


# ---------------------------------------------------------------- normalização

def normalizar(texto: str) -> str:
    """Caixa alta, sem acentos, espaços colapsados — para comparar com segurança."""
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


def normalizar_com_mapa(texto: str) -> tuple[str, list[int]]:
    """
    Como `normalizar`, mas devolve também de onde veio cada caractere.

    `mapa[i]` é o índice, no texto ORIGINAL, do caractere que virou o `i`-ésimo
    do normalizado. Serve para casar um padrão na forma normalizada — que é a
    única em que dá para escrever regex sem sofrer com acento e caixa — e
    recortar o trecho no original, com acento e caixa preservados.

    É o que permite ler "ocupado pelo servidor CIRO JÔNATAS DE SOUZA OLIVEIRA" e
    devolver o nome com o circunflexo no lugar, em vez de "CIRO JONATAS".
    """
    saida: list[str] = []
    mapa: list[int] = []
    espaco_pendente = False

    for indice, caractere in enumerate(texto or ""):
        if caractere.isspace():
            # Espaço só entra se já houver conteúdo antes — é o que reproduz o
            # `" ".join(split())` de `normalizar`, sem perder o alinhamento.
            espaco_pendente = bool(saida)
            continue
        for decomposto in unicodedata.normalize("NFKD", caractere):
            if unicodedata.combining(decomposto):
                continue
            if espaco_pendente:
                saida.append(" ")
                mapa.append(indice)
                espaco_pendente = False
            for maiuscula in decomposto.upper():
                saida.append(maiuscula)
                mapa.append(indice)

    return "".join(saida), mapa


# ------------------------------------------------------------------ rede/cache

def _caminho_cache(url: str, dir_cache: Path | None = None) -> Path:
    return (dir_cache or DIR_CACHE) / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".html")


def _respeitar_pausa(pausa: float | None = None) -> None:
    global _ultima_requisicao
    espera = (PAUSA_SEGUNDOS if pausa is None else pausa) - (time.monotonic() - _ultima_requisicao)
    if espera > 0:
        time.sleep(espera)
    _ultima_requisicao = time.monotonic()


def baixar(
    url: str,
    timeout: int = 90,
    usar_cache: bool = True,
    validade_horas: float | None = None,
    dir_cache: Path | None = None,
    aceitar_gzip: bool = False,
    pausa_segundos: float | None = None,
) -> str:
    """
    Baixa uma URL como texto, com cache em disco e pausa entre requisições.

    `validade_horas=None` é cache eterno — o certo para página de ato, que não
    muda depois de publicada. Com um valor, a cópia em disco mais velha que isso
    é ignorada e a URL vai à rede de novo (ver VALIDADE_BUSCA_ABERTA_HORAS).

    `dir_cache` separa a prateleira: o DOU e o rankingdosconcursos guardam coisas
    de validade diferente, e misturá-las na mesma pasta faria a limpeza de uma
    apagar a outra. Sem o parâmetro, tudo continua indo para `data/cache_dou`.

    `pausa_segundos` sobrepõe o intervalo entre requisições. Existe porque nem
    todo servidor tolera o mesmo ritmo: o in.gov.br aceita uma por segundo, e o
    rankingdosconcursos responde uma página de erro "Muitas Consultas" nesse
    ritmo — com status 200, o que a fazia passar por resposta boa.

    `aceitar_gzip` pede a resposta comprimida. Fica DESLIGADO por padrão de
    propósito: o in.gov.br já entrega páginas pequenas e mexer no que funciona
    não paga. Para o rankingdosconcursos paga muito — a mesma página vai de
    2,9 MB para 218 KB, e a varredura inteira de 480 MB para 9 MB.

    Tenta urllib e cai para o curl se levar 403 — alguns proxies bloqueiam o
    User-Agent do urllib mas deixam o curl passar. Este fallback não é
    decorativo: sem ele a busca do DOU responde 403 nesta máquina.
    """
    cache = _caminho_cache(url, dir_cache)
    vencido = False
    if usar_cache and cache.is_file():
        if validade_horas is None:
            return cache.read_text(encoding="utf-8")
        idade_horas = (time.time() - cache.stat().st_mtime) / 3600
        if idade_horas <= validade_horas:
            return cache.read_text(encoding="utf-8")
        vencido = True

    cabecalhos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    if aceitar_gzip:
        cabecalhos["Accept-Encoding"] = "gzip"

    _respeitar_pausa(pausa_segundos)
    conteudo = ""
    try:
        req = urllib.request.Request(url, headers=cabecalhos)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read()
            # O servidor pode ignorar o pedido e responder sem comprimir; quem
            # manda é o cabeçalho da RESPOSTA, nunca o do pedido.
            if (resp.headers.get("Content-Encoding") or "").lower() == "gzip":
                bruto = gzip.decompress(bruto)
            conteudo = bruto.decode("utf-8", errors="replace")
    except Exception:
        try:
            comando = ["curl", "-sS", "-m", str(timeout), "-A", cabecalhos["User-Agent"]]
            if aceitar_gzip:
                # `--compressed` faz o próprio curl descomprimir.
                comando.append("--compressed")
            proc = subprocess.run(
                [*comando, url],
                capture_output=True,
                check=True,
            )
            conteudo = proc.stdout.decode("utf-8", errors="replace")
        except Exception as erro:
            print(f"    ! falha ao baixar {url[:80]}: {erro}", file=sys.stderr)
            # Rede fora com cópia vencida em disco: a cópia velha é melhor que
            # nada. Sem esta volta, uma queda de rede transformaria o cache
            # vencido em ausência de resultado — e a varredura do dia
            # "descobriria" que a CGU não tem mais saída nenhuma.
            if vencido:
                print("      (usando a cópia vencida do cache)", file=sys.stderr)
                return cache.read_text(encoding="utf-8")
            return ""

    # Só grava resposta não-vazia: cachear "" transformaria uma falha de rede
    # momentânea em ausência permanente de resultado.
    if usar_cache and conteudo:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(conteudo, encoding="utf-8")
    return conteudo


def janela_fechada(fim: date | None) -> bool:
    """True quando o fim da janela já passou tempo bastante para não mudar mais."""
    if fim is None:
        return False
    return (date.today() - fim).days > DIAS_PARA_JANELA_FECHADA


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

    O cache só é eterno para janela FECHADA (ver DIAS_PARA_JANELA_FECHADA). Busca
    que alcança o presente — e busca sem janela, que é como se busca por nome —
    tem validade curta: senão a varredura de hoje devolveria o resultado do dia
    em que rodou pela primeira vez.
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

    validade = None if janela_fechada(fim) else VALIDADE_BUSCA_ABERTA_HORAS
    pagina = baixar(
        BASE_BUSCA + "?" + urllib.parse.urlencode(parametros),
        usar_cache=usar_cache,
        validade_horas=validade,
    )
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


def titulo_do_ato(resultado: dict) -> str:
    """
    O título do ato, limpo da marcação que a busca do DOU acrescenta.

    A busca DESTACA os termos procurados dentro do `title` que devolve:

        <span class='highlight' style='background:#FFA;'>PORTARIA</span> Nº ...

    Enquanto se buscou por nome de pessoa isso nunca apareceu — nome de gente não
    está no título da portaria. Passou a aparecer quando a busca passou a ser
    pelo TÍTULO do ato (é assim que se acha o original de uma retificação), e aí
    o índice guardava o HTML e a tela mostrava a marcação crua.

    Tirar a tag e desescapar a entidade é tudo o que é preciso: o texto do título
    é o mesmo, com ou sem destaque.
    """
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", resultado.get("title") or "")).split())


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
TIPOS_SAIDA = ("falecimento", "demissao", "vacancia", "aposentadoria", "exoneracao", "cessao")

ROTULOS = {
    "falecimento": "Falecimento",
    "demissao": "Demissão",
    "vacancia": "Vacância (posse em outro cargo)",
    "aposentadoria": "Aposentadoria",
    "exoneracao": "Exoneração",
    "cessao": "Cessão a outro órgão",
    # Ato de CHEGADA, publicado pelo órgão de destino (D30). `classificar` NUNCA
    # o devolve — ele não é motivo de saída da CGU, e por isso não pode virar
    # `MOTIVO_SAIDA`. Está aqui só para a cópia arquivada sair com um rótulo
    # legível no cabeçalho, via `salvar_ato`.
    "nomeacao": "Nomeação ou posse em outro órgão",
}

# Situação correspondente na coluna SITUACAO do dados.csv.
SITUACAO_POR_TIPO = {
    "falecimento": "FALECIDO",
    "demissao": "DEMITIDO",
    "vacancia": "VACÂNCIA",
    "aposentadoria": "APOSENTADO",
    "exoneracao": "EXONERADO",
    "cessao": "CEDIDO",
}

# DECISÃO EDITORIAL (usuário, 14/08/2026, alcance revisto em 16/08/2026): o ATO
# de demissão não vai ao ar.
#
# Demissão é penalidade de processo disciplinar. O ato é público no DOU, mas o
# observatório existe para medir evasão — quem é demitido não escolheu sair —, e
# repetir a penalidade numa página que agrega e ranqueia pessoas nomeadas é outra
# coisa, com outro efeito sobre a vida de alguém. Por isso o ato não entra no
# índice, não é arquivado em `atos_saida/` e não recebe link em tela nenhuma.
#
# O tipo continua sendo RECONHECIDO pelo classificador, de propósito: sem isso a
# pessoa cairia em "saída sem ato identificado", o crawler tentaria de novo todo
# mês, e o site afirmaria não saber uma coisa que sabe.
#
# O QUE MUDOU EM 16/08/2026. Até aqui o dado gravado também era neutro
# (`SITUACAO=DESLIGADO`, `MOTIVO_SAIDA=Desligamento`), e isso era impreciso:
# desligamento não é o nome do que aconteceu. Agora o `dados.csv` grava o motivo
# real, como qualquer outro, e quem decide o que mostrar é a TELA — `motivoDe`,
# em lib/painel.ts, devolve um rótulo neutro para todo mundo, e só a tabela
# detalhada pede o motivo sem máscara. A regra continua a mesma; o que mudou é
# onde ela é aplicada, de um lugar onde apagava o dado para um lugar onde apenas
# não o exibe.
MOTIVOS_NAO_PUBLICADOS = frozenset({"demissao"})

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
    # `DECLARAR?` e não `DECLARAR`: a retificação fala do ato no presente — "na
    # Portaria nº 2.025 [...], QUE DECLARA VAGO o cargo de Auditor Federal [...]
    # ocupado pelo servidor HENRIQUE DA SILVA KRANZFELD". Exigindo o infinitivo,
    # nenhuma retificação de vacância casava, e o Auditor ficava sem ato.
    "vacancia": (
        r"DECLARAR?\s+VAG[OA]",
        r"DECLARAR\s+A\s+VACANCIA",
        r"VACANCIA\s+DO\s+CARGO",
    ),
    "aposentadoria": (r"APOSENTADORIA", r"\bAPOSENTAR\b"),
    "exoneracao": (r"EXONERACAO", r"\bEXONERAR\b"),
    # Cessão: a pessoa continua Auditora da CGU, mas passa a servir em outro
    # órgão, e por isso some do quadro que o Portal da Transparência filtra por
    # COD_ORG_LOTACAO. Para o SIAPE ela "saiu"; o ato é o que explica que não foi
    # evasão. Sem este tipo, o caso caía em "saída sem ato identificado" tendo o
    # ato publicado — foi o que aconteceu com a Portaria nº 604, de 23/02/2023.
    #
    # O ato NÃO cita o cargo de AFFC ("CEDER O SERVIDOR FULANO, matrícula SIAPE
    # nº ..., pertencente ao quadro de pessoal da Controladoria-Geral da União,
    # para exercer a Função Comissionada Executiva de ... do Ministério ..."),
    # então só a busca por NOME o alcança, com a identidade provada pela
    # matrícula. A varredura por frase nunca o vê, e o card não conta cessão.
    "cessao": (r"\bCEDER\b[^.]{0,140}?\bSERVIDOR[A]?\b",),
}

# O que parece cessão e não é: o ato que a desfaz ou a encerra. Nos dois casos a
# pessoa VOLTA para a CGU, e publicá-los como saída inverteria o fato.
PADROES_NAO_E_CESSAO = (
    r"TORNAR\s+SEM\s+EFEITO",
    r"(?:ENCERRAR|DAR\s+POR\s+ENCERRADA)\s+A\s+CESSAO",
)

# O MOTIVO DA VACÂNCIA DECIDE QUE SAÍDA ELA É — e não são todas a mesma.
#
# "Declarar vago" é a forma do ato, não a causa: o art. 33 da Lei 8.112/90 lista
# nove causas e o ato cita o inciso. Duas interessam, e cada uma é um tipo:
#
#   inciso VIII  posse em outro cargo inacumulável  -> vacância
#   inciso I     exoneração (aqui, por desistência
#                do estágio probatório)             -> exoneração
#
# O inciso I faltava, e a falta era silenciosa. A Portaria nº 3.232, de
# 29/09/2025 — "declarar vago, a contar do dia 8 de outubro de 2025, POR
# DESISTÊNCIA DO ESTÁGIO PROBATÓRIO, o cargo de Auditor Federal [...] de acordo
# com art. 33, inciso I" — casava o gatilho da vacância, não casava o motivo, e
# caía fora de todos os tipos. O Auditor aparecia como "saída sem ato
# identificado" com o ato publicado no DOU.
#
# É exoneração e não vacância porque é isso que o ato diz: o inciso I do art. 33
# é a exoneração, e a desistência do estágio probatório é o pedido de saída de
# quem ainda não estabilizou. Chamá-la de "vacância (posse em outro cargo)"
# afirmaria uma posse que o ato não menciona.
#
# Motivo DESCONHECIDO continua não classificando, de propósito: "declarar vago"
# sozinho não distingue quem foi embora de quem se aposentou ou foi promovido, e
# o laço de `classificar` ainda testará os outros tipos — é assim que a
# aposentadoria que termina em "declarar vago o referido cargo" segue sendo
# aposentadoria.
#
# O gatilho da vacância é também o desempate contra a exoneração a pedido, cuja
# redação traz "ficando vago o cargo que atualmente ocupa" — texto que casaria
# com um padrão frouxo tipo "VAGO O CARGO", mas não com "DECLARAR VAGO".
PADRAO_VACANCIA_MOTIVO = r"POSSE\s+EM\s+OUTRO\s+CARGO"
PADRAO_VACANCIA_DESISTENCIA = r"DESISTENCIA\s+DO\s+ESTAGIO\s+PROBATORIO"


def _art_33(inciso: str) -> str:
    """
    Regex da citação de um inciso do art. 33 da Lei 8.112/90, nas duas ordens.

    Às vezes o INCISO é tudo o que o ato diz sobre o motivo — e num caso ele é
    tudo o que o ato diz, ponto. A Portaria nº 3.089, de 09/11/2022, saiu
    TRUNCADA no próprio DOU: "declarar vago, a contar de 27 de outubro de 2022,
    o cargo efetivo de Auditor Federal [...], classe C, padrão II, O." — o texto
    acaba no meio da palavra, sem nome e sem motivo. Foi para consertar isso que
    a retificação de 10/05/2023 existiu. O que restou de motivo no ato original é
    "conforme inciso VIII do art. 33", e é o bastante: o inciso VIII É a posse em
    outro cargo inacumulável.

    O `\\b` no fim do inciso não é decoração: sem ele, `INCISO I` casaria dentro
    de `INCISO VIII` e toda vacância por posse viraria exoneração.
    """
    return (
        rf"ART(?:IGO)?\.?\s*33\s*,?\s*INCISO\s+{inciso}\b"
        rf"|INCISO\s+{inciso}\s+DO\s+ART(?:IGO)?\.?\s*33"
    )


PADRAO_VACANCIA_ART33_VIII = _art_33("VIII")
PADRAO_VACANCIA_ART33_I = _art_33("I")

# Motivo declarado no ato -> tipo de saída. Ordem: o que o ato diz por extenso
# vem antes do que ele diz por citação legal. Inciso não mapeado aqui (III,
# promoção; IV, readaptação) não classifica de propósito: são movimentação
# interna, não saída da CGU.
TIPO_POR_MOTIVO_DA_VACANCIA = (
    (PADRAO_VACANCIA_MOTIVO, "vacancia"),
    (PADRAO_VACANCIA_DESISTENCIA, "exoneracao"),
    (PADRAO_VACANCIA_ART33_VIII, "vacancia"),
    (PADRAO_VACANCIA_ART33_I, "exoneracao"),
)


def tipo_da_vacancia(texto_normalizado: str) -> str | None:
    """Que saída é esta vacância, pelo motivo que o ato declara. `None` se não diz."""
    for padrao, tipo in TIPO_POR_MOTIVO_DA_VACANCIA:
        if re.search(padrao, texto_normalizado):
            return tipo
    return None

# Só conta se o ato realmente falar do cargo efetivo de AFFC.
PADRAO_CARGO = r"AUDITOR[A]?\s+FEDERAL\s+DE\s+FINANCAS\s+E\s+CONTROLE"

# CONCESSÃO DE PENSÃO NÃO É SAÍDA — descoberto em 15/08/2026, quando a varredura
# por frase deixou de parar no primeiro ato de cada tipo e passou a ver tudo.
#
# O ato diz: "Conceder pensão vitalícia a FULANA, na qualidade de cônjuge do
# ex-servidor BELTRANO, ocupante do cargo de Auditor Federal de Finanças e
# Controle [...] falecido em atividade". Ele casa `PADRAO_CARGO` e casa
# `FALECID[OA]`, e por isso era classificado como falecimento — mas o ato é
# sobre a PENSÃO DE OUTRA PESSOA, e sai meses ou anos depois do óbito. Três
# problemas de uma vez:
#
#   - quem o ato nomeia primeiro é o pensionista, que não é Auditor;
#   - a data do ato não é a data da saída;
#   - o instituidor pode ser aposentado, ou de outro cargo. Um dos atos
#     encontrados trata de um TÉCNICO Federal de Finanças e Controle, cargo que
#     está fora do observatório por decisão (D7) — e o nome dele é prefixo do
#     nome de um Auditor real da base, que é o caso de homônimo já documentado
#     em `cita_nome`.
#
# A saída por morte tem ato próprio, com outra redação: "Declarar vago, em
# virtude de falecimento, o cargo efetivo de Auditor Federal...". É esse que
# conta, e ele não fala em conceder pensão.
PADROES_PENSAO = (
    r"CONCEDER\s+PENSAO",
    r"PENSAO\s+(?:VITALICIA|TEMPORARIA)",
    r"INSTITUIDOR\s+DA\s+PENSAO",
)

# ATOS QUE NÃO MOVEM NINGUÉM — descobertos em 16/08/2026, ao varrer o DOU por
# frase desde 2022 pela primeira vez. Nenhum dos dois é saída, e os dois eram
# classificados como aposentadoria por uma palavra solta no texto:
#
#   PORTARIA NORMATIVA SE/CGU nº 224, de 03/09/2025 — "aprova os modelos e
#     estabelece os procedimentos para emissão [...] das cédulas de identificação
#     destinadas às pessoas APOSENTADAS nos cargos da carreira". É uma regra
#     sobre carteirinha de aposentado; não aposenta ninguém.
#
#   EXTRATO DE AJUSTAMENTO DE CONDUTA de 25/08/2023 — instrumento DISCIPLINAR,
#     que nomeia um Auditor e descreve a conduta imputada a ele. A palavra
#     "aposentadoria" aparece só dentro da descrição do fato. Publicá-lo seria
#     duas coisas erradas de uma vez: afirmar uma aposentadoria que não houve, e
#     pôr no ar, com link, um documento disciplinar sobre pessoa nomeada — o
#     mesmo dano que a D18 evita no ato de demissão. Aqui nem chega a ser
#     decisão editorial: o servidor não saiu, e o ato não é sobre saída.
#
# A âncora do primeiro é o INÍCIO do texto, e tem de ser: "Portaria Normativa" é
# citada como fundamento legal por metade dos atos de vacância reais ("no uso da
# competência que lhe foi subdelegada pelo art. 2º da Portaria Normativa CGU
# nº 33"). Procurar a expressão solta excluiria as saídas de verdade.
#   PORTARIA nº 2.909, de 01/09/2025 — instaura Processo Administrativo de
#     Responsabilização contra uma EMPRESA e designa um Auditor para a comissão.
#     A palavra "aposentadoria" está dentro do nome do ente investigado ("CABPREV
#     Casa de Apoio ao Beneficiário Previdenciário de APOSENTADORIA e Pensão do
#     INSS"). Ninguém se aposentou; o ato abre processo contra terceiro.
PADROES_NAO_E_ATO_DE_PESSOAL = (
    r"^PORTARIA\s+NORMATIVA\b",
    r"\bESTA\s+PORTARIA\s+NORMATIVA\b",
    r"\bAJUSTAMENTO\s+DE\s+CONDUTA\b",
    r"\bINSTAURAR\s+PROCESSO\s+ADMINISTRATIVO\b",
)

# ATO QUE TRAZ A PESSOA DE VOLTA É O CONTRÁRIO DE UMA SAÍDA.
#
# A Portaria nº 3.331, de 09/10/2025, "reverte a aposentadoria da servidora
# QUELI RODRIGUES DOS SANTOS [...] para que RETORNE ao quadro de pessoal desta
# Controladoria-Geral da União". Ela casa `APOSENTADORIA`, casa o cargo, é da
# CGU — e diz exatamente o oposto do que seria publicado. É o mesmo erro de sinal
# que `PADROES_NAO_E_DESTINO` evita do outro lado: ler o ato que desfaz como se
# fosse o ato que faz.
PADROES_DE_RETORNO = (
    r"REVERTER\s+A\s+APOSENTADORIA",
    r"REVERSAO\s+D[AE]\s+APOSENTADORIA",
)

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
    r"DECLARAR?\s+VAG[OA]",
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

    # Antes de qualquer tipo: ato de pensão fala do falecimento de um servidor
    # sem ser o ato de saída dele. Ver PADROES_PENSAO.
    if any(re.search(p, normalizado) for p in PADROES_PENSAO):
        return None

    # Ato que não move ninguém — norma geral, instrumento disciplinar, abertura
    # de processo contra terceiro. Ver PADROES_NAO_E_ATO_DE_PESSOAL.
    if any(re.search(p, normalizado) for p in PADROES_NAO_E_ATO_DE_PESSOAL):
        return None

    # Ato que traz a pessoa de volta. Ver PADROES_DE_RETORNO.
    if any(re.search(p, normalizado) for p in PADROES_DE_RETORNO):
        return None

    # IMPORTANTE: quando um tipo é descartado, o certo é `continue` — testar os
    # demais —, nunca `return None`. Os atos se sobrepõem no vocabulário: um ato
    # de aposentadoria termina com "declarar vago o referido cargo", e um
    # `return` no teste de vacância engolia a aposentadoria inteira.
    for tipo in TIPOS_SAIDA:
        if not any(re.search(p, normalizado) for p in PADROES[tipo]):
            continue

        if tipo == "vacancia":
            # O motivo declarado decide QUE saída é: posse em outro cargo é
            # vacância, desistência do estágio probatório é exoneração. Sem
            # motivo reconhecido, `continue` — ainda pode ser outro tipo.
            pelo_motivo = tipo_da_vacancia(normalizado)
            if pelo_motivo is None:
                continue
            return pelo_motivo

        if tipo == "cessao" and any(re.search(p, normalizado) for p in PADROES_NAO_E_CESSAO):
            continue  # ato que desfaz ou encerra a cessão: a pessoa volta

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
    r"DECLARAR?\s+VAG[OA][^.]{{0,120}}{nome}",
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


# ------------------------------------------------------------ nome no próprio ato
#
# De quem é o ato, lido do texto dele. Existe porque o ato do DOU sai ANTES de o
# SIAPE mostrar a ausência (~2 meses de atraso do Portal), e sem isto a saída
# mais recente chegava à tela como "houve uma vacância em 11/08", sem dizer de
# quem — que é justamente a informação que interessa.
#
# ATENÇÃO: isto publica o nome de uma pessoa real a partir de leitura de máquina.
# Por isso os padrões são ANCORADOS na fórmula do ato inteira, com terminador
# explícito, e não em "uma sequência de maiúsculas perto de um verbo". Quando
# nenhum padrão casa, a resposta é vazia — a lista mostra o ato sem nome, que é
# menos pior que mostrar o nome errado.
#
# Medido sobre os 251 atos que já estavam casados com pessoa pelo SIAPE: ver
# `testar_dou.py`, que refaz essa conferência sem rede.
_NOME = r"([A-ZÀ-Ý][A-ZÀ-Ý'\- ]{4,70}?)"

PADROES_NOME_NO_ATO = (
    # "...o cargo de Auditor... ocupado pelo servidor FULANO, matrícula SIAPE"
    # (vacância e falecimento)
    #
    # `SERVIDO[AR]{0,2}` em vez de `SERVIDOR[A]?` porque o DOU erra: a Portaria
    # 1.872, de 20/07/2026, publicou "ocupado pelo servidoa GABRIEL...". Com o
    # grupo exigindo a grafia certa e sendo opcional, a palavra errada caía
    # DENTRO do nome capturado e o site publicaria "servidoa Gabriel" como se
    # fosse o nome da pessoa.
    r"OCUPAD[OA]\s+(?:PEL[OA]|POR)\s+(?:SERVIDO[AR]{0,2}\s+)?" + _NOME + r"\s*,",
    # "...ao servidor FULANO, ocupante do cargo de..."   (aposentadoria voluntária)
    # "...o servidor FULANO, ocupante do cargo de..."    (aposentadoria compulsória)
    # "...o servidor FULANO, SIAPE nº 3302689, do cargo" (exoneração de ofício)
    # O `(?<!EX-)` guarda contra "ex-servidor", que é como o ato de pensão fala
    # do falecido — ato que já não chega aqui (PADROES_PENSAO), mas a fórmula é
    # frequente demais para depender só disso.
    r"(?<!EX-)\bSERVIDOR[A]?\s+" + _NOME + r"\s*,\s*(?:OCUPANTE|MATRICULA|SIAPE)",
    # "EXONERAR, a pedido, FULANO do cargo de Auditor..."
    # "EXONERAR, a pedido, por motivo de desistência do estágio probatório,
    #  FULANO do cargo de Auditor..." — o preâmbulo varia, então quem ancora é o
    # terminador: o nome vem logo antes de "do cargo", e não cruza vírgula
    # porque a vírgula não está na classe de caracteres de `_NOME`.
    r"\bEXONERAR\b[^.]{0,160}?,\s*" + _NOME + r"\s+DO\s+CARGO",
    # "EXONERAR, A PEDIDO LUIZ AUGUSTO DA SILVA ALVES, DO CARGO DE AUDITOR..."
    # — sem a vírgula depois de "a pedido" (Portaria 1.968, de 17/08/2022). O
    # padrão acima depende dessa vírgula como âncora e não casa nada aqui.
    #
    # A âncora, então, passa a ser o próprio preâmbulo, CONSUMIDO explicitamente.
    # Não basta tornar a vírgula opcional no padrão de cima: `_NOME` aceita
    # espaços, então ele engoliria "A PEDIDO LUIZ AUGUSTO DA SILVA ALVES" inteiro
    # e o site publicaria "A Pedido Luiz Augusto" como nome de gente. Este vem
    # DEPOIS na lista, então só roda quando o de cima não casou.
    r"\bEXONERAR\b\s*,?\s*(?:A\s+PEDIDO|DE\s+OFICIO)\s*,?\s*" + _NOME + r"\s*,?\s+DO\s+CARGO",
)


# Partículas que podem vir em minúscula no meio de um nome ("Lucas José Silva
# da Silveira"). Fora destas, todo token de nome começa com maiúscula — seja o
# ato escrito em CAIXA ALTA (222 dos 251 conferidos) ou em Title Case (29).
PARTICULAS_DE_NOME = {"de", "da", "do", "das", "dos", "e", "del", "di", "van", "von"}


def _token_de_nome(token: str, primeiro: bool) -> bool:
    if not token:
        return False
    if token[0].isupper():
        return True
    return not primeiro and token.lower() in PARTICULAS_DE_NOME


def nome_do_ato(texto: str) -> str:
    """
    O nome do Auditor de quem o ato trata, com acento e caixa do original.

    String vazia quando nenhuma fórmula conhecida casa, ou quando o que casou
    não se parece com nome de gente — e isso é resposta, não falha: melhor a
    lista dizer que houve uma exoneração sem dizer de quem do que atribuí-la à
    pessoa errada.
    """
    normalizado, mapa = normalizar_com_mapa(texto)
    for padrao in PADROES_NOME_NO_ATO:
        achado = re.search(padrao, normalizado)
        if not achado:
            continue
        inicio, fim = achado.span(1)
        if inicio >= len(mapa) or fim - 1 >= len(mapa):
            continue

        tokens = texto[mapa[inicio]: mapa[fim - 1] + 1].strip(" ,.").split()
        # Palavra da fórmula que vazou para dentro da captura (o "servidoa" da
        # Portaria 1.872) entra em minúscula e não é partícula: cai fora aqui,
        # antes de virar nome de gente na tela.
        while tokens and not _token_de_nome(tokens[0], primeiro=True):
            tokens.pop(0)

        # Duas palavras é o mínimo para ser nome de gente; sem isto uma fórmula
        # truncada devolveria "SERVIDOR" ou "CARGO" como se fosse pessoa.
        if len(tokens) >= 2 and all(
            _token_de_nome(t, primeiro=(i == 0)) for i, t in enumerate(tokens)
        ):
            return " ".join(tokens)
    return ""


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


def siape_do_ato(texto: str) -> str:
    """A primeira matrícula SIAPE citada no ato, em 7 dígitos. Vazio se não houver.

    Vai a 7 dígitos pelo mesmo motivo de `siape_compativel`: o Portal mascara em
    7 posições preservando o zero à esquerda (`014****`) e o DOU escreve sem ele
    (`149262`). Guardar já preenchido evita ter de lembrar disso em cada uso.
    """
    achados = re.findall(PADRAO_SIAPE, normalizar(texto))
    return achados[0].zfill(7) if achados else ""


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


# ------------------------------------------------------- de quem o ato é, afinal
#
# TRÊS PROVAS, EM ORDEM DE FORÇA, e a distinção não é acadêmica: até 16/08/2026 o
# crawler usava uma prova só — `cita_nome`, que é substring — como PORTA de
# entrada, e a matrícula como VETO. As duas falhavam ao contrário uma da outra, e
# quatro Auditores ficaram sem ato tendo o ato publicado:
#
#   - o DOU erra o nome. A Portaria nº 325, de 02/02/2023 escreve "LUIS PAULO
#     PAGLIONE MARCONDES" onde o SIAPE diz "PAGLIONI". `cita_nome` dava falso, e
#     o ato era descartado ANTES de a matrícula (que batia) poder salvá-lo;
#   - o DOU erra a matrícula. Três vacâncias — Portarias 1.026/2024, 2.529/2024 e
#     2.017/2025 — nomeiam a pessoa por extenso, citam o cargo de AFFC e são da
#     própria CGU, mas trazem um SIAPE que não é o dela (a 2.017 diz 2435442
#     quando a própria CGU, na Portaria 2.605, lista o Auditor como 3347490). O
#     veto de homônimo derrubava os três.
#
# Medido sobre os 251 atos que já estavam casados com pessoa: 236 se provam pela
# matrícula, 15 pela fórmula do ato, ZERO só por citação. O nível `CITACAO` fica
# como estava — não porque alguma coisa depende dele hoje, mas para não perder
# recall no dia em que o DOU inventar uma fórmula que `nome_do_ato` não lê.
IDENTIDADE_SIAPE = "SIAPE"
IDENTIDADE_NOME = "NOME"
IDENTIDADE_CITACAO = "CITACAO"


def nome_do_ato_bate(texto: str, nome: str) -> bool:
    """
    True quando a FÓRMULA do ato nomeia exatamente esta pessoa.

    Diferente de `cita_nome`, que é substring e por isso casa "LUIZ CARLOS DE
    ALMEIDA" dentro de "LUIZ CARLOS DE ALMEIDA SOUZA". Aqui o nome vem de
    `nome_do_ato`, que o recorta com terminador explícito, e a comparação é de
    igualdade — o prefixo de outra pessoa não passa.
    """
    lido = nome_do_ato(texto)
    return bool(lido) and normalizar(lido) == normalizar(nome)


def identidade_no_ato(texto: str, nome: str, matricula_mascarada: str) -> str:
    """
    Como este ato prova ser DESTA pessoa. `""` quando não prova.

    Devolve o nível mais forte que se sustenta:

      `IDENTIDADE_SIAPE`   a matrícula do ato bate com a do Portal. Identidade
                           provada: quem chama pode dispensar a prova do cargo
                           (é o que torna legível a demissão, cujo ato fala do
                           servidor e da penalidade, mas não do cargo).
      `IDENTIDADE_NOME`    a matrícula não decide, ou o ato a escreveu errado,
                           mas a fórmula do ato nomeia exatamente esta pessoa.
      `IDENTIDADE_CITACAO` o nome só aparece solto no meio do texto, e a
                           matrícula não CONFLITA. É o nível fraco: quem chama
                           tem de exigir também o cargo.

    O conflito de matrícula deixou de VETAR e passou a apenas REBAIXAR: com o
    nome exato lido da fórmula, num ato da CGU que cita o cargo de AFFC, a
    identidade se sustenta sem ele. Isso é seguro aqui porque não há nome
    repetido na base — 2.009 pessoas, zero homônimos — e deixa de ser seguro no
    dia em que houver; ver a limitação documentada em `cita_nome`.
    """
    if siape_compativel(texto, matricula_mascarada) is True:
        return IDENTIDADE_SIAPE
    if nome_do_ato_bate(texto, nome):
        return IDENTIDADE_NOME
    if siape_compativel(texto, matricula_mascarada) is False:
        return ""
    return IDENTIDADE_CITACAO if cita_nome(texto, nome) else ""


# --------------------------------------------------- retificação -> ato original
#
# A retificação é um ato sobre outro ato, e às vezes é o ÚNICO que traz o nome da
# pessoa — porque foi o nome que ela veio consertar. Dois casos reais:
#
#   Portaria 3.089, de 09/11/2022, saiu sem dizer de quem era o cargo; a
#   retificação de 10/05/2023 acrescenta "ocupado pelo servidor ANGIVALDO
#   ALMEIDA FERREIRA JUNIOR [...] em virtude de posse em outro cargo".
#
#   Portaria 2.025, de 30/05/2023, declarou vago o cargo de "HENRIQUE DA SILVA
#   KRANZFIELD"; a retificação de 01/06/2023 corrige para "KRANZFELD".
#
# Nos dois, a busca por nome só alcança a retificação — e a retificação, sozinha,
# é um documento pobre: a de Kranzfeld não diz o motivo da vacância, e a de
# Angivaldo não cita o cargo. Classificá-la seria afirmar mais do que ela diz, e
# datar a saída no dia em que o erro foi corrigido.
#
# Por isso o caminho é o outro: ler nela a REFERÊNCIA ao ato original e ir buscar
# o original, que tem o motivo, a data certa e a URL própria. O que a retificação
# fornece é o vínculo com a pessoa.
PADRAO_ATO_RETIFICADO = (
    r"RETIFICA(?:CAO|R|-SE)?\b[^.]{0,80}?"
    r"\bPORTARIA\s+N?[O°º.\s]{0,4}\s*([\d.]+)\s*,\s*"
    r"DE\s+(\d{1,2}O?\s+DE\s+[A-Z]+\s+DE\s+\d{4})"
)


def _numero_com_ponto(numero: str) -> str:
    """`3089` -> `3.089`. O DOU titula com o ponto de milhar; o corpo do ato, nem sempre."""
    digitos = numero.replace(".", "")
    return f"{int(digitos):,}".replace(",", ".") if digitos.isdigit() else numero


def frases_do_ato_retificado(texto: str) -> list[str]:
    """
    Frases de busca que acham o ato que esta retificação corrige. `[]` se não é uma.

    Devolve VARIANTES porque a grafia do número e do dia varia entre o corpo da
    retificação e o título do ato original, e a busca do DOU é por frase exata:
    `3089` no corpo é `3.089` no título, e `1O` (o `1º` já normalizado) é `1º`.
    Quem chama tenta uma por uma e para na primeira que responder.
    """
    achado = re.search(PADRAO_ATO_RETIFICADO, normalizar(texto))
    if not achado:
        return []

    numero, data = achado.group(1).strip(". "), achado.group(2)
    datas = [data] + ([re.sub(r"^(\d{1,2})O\b", r"\1º", data)] if re.match(r"\d{1,2}O\b", data) else [])
    numeros = list(dict.fromkeys([_numero_com_ponto(numero), numero]))

    return [f"PORTARIA Nº {n}, DE {d}" for n in numeros for d in datas]


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
<title>{html_mod.escape(titulo_do_ato(resultado))} — DOU</title>
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
<h1>{html_mod.escape(titulo_do_ato(resultado))}</h1>
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
