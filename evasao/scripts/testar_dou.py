#!/usr/bin/env python3
"""
Teste de regressão da classificação de atos do DOU. Sem rede, sem dependência.

    python testar_dou.py     # 0 = tudo certo

Cada caso aqui é um erro que já aconteceu de verdade neste projeto e custou
tempo para ser achado, porque nenhum deles quebra nada: produzem um site
plausível e errado sobre pessoa real e nomeada. Antes de mexer nos padrões de
`dou.py`, rode isto; depois de mexer, rode de novo.
"""

from __future__ import annotations

import csv
import html
import re
import sys
from pathlib import Path

import dou

RAIZ = Path(__file__).resolve().parent.parent
ARQ_SAIDAS = RAIZ / "data" / "saidas_dou.csv"
DIR_ATOS = RAIZ / "data" / "saidas_dou"

CARGO = "Auditor Federal de Financas e Controle"

CLASSIFICACAO = [
    (
        "exoneração de cargo comissionado NÃO é saída da CGU",
        f"EXONERAR JOAO DA SILVA, {CARGO}, do Cargo Comissionado Executivo de "
        f"Chefe de Setor, codigo CCE 1.02",
        None,
    ),
    (
        "exoneração do cargo efetivo é saída",
        f"EXONERAR, a pedido, JOAO DA SILVA do cargo de {CARGO} da Controladoria-Geral da Uniao",
        "exoneracao",
    ),
    (
        "o DOU não escreve 'vacância': escreve 'declarar vago ... posse em outro cargo'",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA, "
        f"por motivo de posse em outro cargo inacumulavel",
        "vacancia",
    ),
    (
        "aposentadoria que também diz 'declarar vago' não pode ser engolida "
        "(tipo descartado faz continue, nunca return)",
        f"Conceder aposentadoria voluntaria ao servidor JOAO DA SILVA, ocupante do cargo "
        f"de {CARGO}, e declarar vago o referido cargo",
        "aposentadoria",
    ),
    (
        "exoneração a pedido diz 'ficando vago' — não é vacância",
        f"EXONERAR, a pedido, JOAO DA SILVA do cargo de {CARGO}, ficando vago o cargo "
        f"que atualmente ocupa",
        "exoneracao",
    ),
    (
        "falecimento",
        f"Declarar vago, por motivo de falecimento, o cargo de {CARGO} ocupado por JOAO DA SILVA",
        "falecimento",
    ),
    (
        "concessão de pensão NÃO é saída: o ato é sobre o pensionista, sai muito "
        "depois do óbito, e o instituidor pode ser aposentado ou de outro cargo",
        f"Art. 1o Conceder pensao vitalicia a MARIA DE SOUZA, na qualidade de conjuge "
        f"do ex-servidor JOAO DA SILVA, ocupante do cargo de {CARGO}, Classe S, Padrao V, "
        f"matricula SIAPE no 1538014, falecido em atividade, em 16/02/2025",
        None,
    ),
    (
        "pensão temporária, mesma coisa",
        f"Art. 1o Conceder pensao temporaria, pelo periodo de quatro meses, a LUISA DE SOUZA, "
        f"na qualidade de filha do ex-servidor JOAO DA SILVA, ocupante do cargo de {CARGO}",
        None,
    ),
]

