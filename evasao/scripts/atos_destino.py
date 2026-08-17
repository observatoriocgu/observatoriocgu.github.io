#!/usr/bin/env python3
"""
O índice dos atos de DESTINO: a nomeação ou posse publicada pelo órgão de chegada.

Este módulo NÃO é executável. Ele é o irmão do `atos.py`, e a diferença entre os
dois é de quem publica o ato e sobre o quê:

  atos.py          a CGU diz que alguém SAIU do quadro
  atos_destino.py  outro órgão diz que alguém TOMOU POSSE lá

POR QUE SÃO DOIS ARQUIVOS, E NÃO UMA COLUNA `TIPO` (D30, 16/08/2026)
--------------------------------------------------------------------
Porque o resumo do site é DERIVADO do índice de saídas: o card "dias sem perder
um Auditor", as saídas recentes, a última competência. Se o ato de nomeação em
outro órgão morasse no mesmo arquivo, toda derivação passaria a depender de
lembrar de filtrar por tipo — e a que esquecesse contaria uma CHEGADA em outro
órgão como uma PERDA da CGU. Com dois arquivos, esse erro não tem como ser
escrito.

Isso não contradiz a D19, que juntou o que estava duplicado: lá era o MESMO ato
em duas pastas, e os dois lugares discordavam sobre qual era a última saída.
Aqui são atos diferentes — um ato da CGU sobre alguém saindo nunca é um ato do
TCU sobre alguém entrando —, e nenhum `URL_TITLE` pode cair nos dois índices.

POR QUE ISTO PASSOU A EXISTIR
-----------------------------
Havia uma assimetria que ninguém decidiu: ela simplesmente aconteceu. O ato de
saída tinha índice, cópia arquivada, tipo classificado e 63 casos de regressão;
o ato de destino tinha uma URL solta numa coluna. E são 130 destinos —
a segunda maior afirmação que o site faz sobre pessoa nomeada.

O incômodo é que a assimetria está INVERTIDA em relação à confiança: motivo é
leitura direta do ato da CGU (95%, sem erro nas conferências); destino é
INFERÊNCIA, com cauda longa de falso positivo. A afirmação menos confiável era a
que tinha o rastro de prova mais fraco — e se o in.gov.br mudasse a URL, a saída
continuaria provada pela cópia local e o destino perderia a única evidência.

Arquivar não custa requisição nova: o ato de destino já é baixado hoje, na mesma
busca por nome do `enriquecer_saidas.py`. Ele era lido, usado e jogado fora.

DE QUEM É O ATO
---------------
Quem decide é o CHAMADOR, e a regra é a da D25: em ato de outro órgão a matrícula
divergente VETA (lá o homônimo é risco real — foi assim que uma lista do
Judiciário virou "destino" de um Auditor). Este módulo só registra o que já foi
decidido; ele não julga identidade.

O ÓRGÃO NÃO VEM DO TEXTO
------------------------
Vem do `hierarchyStr` do resultado da busca, por `dou.orgao_do_ato` — a mesma
ideia do território no `diarios.py` e do domínio no `buscaweb.py`. Guarda-se
também a hierarquia crua, porque o DOU às vezes erra o órgão do ato (visto:
PORTARIA-TCU indexada sob Ministério dos Transportes) e sem ela não há como
conferir à mão de onde saiu o nome publicado.
"""

from __future__ import annotations

import csv
import html as html_mod
import re
from pathlib import Path

import atos
import dou

DIR_DOU = atos.DIR_DOU
ARQ_INDICE = DIR_DOU / "atos_destino.csv"
DIR_ATOS = DIR_DOU / "atos_destino"

# O prefixo do nome do arquivo arquivado e a chave do rótulo em `dou.ROTULOS`.
# Não é um tipo que `dou.classificar` devolva, e portanto nunca vira
# `MOTIVO_SAIDA`: nomeação em outro órgão não é motivo de saída da CGU.
TIPO = "nomeacao"

# A coluna do `por_pessoa.csv` que aponta para a cópia arquivada. Mora aqui, e
# não em `enriquecer_saidas.py`, porque quem a preenche são DOIS scripts — aquele
# e o `arquivar_destinos.py` — e o nome tem de ser o mesmo nos dois.
COLUNA_ARQUIVO = "ATO_DESTINO_ARQUIVO"

