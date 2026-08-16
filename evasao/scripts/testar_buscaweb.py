#!/usr/bin/env python3
"""
Teste de regressão da busca web. Sem rede, sem chave, sem dependência.

    python testar_buscaweb.py     # 0 = tudo certo

Todo título e resumo aqui foi COPIADO de um resultado real da sondagem de
16/08/2026. Antes de mexer no catálogo de domínios ou nos padrões de posse de
`buscaweb.py`, rode isto; depois de mexer, rode de novo.

Roda sem chave de propósito: a etapa inteira é opcional, e o teste tem de passar
numa máquina que nunca configurou `.env` — inclusive no CI, quando o segredo não
estiver disponível.
"""

from __future__ import annotations

import sys

import buscaweb

# ------------------------------------------------------ domínio -> órgão
DOMINIO = [
    ("o TCDF tem domínio próprio, e é o caso que motivou a fonte",
     "https://www2.tc.df.gov.br/tcdf-da-posse-a-novos-servidores-2/",
     "Tribunal de Contas do Distrito Federal"),
    ("família TRT reproduz a forma que o catálogo do ranking usa",
     "https://www.trt4.jus.br/portais/trt4/documento", "Tribunal Regional do Trabalho da 4ª Região"),
    ("família TCE estadual, idem",
     "https://www.tce.sp.gov.br/sala-imprensa/quem-e-quem/wagner-campos-rosario",
     "Tribunal de Contas do Estado de São Paulo"),
    ("o TCM de São Paulo",
     "https://portal.tcm.sp.gov.br/Management/GestaoPublicacao/DocumentoId",
     "Tribunal de Contas do Município de São Paulo"),
    ("município conhecido pelo catálogo do ranking",
     "https://www.aracaju.se.gov.br/userfiles/edital.pdf", "Prefeitura de Aracaju"),
    ("a Defensoria do DF, que o ranking não conhecia",
     "https://www.defensoria.df.gov.br/edicao-1798", "Defensoria Pública do Distrito Federal"),
    # O DOE de um estado publica ato de TODOS os órgãos dele: achar o nome ali
    # não diz se o ato é da SEFAZ, da PGE ou da Polícia Civil. É a mesma razão
    # pela qual o DODF ficou fora do `diarios.py`.
    ("diário oficial estadual NÃO identifica órgão",
     "https://imagens.seplag.ce.gov.br/PDF/20221228/do20221228p01.pdf", ""),
    ("...nem a imprensa oficial",
     "https://diariooficial.imprensaoficial.com.br/x", ""),
    ("...nem o DODF", "https://www.dodf.df.gov.br/dodf/materia/visualizar?co_data=1", ""),
    ("...nem agregador de diário", "https://www.jusbrasil.com.br/diarios/1", ""),
    ("...nem banca de concurso", "https://cdn.cebraspe.org.br/concursos/edital.pdf", ""),
    # O sítio da CGU é o órgão de ORIGEM: achar a pessoa lá é o esperado.
    ("o sítio da própria CGU não é destino",
     "https://basedeconhecimento.cgu.gov.br/items/abc", ""),
    ("domínio fora do catálogo não vira destino",
     "https://www.orgaodesconhecido.org.br/x", ""),
    ("rede social tampouco", "https://br.linkedin.com/in/fulano", ""),
]

# ------------------------------------------------------ é POSSE ou é concurso?
POSSE_TCDF = ("TCDF dá posse a novos servidores | Auditores de Controle Externo: "
              "Alinne Patrícia de Andrade Carvalho e Silva. Carlos Alexandre Alves "
              "da Cunha. Fabrício Resende Naves. Natalia ...")
NOMEACAO_TCM = ("DOCSP - Diário Oficial Cidade de São Paulo - 117864005 | NOMEAR "
                "LEONARDO TOIOMOTO, de acordo com o disposto nos artigos 10 e 15, "
                "item II, da Lei Municipal nº 8.989/79, por ter sido aprovado em ...")
POSSE_TCESP = ("Wagner de Campos Rosário toma posse administrativa como novo "
               "Conselheiro | 26/09/2025 – SÃO PAULO – Wagner de Campos Rosário é "
               "empossado como o novo Conselheiro")
# O ruído dominante: o nome numa lista de classificação de concurso que a pessoa
# apenas prestou. VICTOR aparece assim em Aracaju E no Ceará.
LISTA_ARACAJU = ("estado de sergipe | Silva / 10004949, Victor Gabriel Carvalho Santos "
                 "Souza / 10008062, Vinicius Felippe Feitosa Armando. 2.1.2 CARGO 2: "
                 "AUDITOR DE TRIBUTOS ... resultado da classificação")
LISTA_NOTAS = ("resultado final | 10000122, Thiago Santos Braga, 126, 30.41 / "
               "10000333, Tiago Dias Sobrinho, nota final")