DESTINO = [
    (
        "nomeação para cargo efetivo é destino",
        "RESOLVE: NOMEAR JOAO DA SILVA, aprovado no concurso publico, para o cargo de Analista",
        True,
    ),
    (
        "nomeação para cargo comissionado NÃO é destino",
        "RESOLVE: NOMEAR JOAO DA SILVA para exercer o Cargo Comissionado Executivo, CCE 1.07",
        False,
    ),
    (
        "'declarar vago' é o emprego ANTERIOR liberando a pessoa, nunca destino",
        "Declarar vago o cargo ocupado por JOAO DA SILVA por posse em outro cargo",
        False,
    ),
    (
        "tabela de resultado: constar da lista de classificação não é ser nomeado",
        "RESULTADO: NOMEAR ... "
        + "".join(
            f"1002{i:04d}, FULANO DE TAL LETRA {chr(65 + i)}, {60 + i}.00 / " for i in range(8)
        )
        + "10039178, JOAO DA SILVA, 197.03 / ",
        False,
    ),
    (
        "lista de nomeação legítima é destino, mesmo com o nome longe do verbo",
        "RESOLVE: NOMEAR os candidatos aprovados no concurso: "
        + ("FULANO BELTRANO DE TAL / " * 60)
        + "JOAO DA SILVA",
        True,
    ),
    (
        "estar CLASSIFICADO (nome seguido de nota) não é ser nomeado",
        "RESOLVE: NOMEAR ... 81 10000591 JOAO DA SILVA 346.35 9 PCD 82 10005595 MYLLENA SOUZA 344.10",
        False,
    ),
    (
        "nome cercado de marcação de cota é lista de classificação",
        "NOMEAR ... CLASSIFICACAO: 8 (AMPLA) JULIANA COSTA 10 (AMPLA) JOAO DA SILVA 14 (AMPLA)",
        False,
    ),
    (
        "lista de nomeação com matrícula e lotação É destino",
        "RESOLVE: NOMEAR ... 322 HENRIQUE FRANCO 388207846 PREVIC - BRASILIA/DF "
        "323 JOAO DA SILVA 388260521 DRF - RIO BRANCO/AC",
        True,
    ),
    (
        "'vago em decorrência da posse de <a pessoa>' é o emprego ANTERIOR, não destino",
        "Declarar vago o cargo de Tecnico Judiciario, em decorrencia da posse de "
        "JOAO DA SILVA em outro cargo publico inacumulavel",
        False,
    ),
    (
        "'nomear <a pessoa> em cargo vago decorrente da posse de OUTRA pessoa' É destino",
        "RESOLVE: NOMEAR JOAO DA SILVA, em cargo vago decorrente da posse de "
        "MARIA APARECIDA SOUZA em outro cargo inacumulavel",
        True,
    ),
    (
        "cargo 'anteriormente ocupado por <a pessoa>' — é quem SAIU, não quem entra",
        "NOMEAR MATEUS GOMES, 6o lugar, em vaga originaria da vacancia do cargo "
        "anteriormente ocupado por JOAO DA SILVA",
        False,
    ),
    (
        "lista de DESISTENTES da nomeação não é destino — o ato diz que a pessoa não foi",
        "Considerando os pedidos de DESISTENCIA de nomeacao ou posse formulados pelos "
        "candidatos DEBORAH COSTA FUSCALDI, JOAO DA SILVA, LEONARDO AZEVEDO, resolve NOMEAR",
        False,
    ),
    (
        "'em vaga decorrente da vacância do cargo de <a pessoa>' — é quem vagou",
        "NOMEAR IOLY FREITAS SANTANA, em vaga decorrente da vacancia do cargo de "
        "JOAO DA SILVA",
        False,
    ),
    (
        "'tornar sem efeito a nomeação de <a pessoa>' diz o OPOSTO de ter ido",
        "TORNAR SEM EFEITO A NOMEACAO DE JOAO DA SILVA para exercer o cargo efetivo de Analista",
        False,
    ),
    (
        "lista de nomeação longa: nome distante do verbo, mas com preâmbulo de nomeação",
        "RESOLVE: NOMEAR, com fundamento no art. 9o da Lei no 8.112, PARA EXERCEREM O CARGO "
        "de Auditor Federal de Controle Externo do quadro deste Tribunal: "
        + ("ADRIANO CERQUEIRA NETTO ARTHUR MOREIRA LIMA ATILA AMORIM " * 6)
        + "JOAO DA SILVA CARLA OLIVEIRA",
        True,
    ),
]

# O `hierarchyStr` começa pelo guarda-chuva, não pelo órgão. "Foi para o Poder
# Judiciário" é verdadeiro e inútil; "foi para a Presidência da República"
# quando na verdade foi para a AGU induz a erro.
ORGAO = [
    ("desce um nível quando o primeiro é um poder",
     "Poder Legislativo/Senado Federal/Diretoria-Geral", "Senado Federal"),
    ("AGU pendura sob a Presidência",
     "Presidência da República/Advocacia-Geral da União/PGF", "Advocacia-Geral da União"),
    ("órgão próprio fica como está",
     "Tribunal de Contas da União/Secretaria-Geral", "Tribunal de Contas da União"),
    ("sem nível seguinte, mantém o que tem", "Poder Judiciário", "Poder Judiciário"),
]

