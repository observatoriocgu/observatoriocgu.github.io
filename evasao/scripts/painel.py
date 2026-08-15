#!/usr/bin/env python3
"""
Derivação do painel a partir dos snapshots mensais do Portal da Transparência.

Este módulo NÃO é executável: é a biblioteca que `construir_painel.py` usa. Ele
não acessa rede e não escreve arquivo — só transforma os snapshots em estruturas.

O que ele resolve, e por quê (números medidos em 14/08/2026 sobre 49 snapshots):

  AFFC != CGU. A carreira é compartilhada: além dos ~1.750 da CGU
  (COD_ORG_LOTACAO = 59000) há ~825 AFFC no Ministério da Fazenda/Economia
  (17600/17000). O recorte é sempre pelo CÓDIGO — o nome do órgão muda de grafia
  entre meses ("Ministério da Economia" -> "MINISTERIO DA FAZENDA", acentos
  somem), e filtrar por nome perderia gente em silêncio.

  Saída = ausência A PARTIR DA ÚLTIMA PRESENÇA, nunca diff par a par (D13).
  Existem 6 "ressurreições" na série: pessoas que somem por 1 a 6 meses e voltam
  (uma delas ausente de 202302 a 202307). Um diff par a par publicaria 6 saídas
  falsas sobre gente que nunca saiu, e mandaria 6 nomes ao crawler à toa. Com a
  regra da última presença elas se dissolvem sozinhas, sem caso especial.

  Unidade se conta pelo CÓDIGO. `UORG_LOTACAO` muda de valor para 1.229 pessoas
  ao longo da série, mas `COD_UORG_LOTACAO` só para 410: a diferença é regrafia
  (34 códigos aparecem sob 38 grafias). O nome é rótulo, o código é identidade.

  UF vem da UNIDADE, não de `UF_EXERCICIO`. O Portal só passou a preencher
  `UF_EXERCICIO` no fim de 2023 — em 202206 são 100% "-1", hoje ainda são 615.
  Usá-lo cru produziria uma explosão fictícia de "auditores por UF" em 2023/2024
  que é só o campo começando a existir. A lotação regional, essa, existe desde o
  primeiro snapshot.

  `DATA_INGRESSO_ORGAO` muta para 6 pessoas em 2.009 — usamos o valor MODAL da
  série, não o do último snapshot.
"""

from __future__ import annotations

import collections
import csv
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SNAPSHOTS = RAIZ / "data" / "historico_transparencia_cgu"
PADRAO_SNAPSHOT = "*_Cadastro_filtrado_AFFC.csv"

COD_ORG_CGU = "59000"

# Código de UORG "sem informação" no Portal. Estável em ~150 linhas/mês (8%) do
# começo ao fim da série — é ausência de dado, não mudança de estrutura.
COD_UORG_DESCONHECIDA = "-99"
COD_UORG_SEDE = "59000000000315"

# Unidades da sede que aparecem com código próprio. Agrupá-las na sede é o que
# torna o gráfico "por unidade" legível: são coordenações e diretorias de
# dentro do prédio de Brasília, não lotações autônomas.
CODS_UORG_SEDE = {
    COD_UORG_SEDE,
    "59000000000330",  # Coordenação-Geral de Gestão de Pessoas
    "59000000000445",  # Coord-Geral Aud Áreas Des Reg e Meio Ambiente
    "59000000000401",  # Dir de Aud de Pol Soc e de Seg Pública
}

UNIDADE_SEDE = "Sede/DF"
UNIDADE_DESCONHECIDA = "Não informada"

# As regionais aparecem ora com a sigla da UF ("- RJ", "- SC"), ora com o nome
# do estado por extenso ("- MINAS GERAIS", "- PARA"). Este de-para fecha as duas
# grafias na mesma unidade.
UF_POR_ESTADO = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA",
    "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS", "MINAS GERAIS": "MG",
    "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE",
    "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}
SIGLAS_UF = set(UF_POR_ESTADO.values())

