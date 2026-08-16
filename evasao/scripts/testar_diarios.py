#!/usr/bin/env python3
"""
Teste de regressão do crawler de diários municipais. Sem rede, sem dependência.

    python testar_diarios.py     # 0 = tudo certo

Cada trecho aqui foi COPIADO de um diário real que a sondagem de 16/08/2026
devolveu, e cada caso é um erro que aconteceu enquanto a D27 era escrita. Antes
de mexer nos padrões de `diarios.py`, rode isto; depois de mexer, rode de novo.

O que este arquivo NÃO testa é a cobertura da fonte — ela é municipal, e o que
ela alcança e o que ela não alcança está medido no cabeçalho de `diarios.py`.
"""

from __future__ import annotations

import sys

import diarios

# --------------------------------------------------------- trechos de verdade
#
# Santos, 07/03/2025. O ato que motivou a regra "a palavra mais próxima vence":
# ele é uma nomeação inequívoca, e traz "aposentadoria" logo adiante porque é
# assim que se descreve a vaga preenchida. O veto por presença o descartava.
SANTOS = (
    "SANTOS PREFEITO MUNICIPAL PORTARIA Nº 1642-P-DEGEPAT/2025 O PREFEITO MUNICIPAL "
    "DE SANTOS, usando das atribuições que lhe são conferidas por lei, de acordo com "
    "o artigo 20, inciso II, da Lei nº 4623/84, nomeia, após concurso público, "
    "CARLOS MOACYR FERREIRA NETO, para exercer o cargo de Procurador, Nível I, "
    "Referência 1, em vaga decorrente da aposentadoria de OSVALDO PEREIRA DA SILVA"
)

# Paulínia, 19/05/2025. Convocação de aprovado — o ato que o município publica
# antes da posse, e o único que existe para LEONARDO TOIOMOTO.
PAULINIA = (
    "Avenida Prefeito José Lozano Araújo, 1551 – Parque Brasil 500 Paulínia/SP – "
    "CEP 13.141-901 1ª CONVOCAÇÃO CLAS. NOME CPF. CARGO HORÁRIO 12º Daiane Sabino "
    "Russo xxx.573.278-xx AUDITOR FISCAL TRIBUTÁRIO 11h30 13º Leonardo Toiomoto "
    "xxx.718.358-xx AUDITOR FISCAL TRIBUTÁRIO 11h30 Paulínia, 19 de maio de 2025."
)

# São Paulo, 06/03/2025. Licença médica: o nome está lá, e não há ato de entrada.
LICENCA = (
    "COORDENADORIA DE RECURSOS HUMANOS Licença(s) médica(s) concedida(s) ao(s) "
    "servidor(es), de acordo com o Decreto Municipal 64.014/2025: REG.TC NOME "
    "DURAÇÃO A PARTIR 20.383 CARLOS MOACYR FERREIRA NETO 07 18.02.2025 "
    "20.210 ANNE TOBOS MELNIKOFF 05 20.02.2025"
)

# Brasília, 31/01/2025. Resultado de prova — o falso positivo mais comum de
# todos: o nome aparece numa lista com nota e classificação.
RESULTADO = (
    "resultado final na prova objetiva, na seguinte ordem: número de inscrição, "
    "nome do candidato, acertos e nota. 10000534, Thiago Moreira da Silva, 148, "
    "53.09 / 10000122, Thiago Santos Braga, 126, 30.41 / 10000333, Tiago Dias "
    "Sobrinho, 130, 41.02"
)

# São Luís, 07/05/2025. Índice de um diário: o ato é de saída, não de entrada.
EXONERACAO = (
    "SUMÁRIO EXONERAÇÃO DE MARLY VASCONCELOS CORRÊA 3 EXONERAÇÃO DE "
    "MATHEUS KLOTZ BUSCH 3 PORTARIA DE DIÁRIAS 4"
)