# A página de um ato traz o texto numa div .texto-dou. Página-índice (sumário do
# dia, com várias matérias) não tem essa div — e o fallback antigo entregava a
# página inteira, ~27 mil caracteres de JavaScript, como se fosse o ato.
EXTRACAO = [
    (
        "extrai o texto da div do ato",
        '<html><body><div class="texto-dou"><p>EXONERAR JOAO</p></div><div>rodape</div></body></html>',
        "EXONERAR JOAO",
    ),
    (
        "página sem a div do ato devolve vazio, nunca a página inteira",
        "<html><body><script>window.analytics = 1;</script><div class='materia'>x</div></body></html>",
        "",
    ),
]

# O nome sai do texto do ato e vai para a tela ao lado de "vacância" ou
# "aposentadoria". Errar aqui é afirmar coisa errada sobre pessoa real e
# nomeada, então a régua não é "acerta a maioria": é ZERO nome errado. Não achar
# é resposta aceitável; achar o nome de outra pessoa, não.
NOME_NO_ATO = [
    (
        "vacância: 'ocupado pelo servidor FULANO, matrícula SIAPE'",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor CIRO JONATAS DE SOUZA "
        f"OLIVEIRA, matricula SIAPE no 2576295, Classe S",
        "CIRO JONATAS DE SOUZA OLIVEIRA",
    ),
    (
        "aposentadoria voluntária: 'ao servidor FULANO, ocupante do cargo'",
        f"Conceder aposentadoria voluntaria ao servidor LUIZ CARLOS AKIO MATSUMOTO, "
        f"ocupante do cargo de {CARGO}, Classe S",
        "LUIZ CARLOS AKIO MATSUMOTO",
    ),
    (
        "aposentadoria compulsória: 'o servidor FULANO', sem a preposição",
        f"Aposentar compulsoriamente com proventos proporcionais o servidor JOAO DE DEUS "
        f"SALOMAO BRITO, ocupante do cargo de {CARGO}",
        "JOAO DE DEUS SALOMAO BRITO",
    ),
    (
        "exoneração com preâmbulo longo entre o verbo e o nome",
        f"EXONERAR, a pedido, por motivo de desistencia do estagio probatorio, CELSO ANTONIO "
        f"FERNANDES DE QUEIROZ do cargo de {CARGO} da Controladoria-Geral da Uniao",
        "CELSO ANTONIO FERNANDES DE QUEIROZ",
    ),
    (
        "exoneração de ofício: nome fechado por ', SIAPE no'",
        f"Exonerar, de oficio, por desistencia do estagio probatorio, o servidor EVANDRO "
        f"AMORIM LELIS, SIAPE no 3302689, do cargo de {CARGO}",
        "EVANDRO AMORIM LELIS",
    ),
    (
        "nome em Title Case (29 dos 251 atos escrevem assim)",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor Lucas Jose Silva da "
        f"Silveira, matricula SIAPE no 3021455",
        "Lucas Jose Silva da Silveira",
    ),
    (
        # Portaria 1.872, de 20/07/2026 — erro de digitação do próprio DOU. Com o
        # grupo do cargo sendo opcional, a palavra errada caía DENTRO do nome e o
        # site publicaria "servidoa Gabriel" como nome de gente.
        "erro de digitação do DOU ('servidoa') não vira parte do nome",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidoa GABRIEL ISMAEL "
        f"CARRAZZONE LACATIVA, matricula SIAPE no 3145888",
        "GABRIEL ISMAEL CARRAZZONE LACATIVA",
    ),
    (
        "fórmula desconhecida devolve vazio, nunca um chute",
        "Art. 1o Fica designado o grupo de trabalho de que trata a portaria anterior.",
        "",
    ),
]

