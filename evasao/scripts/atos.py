#!/usr/bin/env python3
"""
O índice único dos atos de saída publicados no DOU.

Este módulo NÃO é executável: é a biblioteca que dá aos dois crawlers um lugar
só para gravar o que acharam.

POR QUE ELE EXISTE
------------------
Até 15/08/2026 havia DUAS estruturas paralelas guardando a mesma coisa:

  varredura por FRASE  -> data/dias_sem_perder_AFFC/*.html + o JSON do card
  varredura por NOME   -> data/saidas_dou/*.html          + saidas_dou.csv

O mesmo ato chegava a ser arquivado nas duas pastas (a exoneração de 25/02/2026
estava em ambas), e as duas discordavam sobre qual era a última saída — porque
elas não podem concordar por construção:

  - a varredura por NOME parte do `dados.csv`, que parte do SIAPE. O Portal da
    Transparência publica com ~2 meses de atraso, então ela NUNCA enxerga o que
    o DOU publicou depois da última competência;
  - a varredura por FRASE lê o DOU direto, então enxerga — mas parava no
    primeiro ato de cada tipo e não guardava mais nada.

Agora as duas escrevem AQUI, e o card é DERIVADO deste índice
(`gerar_card_dou.py`), não de uma varredura própria. A pasta `saidas_dou/` passa
a ser o arquivo único das cópias dos atos.

O QUE É CHAVE
-------------
`URL_TITLE`, o identificador do ato no in.gov.br — e só ele. Não é pessoa: um
ato pode citar mais de uma, e um ato recente ainda não tem pessoa nenhuma do
lado do SIAPE. `ID_SERVIDOR_PORTAL` fica preenchido quando a varredura por nome
casou o ato com alguém, e VAZIO enquanto o SIAPE não alcançar aquele mês. Essa
coluna vazia não é falha: é exatamente a medida de quanto o DOU está à frente.

D18 — O QUE NÃO ENTRA
---------------------
Ato de DEMISSÃO não é registrado aqui, em nenhuma hipótese. Este índice e a
pasta `saidas_dou/` vão para repositório público e para o site; gravar a linha
já publicaria o link. `registrar` devolve `None` nesse caso, e é o único ponto
do pipeline que precisa lembrar disso.
"""

from __future__ import annotations

import csv
import html
import re
from datetime import date, datetime
from pathlib import Path

import dou

RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "data"

ARQ_INDICE = DIR_DADOS / "atos_dou.csv"
DIR_ATOS = DIR_DADOS / "saidas_dou"
ARQ_SAIDAS = DIR_DADOS / "saidas_dou.csv"

# Até onde a varredura por frase já chegou. Guardado à parte porque "último ato
# encontrado" não serve de marca: três meses sem nenhuma saída fariam a
# varredura refazer três meses todo dia, sem nada de novo para achar.
ARQ_VARREDURA = DIR_DADOS / "varredura_dou.txt"

COLUNAS = (
    "URL_TITLE",
    "TIPO",
    "ROTULO",
    "DATA_PUBLICACAO",
    "TITULO",
    # De quem é o ato, LIDO DO TEXTO DELE (`dou.nome_do_ato`). É o que permite a
    # saída recente chegar à tela com nome antes de o SIAPE confirmar — sem isto
    # o painel só saberia dizer "houve uma vacância em 11/08". Quando a varredura
    # por nome casa o ato com uma pessoa, este campo passa a vir do SIAPE, que é
    # a grafia oficial.
    "NOME",
    "MATRICULA_SIAPE",
    "SECAO",
    "EDICAO",
    "PAGINA",
    "ORGAO",
    "URL",
    "ARQUIVO",
    "ID_SERVIDOR_PORTAL",
    "FONTE_VARREDURA",
)

# Como cada linha chegou ao índice. Serve para saber o que a varredura por nome
# ainda não confirmou — não para hierarquia de confiança: o ato é o mesmo.
FONTE_FRASE = "frase"
FONTE_NOME = "nome"