# Maceió, 21/08/2024. Concurso da CÂMARA publicado no diário do município: o
# território diria "Prefeitura de Maceió", e o cargo é do Legislativo.
CAMARA = (
    "CÂMARA MUNICIPAL DE MACEIÓ EDITAL Nº 12/2024 convoca para posse os aprovados. "
    "2.1.3 CARGO 3: PROCURADOR LEGISLATIVO 10003926, Anderson dos Anjos / 10011010, "
    "Andre Vinicius Nunes Silva / 10001201, Carolina Guimarães dos Santos"
)

# Rio de Janeiro. Homônimo por SUFIXO: o nome procurado está inteiro dentro de
# um nome maior. É a armadilha que a D25 descreve para o `dou.cita_nome`.
HOMONIMO_SUFIXO = (
    "convoca para posse os seguintes candidatos: RA20604519 SILVIO LUCIO PEREIRA "
    "CARDOSO SED-2728/2025 RA50130193 MARIA DAS DORES"
)

# Macatuba. Homônimo por PREFIXO, o outro lado da mesma armadilha.
HOMONIMO_PREFIXO = (
    "nomear os aprovados: OFICIAL ADMINISTRATIVO CAMILA DIAS DA SILVA 22016 "
    "OFICIAL ADMINISTRATIVO CAMILA PINHEIRO DE FREITAS 22566 OFICIAL ADMINISTRATIVO"
)

NOMEACAO = [
    ("ato de nomeação com a vaga descrita por aposentadoria de OUTRA pessoa",
     SANTOS, "CARLOS MOACYR FERREIRA NETO", True),
    ("convocação de aprovado, com o cargo colado ao nome",
     PAULINIA, "LEONARDO TOIOMOTO", True),
    ("licença médica não é entrada em cargo",
     LICENCA, "CARLOS MOACYR FERREIRA NETO", False),
    ("resultado de prova não é nomeação",
     RESULTADO, "THIAGO SANTOS BRAGA", False),
    ("exoneração é saída, não entrada",
     EXONERACAO, "MATHEUS KLOTZ BUSCH", False),
    ("homônimo por sufixo não empresta ato a ninguém",
     HOMONIMO_SUFIXO, "LUCIO PEREIRA CARDOSO", False),
    ("homônimo por prefixo tampouco",
     HOMONIMO_PREFIXO, "CAMILA PINHEIRO", False),
    ("nome que não está no trecho não casa",
     SANTOS, "JOAO DA SILVA", False),
]

# O território identifica o órgão? Só quando o diário é de um município e o ato
# é do Executivo dele.
TERRITORIO = [
    ("município conhecido usa o nome que o catálogo já escreve",
     "Rio de Janeiro", "RJ", "Prefeitura do Rio de Janeiro"),
    ("...e o artigo importa: São Paulo é 'de', Rio é 'do'",
     "São Paulo", "SP", "Prefeitura de São Paulo"),
    ("município novo entra pelo mesmo molde",
     "Paulínia", "SP", "Prefeitura de Paulínia"),
    # O DODF é um diário só para GDF, TCDF, Câmara Legislativa, Defensoria e
    # Polícia Civil. Território de DF não identifica órgão nenhum.
    ("Brasília não identifica órgão, e por isso devolve vazio",
     "Brasília", "DF", ""),
    ("território vazio devolve vazio", "", "SP", ""),
]

LEGISLATIVO = [
    ("concurso da Câmara Municipal no diário do município", CAMARA, True),
    ("ato do Executivo municipal não é do Legislativo", SANTOS, False),
]


def _gazeta(territorio, uf, data, trechos):
    return {"territory_name": territorio, "state_code": uf, "date": data,
            "url": "https://exemplo/x.pdf", "excerpts": trechos}