MATRICULA = [
    (
        "zero à esquerda: Portal mascara '014****', DOU escreve '149262'",
        "matricula SIAPE no 149262",
        "014****",
        True,
    ),
    (
        "matrícula que realmente diverge elimina homônimo",
        "matricula SIAPE no 2576295",
        "014****",
        False,
    ),
    (
        "ato sem matrícula não decide nada",
        "EXONERAR JOAO DA SILVA do cargo",
        "014****",
        None,
    ),
]


def conferir_nomes_do_corpus() -> tuple[int, str]:
    """
    Refaz a leitura do nome nos atos já arquivados e compara com o SIAPE.

    Não é teste sintético: usa os atos de verdade em `data/saidas_dou/` e o nome
    que a busca por nome já casou com uma pessoa no `data/saidas_dou.csv`. É a
    única maneira honesta de medir um extrator de nome — as fórmulas do DOU
    variam mais do que se consegue imaginar de cabeça, e foi assim que
    apareceram a aposentadoria compulsória, a exoneração de ofício e o
    "servidoa".

    Sem rede: só relê arquivo. Devolve (falhas, resumo). Se os dados não
    estiverem à mão, não falha — apenas avisa que não conferiu.
    """
    if not ARQ_SAIDAS.is_file() or not DIR_ATOS.is_dir():
        return 0, "sem corpus local — conferência do nome não rodou"

    with open(ARQ_SAIDAS, encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.DictReader(fh, delimiter=";"))

    exato = vazio = 0
    divergentes = []
    for linha in linhas:
        arquivo = (linha.get("ATO_SAIDA_ARQUIVO") or "").strip()
        esperado = (linha.get("NOME") or "").strip()
        if not arquivo or not esperado:
            continue
        caminho = DIR_ATOS / arquivo
        if not caminho.is_file():
            continue

        achado = re.search(r'<div class="texto">(.*?)</div>', caminho.read_text(encoding="utf-8"), re.S)
        obtido = dou.nome_do_ato(html.unescape(achado.group(1))) if achado else ""

        if not obtido:
            vazio += 1
        elif dou.normalizar(obtido) == dou.normalizar(esperado):
            exato += 1
        else:
            divergentes.append((esperado, obtido))

    total = exato + vazio + len(divergentes)
    for esperado, obtido in divergentes:
        print(f"        DIVERGE: SIAPE diz {esperado!r}, ato leu {obtido!r}")
    if vazio:
        print(f"        ({vazio} ato(s) sem nome legível — aceitável, não é falha)")

    # Só nome ERRADO é falha. Vazio é a resposta correta para fórmula que
    # ninguém ensinou a ler ainda.
    return len(divergentes), f"{exato} de {total} atos reais com o nome exato"


def main() -> int:
    falhas = 0

    print("— classificação de saída —")
    for descricao, texto, esperado in CLASSIFICACAO:
        obtido = dou.classificar(texto)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— destino —")
    for descricao, texto, esperado in DESTINO:
        obtido = dou.e_ato_de_nomeacao(texto, "JOAO DA SILVA")
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— guarda de homônimo pela matrícula —")
    for descricao, texto, mascara, esperado in MATRICULA:
        obtido = dou.siape_compativel(texto, mascara)
        ok = obtido is esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— nome do órgão de destino —")
    for descricao, hierarquia, esperado in ORGAO:
        obtido = dou.orgao_do_ato({"hierarchyStr": hierarquia})
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— nome lido do próprio ato —")
    for descricao, texto, esperado in NOME_NO_ATO:
        obtido = dou.nome_do_ato(texto)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— nome conferido contra os atos reais já casados com pessoa —")
    falhas_corpus, resumo = conferir_nomes_do_corpus()
    falhas += falhas_corpus
    print(f"  {'ok  ' if not falhas_corpus else 'FALHA'} {resumo}")

    print("— extração do texto do ato —")
    for descricao, pagina, esperado in EXTRACAO:
        obtido = dou.extrair_texto(pagina)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido[:60]!r}")

    total = (
        len(CLASSIFICACAO) + len(DESTINO) + len(MATRICULA) + len(EXTRACAO) + len(ORGAO)
        + len(NOME_NO_ATO) + 1  # +1: a conferência do corpus inteiro conta como uma
    )
    print()
    print(f"{total - falhas} de {total} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