PADRAO_REGIONAL = re.compile(r"CONTR(?:OLADORIA)?\s+REGIONAL\s+DO\s+ESTADO\s*-\s*(.+)$")

# Colunas do snapshot que sobrevivem ao filtro. As outras 29 são constantes,
# sempre vazias, ou mascaradas — ver §2.2 do PLANO.md.
COLUNAS_ORIGEM = (
    "ID_SERVIDOR_PORTAL",
    "NOME",
    "MATRICULA",
    "CLASSE_CARGO",
    "PADRAO_CARGO",
    "COD_UORG_LOTACAO",
    "UORG_LOTACAO",
    "COD_UORG_EXERCICIO",
    "UORG_EXERCICIO",
    "COD_ORG_EXERCICIO",
    "ORG_EXERCICIO",
    "SITUACAO_VINCULO",
    "UF_EXERCICIO",
    "DATA_INGRESSO_ORGAO",
)

# O cabeçalho do Portal usa `Id_SERVIDOR_PORTAL`; padronizamos em caixa alta.
ORIGEM_NO_CSV = {"ID_SERVIDOR_PORTAL": "Id_SERVIDOR_PORTAL"}

COLUNAS_HISTORICO = ("MES",) + COLUNAS_ORIGEM + ("CONCURSO", "AREA", "UNIDADE", "UF")

SITUACAO_CEDIDO = "ATIVO EM OUTRO ORGAO"
ID_CONCURSO_VETERANO = "VETERANO"
ID_CONCURSO_2021 = "CGU-2021"

SITUACAO_EM_EXERCICIO = "EM EXERCÍCIO"
SITUACAO_SEM_ATO = "SAÍDA SEM ATO IDENTIFICADO"
SITUACAO_MUDOU_ORGAO = "MUDOU DE ÓRGÃO NA CARREIRA"


def normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto or "")
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


def normalizar_unidade(cod: str, nome: str) -> tuple[str, str]:
    """
    (unidade, uf) a partir do código e do nome da UORG de lotação.

    O código manda; o nome só é lido para descobrir de que estado é a regional.
    """
    if cod in CODS_UORG_SEDE:
        return UNIDADE_SEDE, "DF"
    if cod == COD_UORG_DESCONHECIDA or not cod:
        return UNIDADE_DESCONHECIDA, ""

    achado = PADRAO_REGIONAL.match(normalizar(nome))
    if achado:
        sufixo = achado.group(1).strip()
        uf = sufixo if sufixo in SIGLAS_UF else UF_POR_ESTADO.get(sufixo, "")
        if uf:
            return f"CGU-Regional/{uf}", uf

    # Sub-unidades pequenas (divisões, núcleos) sem regional identificável no
    # nome. Não dá para deduzir a que regional pertencem sem inventar, então
    # ficam com o próprio rótulo — são poucas dezenas de linhas em 88 mil.
    return nome.strip() or UNIDADE_DESCONHECIDA, ""


def mes_seguinte(mes: str) -> str:
    ano, m = int(mes[:4]), int(mes[4:])
    m += 1
    if m == 13:
        ano, m = ano + 1, 1
    return f"{ano:04d}{m:02d}"


def _modal(valores: list[str]) -> str:
    """Valor mais frequente, ignorando vazios. Desempate pelo mais antigo."""
    contagem = collections.Counter(v for v in valores if v)
    return contagem.most_common(1)[0][0] if contagem else ""