COLUNAS = (
    "URL_TITLE",
    "DATA_PUBLICACAO",
    "TITULO",
    # O nome utilizável do órgão, por `dou.orgao_do_ato`. É o que vai à tela.
    "ORGAO_DESTINO",
    # O `hierarchyStr` cru, para conferência à mão quando o DOU erra o órgão.
    "ORGAO_HIERARQUIA",
    # Do SIAPE, não do ato: quem chega aqui já foi casado com uma pessoa.
    "NOME",
    "MATRICULA_SIAPE",
    "ID_SERVIDOR_PORTAL",
    "URL",
    "ARQUIVO",
)

# O título limpo do ato dentro da própria página do in.gov.br. Serve para quem
# chega aqui pela URL (o `arquivar_destinos.py`), sem o resultado da busca —
# a `<title>` da página repete o texto duas vezes e ainda cola " - DOU - ...".
_PADRAO_IDENTIFICA = re.compile(r'class="identifica"[^>]*>(.*?)<', re.S)


def titulo_da_pagina(pagina_html: str) -> str:
    """O título do ato lido da página baixada. Vazio se não achar."""
    achado = _PADRAO_IDENTIFICA.search(pagina_html or "")
    if not achado:
        return ""
    return " ".join(html_mod.unescape(re.sub(r"<[^>]+>", "", achado.group(1))).split())


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


def registrar(
    indice: dict[str, dict],
    resultado: dict,
    texto: str,
    id_servidor: str,
    nome: str,
    pagina_html: str = "",
    orgao_destino: str = "",
    arquivar: bool = True,
) -> dict | None:
    """
    Põe um ato de nomeação no índice e arquiva a cópia dele. `None` se não der.

    `None` só acontece quando o ato não tem `urlTitle` — sem ele não há chave,
    não há URL e não há o que arquivar. Aqui NÃO existe o veto da D18: ele é
    sobre penalidade disciplinar publicada pela CGU, e este índice guarda ato de
    entrada em outro órgão.

    Reescrever um ato já indexado é normal e idempotente. Um mesmo ato nomeia
    várias pessoas de uma vez, e nesse caso a última a ser registrada é a que
    fica no `NOME` — a linha é do ATO, não da pessoa. Quem quer o par pessoa×ato
    lê o `por_pessoa.csv`, que é onde esse grão mora.
    """
    chave = resultado.get("urlTitle") or ""
    if not chave:
        return None

    anterior = indice.get(chave, {})
    linha = {
        "URL_TITLE": chave,
        "DATA_PUBLICACAO": dou.data_iso(resultado) or anterior.get("DATA_PUBLICACAO", ""),
        "TITULO": (
            dou.titulo_do_ato(resultado)
            or titulo_da_pagina(pagina_html)
            or anterior.get("TITULO", "")
        ),
        # `orgao_destino` é o caminho de quem chega pela URL, sem o resultado da
        # busca (o `arquivar_destinos.py`): ali o órgão já foi decidido antes, e
        # está gravado no `por_pessoa.csv`. Nesse caso a hierarquia crua fica
        # VAZIA em vez de ser inventada a partir do órgão — o campo existe para
        # conferir de onde o nome saiu, e preenchê-lo com a própria resposta
        # tiraria dele exatamente essa função.
        "ORGAO_DESTINO": (
            dou.orgao_do_ato(resultado) or orgao_destino or anterior.get("ORGAO_DESTINO", "")
        ),
        "ORGAO_HIERARQUIA": resultado.get("hierarchyStr") or anterior.get("ORGAO_HIERARQUIA", ""),
        "NOME": nome or anterior.get("NOME", ""),
        "MATRICULA_SIAPE": dou.siape_do_ato(texto) or anterior.get("MATRICULA_SIAPE", ""),
        "ID_SERVIDOR_PORTAL": id_servidor or anterior.get("ID_SERVIDOR_PORTAL", ""),
        "URL": dou.BASE_ATO + chave,
    }

    if arquivar and texto:
        linha["ARQUIVO"] = dou.salvar_ato(resultado, TIPO, texto, DIR_ATOS)
    else:
        linha["ARQUIVO"] = anterior.get("ARQUIVO", "") or dou.nome_arquivo(resultado, TIPO)

    indice[chave] = linha
    return linha