POSSE = [
    ("posse coletiva noticiada pelo órgão", POSSE_TCDF,
     "ALINNE PATRICIA DE ANDRADE CARVALHO E SILVA", True),
    ("ato de nomeação em diário", NOMEACAO_TCM, "LEONARDO TOIOMOTO", True),
    ("posse noticiada, com o verbo empossar", POSSE_TCESP,
     "WAGNER DE CAMPOS ROSARIO", True),
    ("lista de classificação de concurso NÃO é posse", LISTA_ARACAJU,
     "VICTOR GABRIEL CARVALHO SANTOS SOUZA", False),
    ("lista de notas tampouco", LISTA_NOTAS, "THIAGO SANTOS BRAGA", False),
    ("nome ausente do texto não casa", POSSE_TCDF, "JOAO DA SILVA", False),
]

# ------------------------------------------------------------------ as datas
DATAS = [
    ("data do Google em inglês", "Mar 24, 2025", "202503"),
    ("outro mês", "Jan 15, 2025", "202501"),
    ("só o ano, quando é o que há", "2025", "202501"),
    ("sem data devolve vazio", "", ""),
]

# A janela separa o destino DESTA saída de um emprego posterior: ALINNE aparece
# como analista ATIVA no Senado em 2026, o que é verdade e é outro movimento.
JANELA = [
    ("posse três meses antes da saída cabe", "202503", "202505", True),
    ("posse um ano e meio antes não cabe", "202311", "202505", False),
    ("registro do ano seguinte não cabe", "202606", "202505", False),
    ("resultado sem data passa: exigi-la descartaria metade do sinal",
     "", "202505", True),
]


def _resultado(url, titulo, resumo="", data=""):
    return {"url": url, "titulo": titulo, "resumo": resumo, "data": data}


DECISAO = [
    (
        "um órgão com posse: é o destino",
        "ALINNE PATRICIA DE ANDRADE CARVALHO E SILVA", "202505",
        [_resultado("https://www2.tc.df.gov.br/tcdf-da-posse-a-novos-servidores-2/",
                    POSSE_TCDF, "", "Mar 24, 2025")],
        ("UNICO_WEB", "Tribunal de Contas do Distrito Federal"),
    ),
    (
        "lista de concurso não vira destino, nem em domínio oficial",
        "VICTOR GABRIEL CARVALHO SANTOS SOUZA", "202307",
        [_resultado("https://www.aracaju.se.gov.br/edital.pdf", LISTA_ARACAJU)],
        ("SEM_ACHADO", ""),
    ),
    (
        "dois órgãos com posse: pauta",
        "FULANO DE TAL", "202505",
        [_resultado("https://www2.tc.df.gov.br/x", "posse de FULANO DE TAL como Auditor"),
         _resultado("https://www.trt4.jus.br/y", "nomear FULANO DE TAL, aprovado")],
        ("VARIOS_WEB", ""),
    ),
    (
        # Sem chave, `buscar` devolve `None`. É o estado normal de quem clonou o
        # repositório e não configurou nada.
        "sem busca (sem chave, ou consulta que falhou) não afirma nada",
        "FULANO DE TAL", "202505", None,
        ("SEM_BUSCA", ""),
    ),
    (
        "busca que respondeu e não trouxe nada de útil",
        "FULANO DE TAL", "202505",
        [_resultado("https://br.linkedin.com/in/fulano", "Fulano de Tal - LinkedIn")],
        ("SEM_ACHADO", ""),
    ),
]


def main() -> int:
    falhas = 0

    print("— o domínio identifica o órgão? —")
    for descricao, url, esperado in DOMINIO:
        obtido = buscaweb.orgao_do_dominio(url)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— o texto fala de posse desta pessoa? —")
    for descricao, texto, nome, esperado in POSSE:
        obtido = buscaweb.fala_de_posse(texto, nome)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    print("— a data do resultado —")
    for descricao, bruta, esperado in DATAS:
        obtido = buscaweb.competencia_do_resultado(bruta)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— a janela em torno da saída —")
    for descricao, competencia, mes, esperado in JANELA:
        obtido = buscaweb.na_janela(competencia, mes)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    print("— decisão: o que vira destino e o que vira pauta —")
    for descricao, nome, mes, resultados, (decisao, orgao) in DECISAO:
        obtido = buscaweb.destino_da_pessoa(nome, mes, resultados)
        ok = obtido["decisao"] == decisao and obtido["orgao"] == orgao
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {(decisao, orgao)}, "
                  f"obtido {(obtido['decisao'], obtido['orgao'])}")

    total = len(DOMINIO) + len(POSSE) + len(DATAS) + len(JANELA) + len(DECISAO)
    print()
    print(f"{total - falhas} de {total} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