def carregar(pasta: Path = PASTA_SNAPSHOTS) -> tuple[list[str], dict, dict]:
    """
    Lê os snapshots e devolve (meses, cgu, fora_da_cgu).

    - `cgu[mes][id]`   = dict com as COLUNAS_ORIGEM, só de quem está lotado na CGU
    - `fora[mes][id]`  = nome do órgão, para quem é AFFC mas está lotado alhures

    O segundo existe só para um caso: quem sai do conjunto CGU mas continua na
    carreira em outro órgão. São 3 pessoas em 49 meses, e resolvê-las aqui evita
    3 consultas inúteis ao DOU e 3 "destino desconhecido" no site.
    """
    csv.field_size_limit(10 * 1024 * 1024)

    arquivos = sorted(pasta.glob(PADRAO_SNAPSHOT))
    if not arquivos:
        raise SystemExit(f"Nenhum snapshot {PADRAO_SNAPSHOT} em {pasta}")

    meses: list[str] = []
    cgu: dict[str, dict[str, dict]] = {}
    fora: dict[str, dict[str, str]] = {}

    for arquivo in arquivos:
        mes = arquivo.name[:6]
        meses.append(mes)
        do_mes: dict[str, dict] = {}
        fora_do_mes: dict[str, str] = {}

        with open(arquivo, encoding="utf-8", newline="") as fh:
            for linha in csv.DictReader(fh, delimiter=";"):
                identificador = linha.get("Id_SERVIDOR_PORTAL", "")
                if not identificador:
                    continue
                if linha.get("COD_ORG_LOTACAO") == COD_ORG_CGU:
                    do_mes[identificador] = {
                        coluna: (linha.get(ORIGEM_NO_CSV.get(coluna, coluna)) or "").strip()
                        for coluna in COLUNAS_ORIGEM
                    }
                else:
                    fora_do_mes[identificador] = (linha.get("ORG_LOTACAO") or "").strip()

        cgu[mes] = do_mes
        fora[mes] = fora_do_mes

    return meses, cgu, fora


def _lacunas(meses: list[str]) -> list[str]:
    return [meses[i] for i in range(len(meses) - 1) if mes_seguinte(meses[i]) != meses[i + 1]]


def derivar_pessoas(meses: list[str], cgu: dict, fora: dict) -> list[dict]:
    """
    Uma linha por pessoa que passou pela CGU no período.

    Preenche só o que o SIAPE sabe. Motivo e destino da saída ficam vazios aqui:
    quem os preenche é o `enriquecer_saidas.py`, a partir do DOU.
    """
    ultimo_mes = meses[-1]
    presenca: dict[str, list[str]] = collections.defaultdict(list)
    for mes in meses:
        for identificador in cgu[mes]:
            presenca[identificador].append(mes)

    pessoas = []
    for identificador, meses_presente in presenca.items():
        entrada, ultima = meses_presente[0], meses_presente[-1]
        atual = cgu[ultima][identificador]

        # Valor modal, não o do último snapshot: a data de ingresso muda de
        # valor ao longo da série para 6 pessoas.
        ingresso = _modal([cgu[m][identificador]["DATA_INGRESSO_ORGAO"] for m in meses_presente])

        unidade, uf = normalizar_unidade(atual["COD_UORG_LOTACAO"], atual["UORG_LOTACAO"])
        saiu = ultima != ultimo_mes
        mes_saida = mes_seguinte(ultima) if saiu else ""

        # Ainda é AFFC, mas em outro órgão: a carreira continua, a CGU é que
        # perdeu a pessoa. Não precisa de DOU — o próprio SIAPE diz para onde foi.
        destino_carreira = fora.get(mes_saida, {}).get(identificador, "") if saiu else ""

        if not saiu:
            situacao = SITUACAO_EM_EXERCICIO
        elif destino_carreira:
            situacao = SITUACAO_MUDOU_ORGAO
        else:
            situacao = SITUACAO_SEM_ATO

        pessoas.append(
            {
                "ID_SERVIDOR_PORTAL": identificador,
                "NOME": atual["NOME"],
                "MATRICULA": atual["MATRICULA"],
                "CONCURSO": ID_CONCURSO_VETERANO if entrada == meses[0] else ID_CONCURSO_2021,
                "AREA": "",
                "MES_ENTRADA": entrada,
                "DATA_POSSE": ingresso,
                "INSCRICAO": "",
                "POSICAO_CONCURSO": "",
                "NOTA": "",
                "MODALIDADE": "",
                "UF_VAGA": "",
                "SITUACAO": situacao,
                "UNIDADE": unidade,
                "UF": uf,
                "CEDIDO": "SIM" if atual["SITUACAO_VINCULO"] == SITUACAO_CEDIDO else "NÃO",
                "ORGAO_EXERCICIO": atual["ORG_EXERCICIO"],
                "CLASSE_CARGO": atual["CLASSE_CARGO"],
                "PADRAO_CARGO": atual["PADRAO_CARGO"],
                "MES_SAIDA": mes_saida,
                # Um mês de ausência não é prova: 6 pessoas voltaram depois de
                # sumir. Quem saiu no snapshot mais novo só foi observado ausente
                # uma vez — a saída só vira definitiva quando o mês seguinte
                # confirma.
                "SAIDA_PROVISORIA": "SIM" if mes_saida == ultimo_mes else "",
                "MOTIVO_SAIDA": SITUACAO_MUDOU_ORGAO if destino_carreira else "",
                "FONTE_MOTIVO": "SIAPE" if destino_carreira else "",
                "DATA_SAIDA": "",
                "DATA_PUBLICACAO_SAIDA": "",
                "ATO_SAIDA_TITULO": "",
                "ATO_SAIDA_URL": "",
                "ATO_SAIDA_ARQUIVO": "",
                "ORGAO_DESTINO": destino_carreira,
                "CARGO_DESTINO": "",
                "DATA_DESTINO": "",
                "FONTE_DESTINO": "SIAPE" if destino_carreira else "",
                "URL_DESTINO": "",
                "OBSERVACAO": "",
            }
        )

    pessoas.sort(key=lambda p: (p["MES_ENTRADA"], normalizar(p["NOME"])))
    return pessoas