def ler() -> dict[str, dict]:
    """O índice inteiro, indexado por URL_TITLE."""
    if not ARQ_INDICE.is_file():
        return {}
    with open(ARQ_INDICE, encoding="utf-8-sig", newline="") as fh:
        linhas = [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]
    return {l["URL_TITLE"]: l for l in linhas if l.get("URL_TITLE")}


def gravar(indice: dict[str, dict]) -> None:
    """Grava ordenado por data e chave — o arquivo tem de ser byte a byte estável."""
    ARQ_INDICE.parent.mkdir(parents=True, exist_ok=True)
    linhas = sorted(indice.values(), key=lambda l: (l.get("DATA_PUBLICACAO", ""), l["URL_TITLE"]))
    with open(ARQ_INDICE, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(COLUNAS), delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def _juntar_fontes(anterior: str, nova: str) -> str:
    fontes = {f for f in (anterior or "").split("+") if f}
    fontes.add(nova)
    return "+".join(sorted(fontes))


def registrar(
    indice: dict[str, dict],
    resultado: dict,
    tipo: str,
    texto: str,
    fonte: str,
    id_servidor: str = "",
    nome: str = "",
    arquivar: bool = True,
) -> dict | None:
    """
    Põe um ato no índice e arquiva a cópia dele. Devolve a linha, ou `None`.

    `None` significa "este ato não vai ao ar": ou não tem `urlTitle`, ou é de um
    tipo não publicado (D18). O chamador não precisa saber qual dos dois — em
    nenhum dos casos há linha, arquivo ou link.

    Reescrever um ato que já está no índice é normal e idempotente: as duas
    varreduras acham os mesmos atos, e a segunda só acrescenta o que a primeira
    não tinha (tipicamente o `ID_SERVIDOR_PORTAL`, que só a busca por nome sabe).
    """
    chave = resultado.get("urlTitle") or ""
    if not chave or tipo in dou.MOTIVOS_NAO_PUBLICADOS:
        return None

    anterior = indice.get(chave, {})
    linha = {
        "URL_TITLE": chave,
        "TIPO": tipo,
        "ROTULO": dou.ROTULOS.get(tipo, tipo),
        "DATA_PUBLICACAO": dou.data_iso(resultado) or anterior.get("DATA_PUBLICACAO", ""),
        "TITULO": dou.titulo_do_ato(resultado) or anterior.get("TITULO", ""),
        # O nome do SIAPE (passado por quem busca por nome) vence o lido do ato:
        # é a grafia oficial, e o ato às vezes abrevia ou erra.
        "NOME": nome or anterior.get("NOME", "") or dou.nome_do_ato(texto),
        "MATRICULA_SIAPE": dou.siape_do_ato(texto) or anterior.get("MATRICULA_SIAPE", ""),
        "SECAO": resultado.get("pubName") or anterior.get("SECAO", ""),
        "EDICAO": str(resultado.get("editionNumber") or anterior.get("EDICAO", "")),
        "PAGINA": str(resultado.get("numberPage") or anterior.get("PAGINA", "")),
        "ORGAO": resultado.get("hierarchyStr") or anterior.get("ORGAO", ""),
        "URL": dou.BASE_ATO + chave,
        # Um id já registrado não é apagado por uma passagem que não tenha o
        # dele: a varredura por frase não sabe de quem é o ato, e sobrescrever
        # com vazio desfaria o casamento que a busca por nome tinha feito.
        "ID_SERVIDOR_PORTAL": id_servidor or anterior.get("ID_SERVIDOR_PORTAL", ""),
        "FONTE_VARREDURA": _juntar_fontes(anterior.get("FONTE_VARREDURA", ""), fonte),
    }

    if arquivar and texto:
        linha["ARQUIVO"] = dou.salvar_ato(resultado, tipo, texto, DIR_ATOS)
    else:
        linha["ARQUIVO"] = anterior.get("ARQUIVO", "") or dou.nome_arquivo(resultado, tipo)

    indice[chave] = linha
    return linha


def _url_title(url: str) -> str:
    return url[len(dou.BASE_ATO):] if url.startswith(dou.BASE_ATO) else ""


_TIPO_POR_ROTULO = {rotulo: tipo for tipo, rotulo in dou.ROTULOS.items()}


def importar_de_saidas_dou(indice: dict[str, dict]) -> int:
    """
    Traz para o índice os atos que a varredura por nome já tinha achado.

    Existe por duas razões. A primeira é histórica: quando o índice nasceu, o
    `saidas_dou.csv` já trazia 251 atos, e recrawlá-los seria jogar fora ~50
    minutos de rede por nada. A segunda é permanente: reconciliar as duas
    varreduras é barato e mantém o índice inteiro mesmo se alguém rodar só um
    dos crawlers.

    Linha sem `ATO_SAIDA_URL` é pulada — é o caso de quem saiu sem ato
    identificado e, de propósito, o de quem tem motivo não publicado (D18).
    """
    if not ARQ_SAIDAS.is_file():
        return 0

    with open(ARQ_SAIDAS, encoding="utf-8-sig", newline="") as fh:
        saidas = [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]

    novos = 0
    for saida in saidas:
        chave = _url_title(saida.get("ATO_SAIDA_URL", ""))
        tipo = _TIPO_POR_ROTULO.get(saida.get("MOTIVO_SAIDA", ""))
        if not chave or not tipo or tipo in dou.MOTIVOS_NAO_PUBLICADOS:
            continue

        anterior = indice.get(chave, {})
        if not anterior:
            novos += 1
        indice[chave] = {
            "URL_TITLE": chave,
            "TIPO": tipo,
            "ROTULO": dou.ROTULOS[tipo],
            "DATA_PUBLICACAO": saida.get("DATA_PUBLICACAO_SAIDA", "") or anterior.get("DATA_PUBLICACAO", ""),
            "TITULO": saida.get("ATO_SAIDA_TITULO", "") or anterior.get("TITULO", ""),
            # Aqui o nome vem do SIAPE, não do ato: é a grafia oficial.
            "NOME": saida.get("NOME", "") or anterior.get("NOME", ""),
            "MATRICULA_SIAPE": anterior.get("MATRICULA_SIAPE", ""),
            # Seção, edição e página não estão no saidas_dou.csv. Ficam vazias:
            # o card não as usa, e a cópia arquivada do ato traz todas.
            "SECAO": anterior.get("SECAO", ""),
            "EDICAO": anterior.get("EDICAO", ""),
            "PAGINA": anterior.get("PAGINA", ""),
            "ORGAO": anterior.get("ORGAO", ""),
            "URL": saida["ATO_SAIDA_URL"],
            "ARQUIVO": saida.get("ATO_SAIDA_ARQUIVO", "") or anterior.get("ARQUIVO", ""),
            "ID_SERVIDOR_PORTAL": saida.get("ID_SERVIDOR_PORTAL", "")
            or anterior.get("ID_SERVIDOR_PORTAL", ""),
            "FONTE_VARREDURA": _juntar_fontes(anterior.get("FONTE_VARREDURA", ""), FONTE_NOME),
        }

    return novos


# ------------------------------------------------- releitura das cópias em disco

# O texto na cópia arquivada por `dou.salvar_ato`. É `<div class="texto">…</div>`
# com o conteúdo escapado — nada a ver com o `.texto-dou` da página do in.gov.br,
# que é o que `dou.extrair_texto` lê.
_PADRAO_TEXTO_ARQUIVADO = re.compile(r'<div class="texto">(.*?)</div>', re.S)


def texto_arquivado(arquivo: str) -> str:
    """O texto do ato a partir da cópia em `saidas_dou/`. Vazio se não der."""
    caminho = DIR_ATOS / (arquivo or "")
    if not arquivo or not caminho.is_file():
        return ""
    achado = _PADRAO_TEXTO_ARQUIVADO.search(caminho.read_text(encoding="utf-8"))
    return html.unescape(achado.group(1)) if achado else ""


def completar_do_arquivo(indice: dict[str, dict]) -> int:
    """
    Preenche NOME e MATRICULA_SIAPE que faltarem, relendo as cópias em disco.

    Sem rede: o ato já está arquivado, e o que muda com o tempo é o que sabemos
    ler dele. Serve para o dia em que um padrão novo de `dou.nome_do_ato` passa a
    reconhecer uma fórmula que antes escapava — em vez de recrawlar 264 atos,
    relê-se o que já está aqui. Idempotente.
    """
    completados = 0
    for linha in indice.values():
        if linha.get("NOME") and linha.get("MATRICULA_SIAPE"):
            continue
        texto = texto_arquivado(linha.get("ARQUIVO", ""))
        if not texto:
            continue
        if not linha.get("NOME"):
            linha["NOME"] = dou.nome_do_ato(texto)
        if not linha.get("MATRICULA_SIAPE"):
            linha["MATRICULA_SIAPE"] = dou.siape_do_ato(texto)
        if linha.get("NOME") or linha.get("MATRICULA_SIAPE"):
            completados += 1
    return completados


# --------------------------------------------------------------- leitura do card

def mais_recentes_por_tipo(indice: dict[str, dict], tipos) -> dict[str, dict]:
    """O ato mais recente de cada tipo pedido.

    Empate de data é resolvido pela chave, e não por acaso: em 11/08/2026 saíram
    duas vacâncias (Portarias 2.099 e 2.100). O card mostra UMA como comprovação
    da data, não como censo — o que não pode é a escolha mudar entre execuções.
    """
    recentes: dict[str, dict] = {}
    for linha in indice.values():
        tipo = linha.get("TIPO", "")
        if tipo not in tipos or not linha.get("DATA_PUBLICACAO"):
            continue
        atual = recentes.get(tipo)
        chave_nova = (linha["DATA_PUBLICACAO"], linha["URL_TITLE"])
        if atual is None or chave_nova > (atual["DATA_PUBLICACAO"], atual["URL_TITLE"]):
            recentes[tipo] = linha
    return recentes


def competencia(data_iso: str) -> str:
    """`AAAA-MM-DD` -> `AAAAMM`. Vazio se a data não servir."""
    return data_iso[:4] + data_iso[5:7] if len(data_iso) >= 7 else ""


def posteriores_a_competencia(indice: dict[str, dict], mes: str) -> list[dict]:
    """
    Atos publicados depois da última competência que o SIAPE já entregou.

    É a medida honesta da defasagem entre as duas fontes: cada linha aqui é uma
    saída que o DOU já anunciou e que o Portal da Transparência ainda não
    mostrou. Elas NÃO entram na contagem de evasão — quem conta é o SIAPE, pela
    ausência a partir da última presença (D13).
    """
    if not mes:
        return []
    return sorted(
        (l for l in indice.values() if competencia(l.get("DATA_PUBLICACAO", "")) > mes),
        key=lambda l: (l["DATA_PUBLICACAO"], l["URL_TITLE"]),
    )


# ------------------------------------------------------------ marca da varredura

def ler_varredura() -> date | None:
    """A data até onde a varredura por frase já cobriu. `None` se nunca rodou."""
    if not ARQ_VARREDURA.is_file():
        return None
    try:
        return datetime.strptime(ARQ_VARREDURA.read_text(encoding="utf-8").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def gravar_varredura(ate: date) -> None:
    ARQ_VARREDURA.parent.mkdir(parents=True, exist_ok=True)
    ARQ_VARREDURA.write_text(ate.strftime("%Y-%m-%d") + "\n", encoding="utf-8")
