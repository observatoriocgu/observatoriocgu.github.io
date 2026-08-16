#!/usr/bin/env python3
"""
O ato de nomeação em diário oficial MUNICIPAL, pelo Querido Diário (D27).

Este módulo NÃO é executável: é a biblioteca que `enriquecer_destinos_ranking.py`
usa como TERCEIRA tentativa de descobrir o destino de quem saiu. A ordem do
observatório continua a mesma, e ganha um degrau no fim:

    já saiu (SIAPE/DOU)  ->  destino pelo DOU        (ato federal, o mais forte)
                         ->  destino pelo ranking    (marca "Nomeado", D26)
                         ->  destino pelo DIÁRIO MUNICIPAL  (este módulo)

POR QUE ELE EXISTE
------------------
O DOU só publica ato federal. Quem sai da CGU para SEFAZ, prefeitura ou tribunal
de contas estadual não aparece nele — e é exatamente a maior parte de quem fica
sem destino. O ranking dos concursos ajuda, mas ele cataloga APROVAÇÃO, não
nomeação: a marca azul existe quando alguém alimentou aquela lista, e some em
concurso inteiro (o TCU não tem uma marca sequer em 38 linhas, ver a D26).

O Querido Diário (Open Knowledge Brasil) agrega diários oficiais MUNICIPAIS com
API pública, sem chave, e com busca por FRASE EXATA. Duas propriedades o tornam
utilizável aqui:

  1. o resultado traz o TERRITÓRIO do diário. O órgão não precisa ser lido do
     texto — o município já é a resposta. É o que dispensa qualquer extração de
     nome de órgão a partir de texto livre.
  2. o que se acha é um ATO, não um indício: "O PREFEITO MUNICIPAL DE SANTOS
     [...] nomeia, após concurso público, CARLOS MOACYR FERREIRA NETO, para
     exercer o cargo de Procurador" é da mesma natureza do que o `dou.py` lê.

O QUE ELE NÃO ALCANÇA, E É MUITO
--------------------------------
**Diário estadual (DOE) NÃO está no Querido Diário.** Ele é municipal. Medido
nas 20 pessoas que estavam na pauta em 16/08/2026: 11 não têm um único diário, e
são justamente as de SEFAZ RN, SEFAZ AM, SEFAZ PE, SEFAZ CE e SEFAZ MG. Este
módulo resolve o pedaço municipal do problema, e só ele. Não prometer mais.

A AUSÊNCIA, AQUI TAMBÉM, NÃO É INFORMAÇÃO — pelo mesmo motivo da D26: não achar
ato em diário municipal não diz que a pessoa não foi para um município, diz que
aquele município pode não estar coberto, ou que o PDF não virou texto. Só a
PRESENÇA vale.

O DF FICA DE FORA DE PROPÓSITO
------------------------------
O DODF é um diário só para muitos órgãos — GDF, TCDF, Câmara Legislativa,
Defensoria Pública, Polícia Civil. O território "Brasília/DF" não identifica o
órgão, e é justamente lá que estão os casos mais tentadores (ANA CAROLINA GOMES
MELLAO HADAD aparece nomeada Defensora Pública do DF em 05/2024). Território de
DF vai para a pauta com o trecho, nunca para a tela. Ver `ORGAO_POR_TERRITORIO`.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import unicodedata
from pathlib import Path

import dou
import ranking
from dou import normalizar

RAIZ = Path(__file__).resolve().parent.parent
DIR_CACHE = RAIZ / "data" / "cache_diarios"

BASE = "https://api.queridodiario.ok.org.br/api/gazettes"

# A resposta é JSON pequeno e a busca é por nome de gente: o que ela devolve hoje
# não é o que devolverá quando o próximo diário for indexado. Cache curto, como
# a busca do ranking.
VALIDADE_HORAS = 12.0
PAUSA_SEGUNDOS = 1.5

# Quantos resultados pedir e de que tamanho. Trechos maiores custam banda e
# ajudam pouco: a fórmula de nomeação fica colada ao nome.
TAMANHO_PAGINA = 30
TAMANHO_TRECHO = 500
TRECHOS_POR_DIARIO = 3

# JANELA. A posse no novo cargo costuma ser publicada ANTES da vacância na CGU —
# a mesma observação que o `enriquecer_saidas.py` já faz para o DOU, onde a
# janela é [-6, +6] meses. Aqui ela é maior para trás porque a convocação e a
# nomeação municipal costumam vir em série (1ª, 2ª, 3ª chamada) ao longo de
# meses: LEONARDO TOIOMOTO foi convocado em Paulínia em 19/05, 05/06 e 25/06 de
# 2025, e saiu da CGU na competência 05/2025.
MESES_ANTES = 12
MESES_DEPOIS = 6


# ------------------------------------------------------------------ a consulta

def _janela(mes_saida: str) -> tuple[str, str]:
    """
    `AAAAMM` -> (`AAAA-MM-DD`, `AAAA-MM-DD`), a janela de publicação.

    Competência ausente ou malformada devolve uma janela IMPOSSÍVEL, e não uma
    janela aberta: sem saber quando a pessoa saiu, qualquer ato de nomeação da
    vida dela serviria, inclusive o de antes de entrar na CGU. Quem chama sem
    competência tem de receber lista vazia, não o resultado mais frouxo.
    """
    if len(mes_saida or "") < 6 or not mes_saida[:6].isdigit():
        return "9999-01-01", "9999-01-02"
    ano, mes = int(mes_saida[:4]), int(mes_saida[4:6])
    if not 1 <= mes <= 12:
        return "9999-01-01", "9999-01-02"
    total = ano * 12 + (mes - 1)
    inicio, fim = total - MESES_ANTES, total + MESES_DEPOIS
    return (f"{inicio // 12:04d}-{inicio % 12 + 1:02d}-01",
            f"{fim // 12:04d}-{fim % 12 + 1:02d}-28")


def url_da_consulta(nome: str, mes_saida: str) -> str:
    """A URL que qualquer pessoa pode abrir para repetir o que lemos."""
    desde, ate = _janela(mes_saida)
    return BASE + "?" + urllib.parse.urlencode([
        ("querystring", f'"{nome}"'),
        ("published_since", desde),
        ("published_until", ate),
        ("size", str(TAMANHO_PAGINA)),
        ("sort_by", "descending_date"),
        ("excerpt_size", str(TAMANHO_TRECHO)),
        ("number_of_excerpts", str(TRECHOS_POR_DIARIO)),
    ])


def buscar(nome: str, mes_saida: str, usar_cache: bool = True) -> list[dict] | None:
    """
    Os diários da janela que contêm a FRASE EXATA do nome. `None` se não deu.

    As aspas na `querystring` são o que faz a busca ser por frase — a sintaxe é a
    `simple_query_string` do OpenSearch. Sem elas a consulta vira OU entre as
    palavras e devolve dez mil diários com "ALVES" em qualquer lugar.

    `None` e `[]` são coisas diferentes, como em `ranking.buscar_por_nome`: lista
    vazia é "ninguém com esse nome nos diários da janela", `None` é "não
    conseguimos perguntar". Gravar a segunda como a primeira congelaria a
    resposta errada por um mês.
    """
    bruto = dou.baixar(
        url_da_consulta(nome, mes_saida),
        usar_cache=usar_cache,
        validade_horas=VALIDADE_HORAS,
        dir_cache=DIR_CACHE,
        aceitar_gzip=True,
        pausa_segundos=PAUSA_SEGUNDOS,
    )
    if not bruto:
        return None
    try:
        dados = json.loads(bruto)
    except ValueError:
        return None
    if not isinstance(dados, dict) or "gazettes" not in dados:
        return None
    return dados["gazettes"]


# ------------------------------------------------- é mesmo o nome desta pessoa?

# Palavras que PODEM ladear um nome sem que aquilo seja outro nome. Tudo o mais
# que for alfabético ao lado do nome é tratado como continuação do nome — e o
# caso é descartado.
_PODEM_LADEAR = frozenset("""
A AO AOS AS DA DAS DE DO DOS E EM NA NAS NO NOS O OS PARA PELO PELA POR
SR SRA SENHOR SENHORA DR DRA
CANDIDATO CANDIDATA CANDIDATOS SERVIDOR SERVIDORA SERVIDORES NOME NOMES
CARGO CARGOS CLASSIFICACAO CLASS CPF RG MATRICULA INSCRICAO ORDEM
NOMEAR NOMEIA NOMEADO NOMEADA NOMEAR-SE POSSE EMPOSSADO EMPOSSADA
CONVOCAR CONVOCA CONVOCADO CONVOCADA ADMITIR ADMITIDO ADMITIDA
PUBLICO PUBLICA CONCURSO SEGUE SEGUEM SEGUINTE SEGUINTES INTERESSADO
""".split())

# Cargos que APARECEM COLADOS ao nome nas tabelas de nomeação — "CARLOS MOACYR
# FERREIRA NETO PROCURADOR I1 PGM". Sem eles, a tabela de posse do próprio ato é
# lida como se o cargo fosse mais um sobrenome, e o ato é descartado.
#
# A lista é curta de propósito e cobre o que este observatório encontra: quem sai
# da CGU vai para carreira de fisco, controle, jurídico ou gestão. Cargo novo que
# não estiver aqui não gera erro — gera silêncio, e o caso vai para a pauta.
_CARGOS = frozenset("""
AUDITOR AUDITORA AUDITORES FISCAL FISCAIS PROCURADOR PROCURADORA ANALISTA
TECNICO TECNICA ASSISTENTE AGENTE ESPECIALISTA CONTADOR CONTROLADOR
ADVOGADO ADVOGADA DEFENSOR DEFENSORA JUIZ PROMOTOR INSPETOR
ADMINISTRADOR ECONOMISTA ENGENHEIRO PROFESSOR MEDICO
TRIBUTARIO TRIBUTARIA MUNICIPAL ESTADUAL FEDERAL RECEITA RENDAS
CONTROLE EXTERNO INTERNO GESTAO FAZENDA TESOURO ERARIO
""".split())

_PODEM_LADEAR = _PODEM_LADEAR | _CARGOS

_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9.\-/]*")


def _vizinho_antes(texto: str, posicao: int) -> str:
    achados = _TOKEN.findall(texto[:posicao])
    return achados[-1] if achados else ""


def _vizinho_depois(texto: str, posicao: int) -> str:
    achado = _TOKEN.search(texto[posicao:])
    return achado.group(0) if achado else ""


def ocorrencias_isoladas(trecho: str, nome: str) -> list[int]:
    """
    O nome aparece no trecho como um nome INTEIRO, não dentro de um maior.

    Esta é a mesma armadilha que a `dou.cita_nome` tem e que a D25 mandou parar
    de usar como porta de entrada, e nos diários ela é pior, porque metade do que
    se acha é lista de candidatos em ordem alfabética — onde nomes ficam colados
    uns nos outros. Casos reais desta base:

        "LUANA CAMILA PINHEIRO JUCA"        contém  CAMILA PINHEIRO
        "CAMILA PINHEIRO FEITOSA"           contém  CAMILA PINHEIRO
        "SILVIO LUCIO PEREIRA CARDOSO"      contém  LUCIO PEREIRA CARDOSO

    A regra: o caractere colado ao nome não pode ser letra, e a PALAVRA vizinha,
    de cada lado, ou não é alfabética (é número, código, CPF mascarado, sinal de
    pontuação) ou está em `_PODEM_LADEAR`. Qualquer outra palavra alfabética
    vizinha é tratada como pedaço de um nome maior.

    Isso derruba caso legítimo — "[...] FLAVIA MARIA RIBEIRO CANTAL ALINNE
    PATRICIA DE ANDRADE CARVALHO E SILVA* 6º" é uma lista de nomeação de verdade
    e cai, porque o nome anterior encosta no dela. É o lado certo para errar:
    o caso vai para a pauta humana com o trecho, em vez de virar afirmação.

    Devolve as POSIÇÕES das ocorrências boas no texto normalizado, e não um
    booleano, porque quem chama precisa olhar a vizinhança de cada uma: a
    fórmula de nomeação vale se estiver perto DAQUELE nome, não em qualquer
    lugar do trecho (ver `parece_nomeacao`).
    """
    alvo = normalizar(nome)
    texto = normalizar(trecho)
    if not alvo:
        return []
    posicoes = []
    for achado in re.finditer(re.escape(alvo), texto):
        inicio, fim = achado.start(), achado.end()
        if inicio > 0 and texto[inicio - 1].isalpha():
            continue
        if fim < len(texto) and texto[fim].isalpha():
            continue
        antes = _vizinho_antes(texto, inicio)
        depois = _vizinho_depois(texto, fim)
        if antes.isalpha() and len(antes) > 1 and antes not in _PODEM_LADEAR:
            continue
        if depois.isalpha() and len(depois) > 1 and depois not in _PODEM_LADEAR:
            continue
        posicoes.append(inicio)
    return posicoes


# ---------------------------------------------------- o ato é de ENTRADA mesmo?

# O que caracteriza entrada em cargo.
#
# `CONVOCA...` entra, e é o caso a entender: a convocação de aprovado é o ato que
# o município publica ANTES da posse, e é o único que existe para LEONARDO
# TOIOMOTO — Paulínia o convocou em 19/05, 05/06 e 25/06 de 2025, sempre como 13º
# do concurso nº 02/2021 para AUDITOR FISCAL TRIBUTÁRIO, com exame médico
# admissional, e ele saiu da CGU na competência 05/2025.
#
# CONVOCAÇÃO NÃO É POSSE, e o observatório não finge que seja: o destino é
# "indício com fonte, não fato apurado" desde sempre, e o selo leva ao diário
# para quem quiser conferir. A convocação nominal, para cargo determinado, no
# mês da saída, é evidência ao menos tão forte quanto a marca azul do ranking,
# que já publica — tratá-la como menos seria incoerente.
_ENTRADA = re.compile(
    r"\bNOMEAR\b|\bNOMEIA\b|\bNOMEAD[OA]S?\b|\bNOMEACAO\b|\bNOMEACOES\b"
    r"|\bPOSSE\b|\bEMPOSSAD[OA]S?\b|\bCONVOCA\w*\b|\bADMITID[OA]S?\b"
)

# O que denuncia que aquele trecho NÃO é ato de entrada, mesmo contendo as
# palavras acima. Cada um destes apareceu na sondagem:
#   - resultado/classificação de prova, que é o mais comum de todos
#   - exoneração e vacância, que são saída, não entrada
#   - licitação, contrato, licença médica, processo judicial
_NAO_E_ENTRADA = re.compile(
    r"\bRESULTADO\b|\bCLASSIFICACAO FINAL\b|\bGABARITO\b|\bHETEROIDENTIFICACAO\b"
    r"|\bNOTA FINAL\b|\bREPROVAD[OA]\b|\bAUSENTE\b|\bFALTOSO\b|\bCADASTRO RESERVA\b"
    r"|\bEXONER\w*\b|\bVACANCIA\b|\bDEMISS\w*\b|\bAPOSENTAD\w*\b"
    r"|\bLICITACAO\b|\bDISPENSA DE LICITACAO\b|\bCONTRATO\b|\bLICENCA MEDICA\b"
)

# A Câmara Municipal publica no MESMO diário da Prefeitura. Quando o ato é do
# Legislativo, o território deixa de identificar o órgão — "Prefeitura de Maceió"
# seria errado para quem foi ser Procurador Legislativo da Câmara de lá. Sem
# forma de separar com segurança, o caso vai para a pauta.
_LEGISLATIVO = re.compile(
    r"\bCAMARA MUNICIPAL\b|\bPODER LEGISLATIVO\b|\bLEGISLATIV[OA]\b|\bVEREADOR\w*\b"
)


# A vizinhança que conta, em caracteres, de cada lado do nome. O trecho inteiro
# tem 500 e não serve de unidade: o ato de nomeação de CARLOS MOACYR FERREIRA
# NETO em Santos traz, 300 caracteres adiante, a vaga "decorrente da
# aposentadoria" de outra pessoa — e o veto global descartava o ato inteiro por
# causa daquela palavra. O que vale é o que está ao redor DAQUELE nome.
JANELA_DA_FORMULA = 200


def parece_nomeacao(trecho: str, nome: str) -> bool:
    """
    Alguma ocorrência isolada do nome está dentro de um ato de ENTRADA em cargo.

    "Dentro de" é literal: a palavra que caracteriza entrada (`_ENTRADA`) tem de
    estar a até `JANELA_DA_FORMULA` caracteres do nome, e nenhuma palavra que
    desqualifica (`_NAO_E_ENTRADA`) pode estar na mesma vizinhança. Fora dessa
    janela o texto é outro ato — diário oficial é uma pilha de atos coladas.
    """
    texto = normalizar(trecho)
    tamanho = len(normalizar(nome))
    for posicao in ocorrencias_isoladas(trecho, nome):
        inicio = max(0, posicao - JANELA_DA_FORMULA)
        fim = posicao + tamanho + JANELA_DA_FORMULA
        vizinhanca = texto[inicio:fim]
        deslocamento = posicao - inicio
        perto_entrada = _mais_perto(_ENTRADA, vizinhanca, deslocamento, tamanho)
        perto_veto = _mais_perto(_NAO_E_ENTRADA, vizinhanca, deslocamento, tamanho)
        if perto_entrada is not None and perto_entrada < perto_veto:
            return True
    return False


def _mais_perto(padrao: re.Pattern, vizinhanca: str, nome_em: int, nome_tam: int) -> float:
    """
    Distância, em caracteres, da palavra mais próxima do nome. `inf` se não há.

    Existe porque a palavra que desqualifica costuma aparecer DENTRO de um ato de
    nomeação legítimo, e longe do nome: "nomeia [...] CARLOS MOACYR FERREIRA
    NETO, para exercer o cargo de Procurador [...] em vaga decorrente da
    APOSENTADORIA de outra pessoa". Vetar por presença descarta o ato inteiro;
    vence quem estiver mais perto do nome, que é do que o ato fala.
    """
    melhor = float("inf")
    for achado in padrao.finditer(vizinhanca):
        if achado.end() <= nome_em:
            distancia = nome_em - achado.end()
        elif achado.start() >= nome_em + nome_tam:
            distancia = achado.start() - (nome_em + nome_tam)
        else:
            distancia = 0
        melhor = min(melhor, distancia)
    return melhor


def e_legislativo(trecho: str) -> bool:
    """O ato é do Legislativo municipal, e aí o território não diz o órgão."""
    return bool(_LEGISLATIVO.search(normalizar(trecho)))


# ------------------------------------------------------ território -> órgão

def _municipio_do_canonico(canonico: str) -> str:
    """`Prefeitura do Rio de Janeiro` -> `RIO DE JANEIRO`."""
    achado = re.match(r"Prefeitura d[eoa]s? (.+)$", canonico)
    return normalizar(achado.group(1)) if achado else ""


# O catálogo manda: `Prefeitura DO Rio de Janeiro` e `Prefeitura DE São Paulo`
# não seguem o mesmo molde, e inventar o artigo criaria dois destinos onde há um.
# Este índice é derivado de `ranking.ORGAO_POR_ROTULO`, que é a fonte única dos
# nomes de órgão do observatório (D24) — não há segunda lista para desencontrar.
ORGAO_POR_MUNICIPIO = {
    municipio: canonico
    for canonico in set(ranking.ORGAO_POR_ROTULO.values())
    for municipio in [_municipio_do_canonico(canonico)]
    if municipio
}

# Territórios em que o diário serve a MUITOS órgãos e por isso não identifica
# nenhum. O DF é o caso: um só diário para GDF, TCDF, Câmara Legislativa,
# Defensoria e Polícia Civil.
UFS_SEM_TERRITORIO_UTIL = frozenset({"DF"})


def orgao_do_territorio(territorio: str, uf: str) -> str:
    """
    O órgão canônico de um diário municipal. `""` quando não dá para afirmar.

    Prefere SEMPRE o nome que o catálogo já usa; só constrói `Prefeitura de X`
    quando o município é novo para o observatório. Construir é seguro porque o
    molde é o mesmo do catálogo inteiro e o nome do município vem do IBGE, via
    Querido Diário — mas o catálogo vence, senão "Prefeitura de Rio de Janeiro"
    apareceria ao lado de "Prefeitura do Rio de Janeiro".
    """
    if not territorio or (uf or "").upper() in UFS_SEM_TERRITORIO_UTIL:
        return ""
    conhecido = ORGAO_POR_MUNICIPIO.get(normalizar(territorio))
    return conhecido or f"Prefeitura de {territorio}"


# --------------------------------------------------------------- a decisão

def atos_da_pessoa(nome: str, gazetas: list[dict]) -> list[dict]:
    """
    Os diários da busca que trazem um ato de ENTRADA desta pessoa, com o órgão.

    Cada item traz o trecho que sustenta a afirmação, para ir ao relatório e à
    conferência humana. Diário que não passa em `nome_isolado` ou em
    `parece_nomeacao` simplesmente não entra: o silêncio é a resposta certa.
    """
    achados = []
    for gazeta in gazetas or []:
        trechos = [" ".join((t or "").split()) for t in (gazeta.get("excerpts") or [])]
        bons = [t for t in trechos if parece_nomeacao(t, nome)]
        if not bons:
            continue
        if any(e_legislativo(t) for t in bons):
            continue
        orgao = orgao_do_territorio(gazeta.get("territory_name", ""),
                                    gazeta.get("state_code", ""))
        if not orgao:
            continue
        achados.append({
            "orgao": orgao,
            "data": gazeta.get("date", ""),
            "territorio": f"{gazeta.get('territory_name', '')}/{gazeta.get('state_code', '')}",
            # O PDF é o documento oficial e é o que se manda alguém ler; o `.txt`
            # é a extração que o Querido Diário faz para indexar.
            "url": gazeta.get("url") or gazeta.get("txt_url", ""),
            "trecho": bons[0][:400],
        })
    return achados


def destino_da_pessoa(nome: str, mes_saida: str, gazetas: list[dict] | None) -> dict:
    """
    O destino que os diários municipais sustentam — ou a razão de não haver um.

    `decisao`:
      SEM_DIARIO      nenhum diário municipal com esta pessoa na janela
      SEM_ATO         há diário, mas nenhum é ato de entrada em cargo desta
                      pessoa (o mais comum de longe: lista de aprovados, homônimo
                      em outra cidade, licitação)
      UNICO_DIARIO    um município só publicou ato de entrada -> vai à tela
      VARIOS_DIARIOS  mais de um município -> pauta humana, com os trechos

    NÃO se exige que o órgão esteja entre os candidatos do ranking, e a razão é
    um caso concreto: CARLOS MOACYR FERREIRA NETO foi nomeado Procurador em
    SANTOS (ato explícito, 07/03/2025, saída 05/2025), e Santos NÃO está na ficha
    dele no ranking. Pior — São Paulo ESTÁ, e é onde aparecem uma licença médica
    e um despacho de posse dele. Exigir o cruzamento trocaria um ato de nomeação
    por um registro administrativo, e publicaria o município errado.

    O cruzamento continua sendo registrado (`cruza_ranking`), porque quando ele
    acontece é confirmação de duas fontes independentes — mas ele não é porteiro.
    """
    resposta = {
        "decisao": "SEM_DIARIO",
        "orgao": "",
        "atos": [],
        "url": url_da_consulta(nome, mes_saida),
    }
    if gazetas is None:
        resposta["decisao"] = "FALHA_NA_CONSULTA"
        return resposta

    atos = atos_da_pessoa(nome, gazetas)
    resposta["atos"] = atos
    if not gazetas:
        return resposta
    if not atos:
        resposta["decisao"] = "SEM_ATO"
        return resposta

    orgaos = sorted({a["orgao"] for a in atos})
    if len(orgaos) == 1:
        resposta["decisao"] = "UNICO_DIARIO"
        resposta["orgao"] = orgaos[0]
        return resposta

    resposta["decisao"] = "VARIOS_DIARIOS"
    return resposta