def gerar_historico(meses: list[str], cgu: dict, pessoas: list[dict]) -> list[dict]:
    """
    A base consolidada (D16): os snapshots empilhados, com competência e coorte.

    `CONCURSO` e `AREA` são atributos da pessoa e ficam repetidos em todas as
    linhas dela. A desnormalização é de propósito: é o que deixa a base usável
    direto pela interface, sem join.
    """
    por_id = {p["ID_SERVIDOR_PORTAL"]: p for p in pessoas}
    linhas = []
    for mes in meses:
        for identificador, origem in cgu[mes].items():
            pessoa = por_id[identificador]
            unidade, uf = normalizar_unidade(
                origem["COD_UORG_LOTACAO"], origem["UORG_LOTACAO"]
            )
            linha = {"MES": mes}
            linha.update(origem)
            linha["CONCURSO"] = pessoa["CONCURSO"]
            linha["AREA"] = pessoa["AREA"]
            linha["UNIDADE"] = unidade
            linha["UF"] = uf
            linhas.append(linha)
    return linhas


def gerar_serie_mensal(meses: list[str], cgu: dict) -> list[dict]:
    """Uma linha por competência: efetivo, entradas, saídas e cedidos."""
    serie = []
    for indice, mes in enumerate(meses):
        atual = set(cgu[mes])
        anterior = set(cgu[meses[indice - 1]]) if indice else set()
        cedidos = sum(
            1 for r in cgu[mes].values() if r["SITUACAO_VINCULO"] == SITUACAO_CEDIDO
        )
        serie.append(
            {
                "MES": mes,
                "EFETIVO": len(atual),
                # No primeiro mês não há "antes", então entradas/saídas ficam
                # vazias em vez de 0 — 1.559 pessoas não "entraram" em 202206.
                "ENTRADAS": "" if not indice else len(atual - anterior),
                "SAIDAS": "" if not indice else len(anterior - atual),
                "CEDIDOS": cedidos,
            }
        )
    return serie


