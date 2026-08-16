#!/usr/bin/env python3
"""
O ato de posse achado por busca na web (D28) — a QUARTA tentativa de destino.

Este módulo NÃO é executável: é a biblioteca que `enriquecer_destinos_ranking.py`
usa por último. A ordem do observatório, agora completa:

    já saiu (SIAPE/DOU)  ->  destino pelo DOU          (ato federal)
                         ->  destino pelo RANKING      (marca "Nomeado", D26)
                         ->  destino pelo DIÁRIO MUNICIPAL   (ato, D27)
                         ->  destino pela BUSCA WEB    (este módulo, D28)

POR QUE ELE EXISTE, E POR QUE SÓ AGORA
--------------------------------------
O DOU só publica ato federal; o Querido Diário só cobre diário municipal. Sobrava
tudo o que é estadual e tudo o que tem sítio próprio — e é lá que estavam os
achados que nenhuma outra fonte tinha:

    ALINNE PATRICIA DE ANDRADE CARVALHO E SILVA  tc.df.gov.br, posse no TCDF
                                                 em 24/03/2025 (saiu em 05/2025)
    SERGIO LUIS BORGES CRUZ                      trt4.jus.br, nomeado no TRT da
                                                 4ª Região
    ANA CAROLINA GOMES MELLAO HADAD              defensoria.df.gov.br

Nos TRÊS o órgão certo NÃO estava entre os candidatos do ranking. É a terceira
vez que o cruzamento com o ranking se mostra o portão errado (ver D27), e a
razão de ele aqui ser só selo, nunca filtro.

BUSCA WEB SEM CHAVE NÃO FUNCIONA — já foi medido e está na D27. Google, Bing,
Mojeek e Startpage bloqueiam; o DuckDuckGo lite responde com 3 a 8 resultados e
não tem diário no índice. O que funciona é API paga com cota gratuita, e a chave
mora no `.env` (ver `segredos.py`). SEM CHAVE, ESTA ETAPA SIMPLESMENTE NÃO
RODA — nada mais do observatório depende dela.

O ÓRGÃO VEM DO DOMÍNIO, NUNCA DO TEXTO
--------------------------------------
`tc.df.gov.br` é o TCDF, `trt4.jus.br` é o TRT da 4ª Região. É a mesma ideia do
território no `diarios.py`, e é o que dispensa interpretar texto livre — logo,
dispensa IA. Domínio fora do catálogo NÃO vira destino: o caso vai para a pauta
com o link, para alguém acrescentar.

E O DIÁRIO ESTADUAL CONTINUA SEM RESPOSTA. O DOE de um estado publica ato de
TODOS os órgãos daquele estado: `imagens.seplag.ce.gov.br` e `jornal.iof.mg.gov.br`
não dizem se o ato é da SEFAZ, da PGE ou da Polícia Civil. Esses hospedeiros
estão em `HOSPEDEIROS_SEM_ORGAO`, pelo mesmo motivo que o DODF ficou fora do
`diarios.py`. Achar o nome ali é sinal para a pauta, não destino.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import dou
import ranking
import segredos
from dou import normalizar

RAIZ = Path(__file__).resolve().parent.parent
DIR_CACHE = RAIZ / "data" / "cache_buscaweb"

ENDERECO_SERPER = "https://google.serper.dev/search"
ENDERECO_SERPAPI = "https://serpapi.com/search.json"

VALIDADE_HORAS = 24.0
PAUSA_SEGUNDOS = 1.0

# Janela de publicação, em meses, em torno da competência de saída. A posse no
# novo órgão sai ANTES da vacância — ALINNE tomou posse no TCDF em 03/2025 e sua
# saída é 05/2025. Depois da saída também vale, porque a nomeação pode demorar.
#
# A janela não é enfeite: é ela que separa o destino DESTA saída de um movimento
# posterior. A mesma ALINNE aparece como ANALISTA LEGISLATIVA ATIVA no Senado em
# 2026 — verdade, e outro emprego, depois deste.
MESES_ANTES = 12
MESES_DEPOIS = 9


# ------------------------------------------------------------------ a consulta

def consulta_de(nome: str) -> str:
    """A frase que se manda ao buscador. Aspas = frase exata."""
    return f'"{nome}" nomeação diário oficial'


def buscar(nome: str, usar_cache: bool = True) -> list[dict] | None:
    """
    Os resultados orgânicos da busca. `None` quando não deu para perguntar.

    `None` inclui o caso mais comum de todos: NÃO HÁ CHAVE. Quem chama trata os
    dois igual — pula a etapa —, e é isso que faz o observatório inteiro rodar
    sem nenhuma chave configurada.

    NÃO se manda `gl`, `hl` nem `num` junto com a frase entre aspas: o plano
    gratuito do serper responde `400 Query pattern not allowed for free accounts`
    para essa combinação. Só com `q` a frase exata funciona, e os resultados vêm
    brasileiros do mesmo jeito.
    """
    servico, chave = segredos.chave_de_busca_web()
    if not servico:
        return None

    consulta = consulta_de(nome)
    if servico == "serper":
        bruto = _pedir_serper(consulta, chave, usar_cache)
    else:
        bruto = _pedir_serpapi(consulta, chave, usar_cache)
    if not bruto:
        return None
    try:
        dados = json.loads(bruto)
    except ValueError:
        return None

    organicos = dados.get("organic") or dados.get("organic_results") or []
    return [
        {
            "url": r.get("link", ""),
            "titulo": r.get("title", ""),
            "resumo": r.get("snippet", ""),
            "data": r.get("date", ""),
        }
        for r in organicos if r.get("link")
    ]


def _pedir_serper(consulta: str, chave: str, usar_cache: bool) -> str:
    # O serper é POST com a consulta no corpo, e o `dou.baixar` só faz GET. A
    # chave do cache é a consulta, NUNCA a URL — a URL não a contém, mas o
    # hábito de derivar cache de URL com segredo dentro é como segredo vaza para
    # o disco com nome de arquivo legível.
    caminho = dou._caminho_cache(f"serper::{consulta}", DIR_CACHE)
    if usar_cache and caminho.is_file():
        return caminho.read_text(encoding="utf-8")
    pedido = urllib.request.Request(
        ENDERECO_SERPER,
        data=json.dumps({"q": consulta}).encode("utf-8"),
        headers={"X-API-KEY": chave, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            corpo = resposta.read().decode("utf-8", "replace")
    except Exception:
        return ""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(corpo, encoding="utf-8")
    return corpo


def _pedir_serpapi(consulta: str, chave: str, usar_cache: bool) -> str:
    url = ENDERECO_SERPAPI + "?" + urllib.parse.urlencode(
        {"q": consulta, "engine": "google", "google_domain": "google.com.br",
         "hl": "pt-br", "gl": "br", "api_key": chave})
    # A chave está na URL, então o nome do cache é derivado da consulta, não dela.
    caminho = dou._caminho_cache(f"serpapi::{consulta}", DIR_CACHE)
    if usar_cache and caminho.is_file():
        return caminho.read_text(encoding="utf-8")
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                timeout=60) as resposta:
            corpo = resposta.read().decode("utf-8", "replace")
    except Exception:
        return ""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(corpo, encoding="utf-8")
    return corpo


# --------------------------------------------------------- domínio -> órgão

# Hospedeiros que servem a MUITOS órgãos: diário oficial estadual, imprensa
# oficial, agregador. Achar o nome ali não diz de quem é o ato — é o mesmo caso
# do DODF no `diarios.py`, e é por isso que o estadual segue sem resposta.
HOSPEDEIROS_SEM_ORGAO = (
    "imprensaoficial.com.br", "iof.mg.gov.br", "seplag.ce.gov.br",
    "dodf.df.gov.br", "sinj.df.gov.br", "in.gov.br", "jusbrasil.com.br",
    "escavador.com", "scribd.com", "cloudfront.net", "amazonaws.com",
    "cebraspe.org.br", "cespe.unb.br", "fgv.br", "cesgranrio.org.br",
    "direcaoconcursos.com.br", "tecconcursos.com.br", "novaconcursos.com.br",
    "linkedin.com", "instagram.com", "facebook.com", "gov.br/gestao",
)

# O órgão de ORIGEM. Achar a pessoa no sítio da CGU é o esperado — ela trabalhou
# lá — e não é destino nenhum.
DOMINIOS_DA_ORIGEM = ("cgu.gov.br",)

# O catálogo, fechado. Os nomes canônicos vêm de `ranking.ORGAO_POR_ROTULO` para
# que a tabela de destinos não rache em duas grafias do mesmo órgão (D24).
ORGAO_POR_DOMINIO = {
    "tcu.gov.br": "Tribunal de Contas da União",
    "senado.leg.br": "Senado Federal",
    "camara.leg.br": "Câmara dos Deputados",
    "agu.gov.br": "Advocacia-Geral da União",
    "bcb.gov.br": "Banco Central do Brasil",
    "tc.df.gov.br": "Tribunal de Contas do Distrito Federal",
    "tcm.sp.gov.br": "Tribunal de Contas do Município de São Paulo",
    "defensoria.df.gov.br": "Defensoria Pública do Distrito Federal",
    "cl.df.gov.br": "Câmara Legislativa do Distrito Federal",
    "tjdft.jus.br": "Tribunal de Justiça do Distrito Federal e dos Territórios",
    "prefeitura.sp.gov.br": "Prefeitura de São Paulo",
    "petrobras.com.br": "Petróleo Brasileiro S.A. (Petrobras)",
}

# Famílias com numeração previsível, como no `ranking._FAMILIAS`. O molde tem de
# reproduzir EXATAMENTE a forma que o catálogo do ranking já usa.
_TRT_DOMINIO = re.compile(r"^trt(\d{1,2})\.jus\.br$")
_TRF_DOMINIO = re.compile(r"^trf(\d)\.jus\.br$")
_TRE_DOMINIO = re.compile(r"^tre-([a-z]{2})\.jus\.br$")
_TCE_DOMINIO = re.compile(r"^tce\.([a-z]{2})\.gov\.br$")
# `aracaju.se.gov.br`, `saoluis.ma.gov.br`: cidade.uf.gov.br é o padrão dos
# municípios. `sp.gov.br` (só a UF) é governo estadual e NÃO cai aqui.
_MUNICIPIO_DOMINIO = re.compile(r"^([a-z0-9-]{3,})\.([a-z]{2})\.gov\.br$")


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def orgao_do_dominio(url: str) -> str:
    """
    O órgão canônico de um endereço. `""` quando não dá para afirmar.

    Vazio é a resposta certa para hospedeiro genérico, para o sítio da própria
    CGU e para domínio que o catálogo não conhece. Nenhum desses vira destino.
    """
    host = _host(url)
    if not host:
        return ""
    if any(host.endswith(d) or d in host for d in DOMINIOS_DA_ORIGEM):
        return ""
    if any(host.endswith(h) or h in host for h in HOSPEDEIROS_SEM_ORGAO):
        return ""

    for dominio, orgao in ORGAO_POR_DOMINIO.items():
        if host == dominio or host.endswith("." + dominio):
            return orgao

    achado = _TRT_DOMINIO.match(host)
    if achado:
        return f"Tribunal Regional do Trabalho da {int(achado.group(1))}ª Região"
    achado = _TRF_DOMINIO.match(host)
    if achado:
        return f"Tribunal Regional Federal da {int(achado.group(1))}ª Região"
    achado = _TRE_DOMINIO.match(host)
    if achado and achado.group(1).upper() in ranking._UF:
        return f"Tribunal Regional Eleitoral {ranking._UF[achado.group(1).upper()]}"
    achado = _TCE_DOMINIO.match(host)
    if achado and achado.group(1).upper() in ranking._UF:
        return f"Tribunal de Contas do Estado {ranking._UF[achado.group(1).upper()]}"

    achado = _MUNICIPIO_DOMINIO.match(host)
    if achado and achado.group(2).upper() in ranking._UF:
        cidade = achado.group(1)
        conhecido = ranking.ORGAO_POR_ROTULO.get(f"ISS {normalizar(cidade)}")
        return conhecido or ""
    return ""


# ------------------------------------------------ o resultado é sobre POSSE?

_POSSE = re.compile(
    r"\bPOSSE\b|\bEMPOSSAD[OA]S?\b|\bNOMEAR\b|\bNOMEIA\b|\bNOMEAD[OA]S?\b"
    r"|\bNOMEACAO\b|\bNOMEACOES\b|\bTOMAR POSSE\b|\bEXERCICIO\b|\bLOTAC\w*\b"
)

# O ruído dominante: o nome da pessoa em lista de classificação de concurso que
# ela apenas prestou. VICTOR GABRIEL CARVALHO SANTOS SOUZA aparece em Aracaju e
# no Ceará, nos dois casos em lista de resultado.
_NAO_E_POSSE = re.compile(
    r"\bRESULTADO\b|\bCLASSIFICACAO\b|\bNOTA FINAL\b|\bGABARITO\b|\bINSCRICAO\b"
    r"|\bISENCAO\b|\bHETEROIDENTIFICACAO\b|\bCONVOCACAO PARA PROVA\w*\b"
    r"|\bEDITAL DE ABERTURA\b|\bCADASTRO DE RESERVA\b|\bLICITACAO\b|\bCONTRATO\b"
)

JANELA_DA_FORMULA = 160


def fala_de_posse(texto: str, nome: str) -> bool:
    """
    O texto diz que ESTA pessoa tomou posse — e não que ela prestou um concurso.

    Mesma disciplina do `diarios.parece_nomeacao`: a palavra tem de estar perto
    do nome, e vence a mais próxima. Aqui o texto é curto (título mais resumo do
    buscador), mas a regra continua valendo — um resumo mistura o fim de uma
    frase com o começo de outra.
    """
    plano = normalizar(texto)
    alvo = normalizar(nome)
    if not alvo or alvo not in plano:
        return False
    for achado in re.finditer(re.escape(alvo), plano):
        inicio = max(0, achado.start() - JANELA_DA_FORMULA)
        fim = achado.end() + JANELA_DA_FORMULA
        vizinhanca = plano[inicio:fim]
        deslocamento = achado.start() - inicio
        perto_posse = _mais_perto(_POSSE, vizinhanca, deslocamento, len(alvo))
        perto_veto = _mais_perto(_NAO_E_POSSE, vizinhanca, deslocamento, len(alvo))
        if perto_posse is not None and perto_posse < perto_veto:
            return True
    return False


def _mais_perto(padrao: re.Pattern, texto: str, nome_em: int, nome_tam: int) -> float:
    """Distância da ocorrência mais próxima do nome. `inf` se não houver."""
    melhor = float("inf")
    for achado in padrao.finditer(texto):
        if achado.end() <= nome_em:
            distancia = nome_em - achado.end()
        elif achado.start() >= nome_em + nome_tam:
            distancia = achado.start() - (nome_em + nome_tam)
        else:
            distancia = 0
        melhor = min(melhor, distancia)
    return melhor


# ------------------------------------------------------------- a data importa

_MESES = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), start=1)}


def competencia_do_resultado(data: str) -> str:
    """
    `AAAAMM` da data que o buscador informou. `""` quando ele não informou.

    O formato é o do Google em inglês ("Mar 24, 2025"), porque é assim que a API
    o devolve mesmo com a consulta em português.
    """
    achado = re.match(r"\s*([A-Za-z]{3})[a-z]*\s+\d{1,2},\s*(\d{4})", data or "")
    if achado and achado.group(1).lower() in _MESES:
        return f"{achado.group(2)}{_MESES[achado.group(1).lower()]:02d}"
    achado = re.search(r"\b(20\d{2})\b", data or "")
    return f"{achado.group(1)}01" if achado else ""


def na_janela(competencia: str, mes_saida: str) -> bool:
    """
    A publicação cabe na janela em torno da saída?

    Resultado SEM data passa. É a escolha certa: o buscador informa a data em
    talvez metade dos resultados, e exigi-la descartaria metade do sinal. Quem
    filtra o resto é a fórmula de posse.
    """
    if not competencia:
        return True
    if len(mes_saida or "") < 6 or not mes_saida[:6].isdigit():
        return False
    def em_meses(m):
        return int(m[:4]) * 12 + int(m[4:6]) - 1
    return -MESES_ANTES <= em_meses(competencia) - em_meses(mes_saida) <= MESES_DEPOIS


# --------------------------------------------------------------- a decisão

def achados_da_pessoa(nome: str, mes_saida: str, resultados: list[dict]) -> list[dict]:
    """Os resultados que sustentam um órgão de destino para esta pessoa."""
    achados = []
    for resultado in resultados or []:
        orgao = orgao_do_dominio(resultado["url"])
        if not orgao or orgao == ranking.ORGAO_CGU:
            continue
        texto = f"{resultado['titulo']} {resultado['resumo']}"
        if not fala_de_posse(texto, nome):
            continue
        competencia = competencia_do_resultado(resultado["data"])
        if not na_janela(competencia, mes_saida):
            continue
        achados.append({
            "orgao": orgao,
            "url": resultado["url"],
            "data": resultado["data"],
            "trecho": " ".join(texto.split())[:400],
        })
    return achados


def destino_da_pessoa(nome: str, mes_saida: str, resultados: list[dict] | None) -> dict:
    """
    O destino que a busca web sustenta — ou a razão de não haver um.

    `decisao`:
      SEM_BUSCA     não há chave configurada, ou a consulta falhou
      SEM_ACHADO    a busca respondeu e nada nela é posse desta pessoa num
                    órgão que o catálogo de domínios conheça
      UNICO_WEB     um órgão só  -> vai à tela
      VARIOS_WEB    mais de um  -> pauta, com os links

    O órgão NÃO precisa estar entre os candidatos do ranking. Foi medido três
    vezes que exigir isso é o portão errado: ALINNE (TCDF), SERGIO (TRT 4ª) e
    ANA CAROLINA (Defensoria do DF) têm ato explícito em órgão que o ranking não
    conhece. O cruzamento vira SELO, não filtro — ver `enriquecer_destinos_ranking`.
    """
    resposta = {"decisao": "SEM_BUSCA", "orgao": "", "achados": [], "url": ""}
    if resultados is None:
        return resposta

    achados = achados_da_pessoa(nome, mes_saida, resultados)
    resposta["achados"] = achados
    if not achados:
        resposta["decisao"] = "SEM_ACHADO"
        return resposta

    orgaos = sorted({a["orgao"] for a in achados})
    if len(orgaos) == 1:
        resposta["decisao"] = "UNICO_WEB"
        resposta["orgao"] = orgaos[0]
        resposta["url"] = achados[0]["url"]
        return resposta

    resposta["decisao"] = "VARIOS_WEB"
    return resposta


def orgaos_na_ficha(nome: str, linhas: list[dict]) -> set[str]:
    """
    TODOS os órgãos que a ficha do ranking associa à pessoa, com marca ou sem.

    Serve ao SELO, não à decisão: destino que a busca web achou e que também
    consta da ficha tem duas fontes independentes concordando, e é isso que o
    selo `RANKING` passa a significar quando aparece num destino vindo da web.
    Basta o nome estar na lista — não se exige marca azul nem verde.
    """
    return {
        orgao for linha in ranking.linhas_da_pessoa(nome, linhas or [])
        for orgao in [ranking.canonico(linha["concurso"])]
        if orgao and orgao != ranking.ORGAO_CGU
    }