DECISAO = [
    (
        "um município com ato: é o destino",
        "LEONARDO TOIOMOTO", "202505",
        [_gazeta("Paulínia", "SP", "2025-05-19", [PAULINIA])],
        ("UNICO_DIARIO", "Prefeitura de Paulínia"),
    ),
    (
        # Caso real: CARLOS MOACYR FERREIRA NETO tem ato em Santos e um pedido de
        # prorrogação de posse em São Paulo. Escolher entre dois atos não é
        # trabalho de máquina.
        "dois municípios com ato: vai para a curadoria",
        "CARLOS MOACYR FERREIRA NETO", "202505",
        [_gazeta("Santos", "SP", "2025-03-07", [SANTOS]),
         _gazeta("São Paulo", "SP", "2025-02-07",
                 ["DESPACHO defiro o pedido de posse de CARLOS MOACYR FERREIRA NETO"])],
        ("VARIOS_DIARIOS", ""),
    ),
    (
        "diário sem ato de entrada não afirma nada",
        "THIAGO SANTOS BRAGA", "202507",
        [_gazeta("Brasília", "DF", "2025-01-31", [RESULTADO])],
        ("SEM_ATO", ""),
    ),
    (
        "sem diário nenhum",
        "FULANO DE TAL", "202505", [],
        ("SEM_DIARIO", ""),
    ),
    (
        # `None` é "não conseguimos perguntar" e não pode virar "não achamos".
        "consulta que falhou não é resposta vazia",
        "FULANO DE TAL", "202505", None,
        ("FALHA_NA_CONSULTA", ""),
    ),
    (
        "ato do Legislativo municipal não vira Prefeitura",
        "ANDRE VINICIUS NUNES SILVA", "202508",
        [_gazeta("Maceió", "AL", "2024-08-21", [CAMARA])],
        ("SEM_ATO", ""),
    ),
    (
        "ato no DODF não vira destino: o diário é de muitos órgãos",
        "ANA CAROLINA GOMES MELLAO HADAD", "202406",
        [_gazeta("Brasília", "DF", "2024-05-02",
                 ["nomear para o cargo de Defensor Público, respeitada a "
                  "classificação: ANA CAROLINA GOMES MELLAO HADAD, 71º"])],
        ("SEM_ATO", ""),
    ),
]

# A janela existe para que a nomeação ANTERIOR à entrada na CGU não seja lida
# como destino da saída. Competência ausente não abre a janela — fecha.
JANELA = [
    ("competência normal abre a janela em torno dela",
     "202505", ("2024-05-01", "2025-11-28")),
    ("competência vazia devolve janela impossível",
     "", ("9999-01-01", "9999-01-02")),
    ("competência malformada também",
     "20xx05", ("9999-01-01", "9999-01-02")),
    ("mês inválido também",
     "202513", ("9999-01-01", "9999-01-02")),
]


def main() -> int:
    falhas = 0

    print("— o trecho é ato de ENTRADA desta pessoa? —")
    for descricao, trecho, nome, esperado in NOMEACAO:
        obtido = diarios.parece_nomeacao(trecho, nome)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado}, obtido {obtido}")

    print("— o território identifica o órgão? —")
    for descricao, territorio, uf, esperado in TERRITORIO:
        obtido = diarios.orgao_do_territorio(territorio, uf)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— Executivo ou Legislativo? —")
    for descricao, trecho, esperado in LEGISLATIVO:
        obtido = diarios.e_legislativo(trecho)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    print("— a janela de publicação —")
    for descricao, mes, esperado in JANELA:
        obtido = diarios._janela(mes)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado}, obtido {obtido}")

    print("— decisão: o que vira destino e o que vira pauta —")
    for descricao, nome, mes, gazetas, (decisao, orgao) in DECISAO:
        obtido = diarios.destino_da_pessoa(nome, mes, gazetas)
        ok = obtido["decisao"] == decisao and obtido["orgao"] == orgao
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {(decisao, orgao)}, "
                  f"obtido {(obtido['decisao'], obtido['orgao'])}")

    total = len(NOMEACAO) + len(TERRITORIO) + len(LEGISLATIVO) + len(JANELA) + len(DECISAO)
    print()
    print(f"{total - falhas} de {total} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