def gerar_alteracoes(meses: list[str], cgu: dict, pessoas: list[dict]) -> dict:
    """
    O log de alterações, agora derivado do diff mensal.

    Substitui o `generate-alteracoes.js`, que reconstruía isso do histórico git
    do `dados.csv` — arqueologia de commits, com a data do commit no lugar da
    data do fato.
    """
    por_id = {p["ID_SERVIDOR_PORTAL"]: p for p in pessoas}
    historico = []

    def por_nome(identificador: str) -> tuple[str, str]:
        """Ordem estável para a diferença entre dois conjuntos.

        `set - set` sai em ordem de hash, e o Python randomiza o hash de string a
        cada processo: sem esta chave o arquivo nascia diferente a cada execução,
        com os mesmos registros embaralhados. Não quebrava nada e não aparecia em
        tela — só produzia ~1.850 linhas de diff falso em todo commit, escondendo
        a alteração de verdade no meio. O id entra como desempate porque nome não
        é chave (D12).
        """
        pessoa = por_id.get(identificador)
        return ((pessoa or {}).get("NOME", ""), identificador)

    for indice in range(1, len(meses)):
        mes, anterior = meses[indice], meses[indice - 1]
        mudancas = []

        for identificador in sorted(set(cgu[anterior]) - set(cgu[mes]), key=por_nome):
            pessoa = por_id[identificador]
            # Só é saída se a pessoa não voltou depois (D13). Quem voltou teve
            # um buraco na série, não uma saída.
            if pessoa["MES_SAIDA"] != mes:
                continue
            mudancas.append(
                {
                    "id": identificador,
                    "nome": pessoa["NOME"],
                    "tipo": "saida",
                    "fromSituacao": SITUACAO_EM_EXERCICIO,
                    "toSituacao": pessoa["SITUACAO"],
                    "orgaoDestino": pessoa["ORGAO_DESTINO"],
                    "unidade": pessoa["UNIDADE"],
                    "concurso": pessoa["CONCURSO"],
                }
            )

        for identificador in sorted(set(cgu[mes]) - set(cgu[anterior]), key=por_nome):
            pessoa = por_id.get(identificador)
            if not pessoa or pessoa["MES_ENTRADA"] != mes:
                continue  # retorno de quem tinha sumido, não entrada nova
            mudancas.append(
                {
                    "id": identificador,
                    "nome": pessoa["NOME"],
                    "tipo": "entrada",
                    "fromSituacao": "",
                    "toSituacao": SITUACAO_EM_EXERCICIO,
                    "orgaoDestino": "",
                    "unidade": pessoa["UNIDADE"],
                    "concurso": pessoa["CONCURSO"],
                }
            )

        if mudancas:
            historico.append(
                {
                    "mes": mes,
                    "data": f"{mes[:4]}-{mes[4:]}-01",
                    "changeCount": len(mudancas),
                    "changes": mudancas,
                }
            )

    historico.reverse()  # mais recente primeiro, como a interface espera
    return {
        "fonte": "Portal da Transparência — Cadastro de Servidores Civis (SIAPE)",
        "primeiroMes": meses[0],
        "ultimoMes": meses[-1],
        "totalChangeCount": sum(h["changeCount"] for h in historico),
        "history": historico,
    }


def diagnosticar(meses: list[str], cgu: dict) -> list[str]:
    """Avisos sobre a série, para o script imprimir antes de gravar."""
    avisos = []
    lacunas = _lacunas(meses)
    if lacunas:
        avisos.append(f"LACUNAS na série depois de: {', '.join(lacunas)}")

    presenca: dict[str, list[int]] = collections.defaultdict(list)
    for indice, mes in enumerate(meses):
        for identificador in cgu[mes]:
            presenca[identificador].append(indice)

    ressurreicoes = sum(
        1 for indices in presenca.values() if indices[-1] - indices[0] + 1 != len(indices)
    )
    if ressurreicoes:
        avisos.append(
            f"{ressurreicoes} pessoa(s) sumiram e voltaram — absorvidas pela regra "
            f"da última presença (D13), não viraram saída"
        )
    return avisos
