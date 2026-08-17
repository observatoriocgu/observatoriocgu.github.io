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
ARQ_POR_PESSOA = RAIZ / "data" / "dou" / "por_pessoa.csv"
DIR_ATOS = RAIZ / "data" / "dou" / "atos_saida"

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
    (
        # Portaria 3.232, de 29/09/2025. Casava o gatilho da vacância, não casava
        # "posse em outro cargo", e caía fora de todos os tipos: o Auditor
        # aparecia como "saída sem ato identificado" com o ato publicado.
        "'declarar vago por desistência do estágio probatório' é EXONERAÇÃO "
        "(art. 33, I), não vacância — o ato não fala em posse nenhuma",
        f"Art. 1o Declarar vago, a contar do dia 8 de outubro de 2025, por desistencia do "
        f"estagio probatorio, o cargo de {CARGO} da Controladoria-Geral da Uniao, classe B, "
        f"padrao IV, ocupado pelo servidor JOAO DA SILVA, SIAPE no 1810341, de acordo com "
        f"art. 33, inciso I, da Lei no 8.112, de 11 de dezembro de 1990",
        "exoneracao",
    ),
    (
        "'declarar vago' sem motivo reconhecido não classifica — a forma do ato "
        "não diz se a pessoa foi embora, se aposentou ou se foi promovida",
        f"Art. 1o Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA, "
        f"com fundamento no art. 33, inciso III, da Lei no 8.112",
        None,
    ),
    (
        # Portaria 3.089, de 09/11/2022: o DOU publicou o ato truncado no meio da
        # frase, sem nome e sem motivo por extenso. O inciso é o que restou.
        "ato truncado pelo próprio DOU: o inciso VIII do art. 33 é a posse em "
        "outro cargo, e sozinho basta para classificar",
        f"Conforme inciso VIII do art. 33 da Lei no 8.112, de 11 de dezembro de 1990, resolve: "
        f"DECLARAR VAGO, a contar de 27 de outubro de 2022, o cargo efetivo de {CARGO}, "
        f"codigo 403/100-NS, classe C, padrao II, O.",
        "vacancia",
    ),
    (
        # Portaria Normativa SE/CGU nº 224, de 03/09/2025.
        "portaria NORMATIVA sobre carteirinha de aposentado não aposenta ninguém",
        "PORTARIA NORMATIVA SE/CGU no 224, de 3 de setembro de 2025. Aprova os modelos e "
        f"estabelece os procedimentos para emissao das cedulas de identificacao destinadas as "
        f"pessoas aposentadas nos cargos da carreira. Art. 1o Esta Portaria Normativa aprova os "
        f"modelos: cedula de identificacao do aposentado - {CARGO}",
        None,
    ),
    (
        # A guarda acima se ancora no INÍCIO do texto justamente por isto: metade
        # dos atos de vacância reais cita uma Portaria Normativa como fundamento.
        "citar Portaria Normativa como fundamento não descaracteriza a vacância",
        f"PORTARIA No 3.089, no uso da competencia que lhe foi subdelegada pelo art. 2o da "
        f"PORTARIA NORMATIVA CGU no 33, de 8 de novembro de 2022, resolve: declarar vago o cargo "
        f"de {CARGO} ocupado pelo servidor JOAO DA SILVA, por motivo de posse em outro cargo",
        "vacancia",
    ),
    (
        # Extrato de 25/08/2023. Documento disciplinar, com nome de gente — a
        # palavra "aposentadoria" está na descrição da conduta, não no ato.
        "ajustamento de conduta é instrumento disciplinar, não saída: o servidor "
        "não saiu, e o ato não pode ir ao ar com link",
        f"EXTRATO DE AJUSTAMENTO DE CONDUTA PROCESSO No 00190.106909/2023-85 SERVIDOR CELEBRANTE: "
        f"JOAO DA SILVA ({CARGO}) DESCRICAO DO FATO: apresentar comportamento inadequado ao "
        f"requerer concessao de beneficio de aposentadoria junto a COPAG",
        None,
    ),
    (
        # Portaria 3.331, de 09/10/2025.
        "reverter a aposentadoria é o CONTRÁRIO de uma saída: a pessoa volta",
        f"Art. 1o Reverter a aposentadoria da servidora MARIA APARECIDA SOUZA, ocupante do cargo "
        f"de {CARGO}, classe S, padrao V, matricula SIAPE no 1571351, para que retorne ao quadro "
        f"de pessoal desta Controladoria-Geral da Uniao",
        None,
    ),
    (
        # Portaria 2.909, de 01/09/2025 — "aposentadoria" está no nome da empresa
        # investigada, e o Auditor citado é quem vai apurar, não quem saiu.
        "abertura de processo contra empresa não é saída de ninguém",
        f"Art. 1o Instaurar Processo Administrativo de Responsabilizacao destinado a apuracao de "
        f"supostas irregularidades praticadas pelo ente privado CASA DE APOIO AO BENEFICIARIO "
        f"PREVIDENCIARIO DE APOSENTADORIA E PENSAO. Art. 2o Designar JOAO DA SILVA, {CARGO}, "
        f"matricula SIAPE no 1022042, para integrar a comissao",
        None,
    ),
    (
        "inciso I citado ao lado do VIII não confunde: 'INCISO I' não pode casar "
        "dentro de 'INCISO VIII'",
        f"Tendo em vista o disposto no art. 33, inciso VIII, c/c o art. 34, paragrafo unico, "
        f"inciso I, resolve declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA",
        "vacancia",
    ),
]

# A cessão não cita o cargo de AFFC — só a busca por NOME a alcança, com a
# identidade provada pela matrícula. Por isso estes casos rodam com
# `exigir_cargo=False`, que é como `enriquecer_saidas.py` os classifica.
CLASSIFICACAO_SEM_CARGO = [
    (
        # Portaria 604, de 23/02/2023. Sem este tipo, o Auditor cedido aparecia
        # como "saída sem ato identificado" — e a saída dele não é evasão.
        "cessão a outro órgão é saída do quadro da CGU, com motivo próprio",
        "Art. 1o CEDER O SERVIDOR JOAO DA SILVA, matricula SIAPE no 1459878, pertencente ao "
        "quadro de pessoal da Controladoria-Geral da Uniao, para exercer a Funcao Comissionada "
        "Executiva de Coordenador-Geral de Governanca e Controle da Policia Federal, codigo "
        "FCE 1.13, do Ministerio da Justica e Seguranca Publica. Art. 2o O onus pela remuneracao "
        "e do orgao cedente. Art. 4o Torna-se sem efeito o disposto nesta Portaria caso o "
        "servidor nao se apresente a entidade cessionaria no prazo de trinta dias",
        "cessao",
    ),
    (
        "o ato que ENCERRA a cessão diz o oposto: a pessoa volta para a CGU",
        "Art. 1o Dar por encerrada a cessao do servidor JOAO DA SILVA, matricula SIAPE no "
        "1459878, ceder o servidor ao orgao de origem a partir desta data",
        None,
    ),
    (
        "'tornar sem efeito' a cessão também não é saída",
        "Tornar sem efeito a portaria que resolveu ceder o servidor JOAO DA SILVA, matricula "
        "SIAPE no 1459878, ao Ministerio da Justica",
        None,
    ),
]

# A retificação é o único ato que traz o nome, mas é pobre e tem a data errada.
# O que se lê nela é a REFERÊNCIA ao ato original, que tem motivo, data e URL.
RETIFICACAO = [
    (
        "retificação que acrescenta o nome que faltava aponta o ato original, "
        "e o número ganha o ponto de milhar que o título do DOU usa",
        "RETIFICACAO NA PORTARIA No 3089, DE 9 DE NOVEMBRO DE 2022, PUBLICADAS NA EDICAO DO "
        "DOU No 213, DE 10/11/2022, SECAO 2, PAGINA 47: ONDE SE LE: ... LEIA-SE: OCUPADO PELO "
        "SERVIDOR JOAO DA SILVA, MATRICULA SIAPE No 1980145",
        "PORTARIA Nº 3.089, DE 9 DE NOVEMBRO DE 2022",
    ),
    (
        "retificação que corrige a grafia do sobrenome aponta o mesmo caminho",
        f"RETIFICACAO NA PORTARIA No 2.025, DE 30 DE MAIO DE 2023, PUBLICADA NA EDICAO DO DOU "
        f"No 103, DE 31 DE MAIO DE 2023, SECAO II, PAGINA 82, QUE DECLARA VAGO O CARGO DE "
        f"{CARGO} OCUPADO PELO SERVIDOR JOAO DA SILVA, SIAPE NO 3302990",
        "PORTARIA Nº 2.025, DE 30 DE MAIO DE 2023",
    ),
    (
        "ato que não é retificação não manda buscar nada",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA, por motivo "
        f"de posse em outro cargo inacumulavel",
        "",
    ),
]

# De quem o ato é. Três provas de força diferente, e a distinção existe porque o
# DOU erra os dois lados: o nome (Portaria 325/2023 escreve "PAGLIONE" onde o
# SIAPE diz "PAGLIONI") e a matrícula (Portarias 1.026/2024, 2.529/2024 e
# 2.017/2025 nomeiam a pessoa por extenso e trazem um SIAPE que não é o dela).
IDENTIDADE = [
    (
        "matrícula que bate prova a identidade, mesmo com o DOU errando o nome",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVEIRA, "
        f"matricula SIAPE no 3321195",
        "JOAO DA SILVA",
        "332****",
        dou.IDENTIDADE_SIAPE,
    ),
    (
        "nome exato lido da fórmula prova a identidade mesmo com o DOU errando "
        "a matrícula — três vacâncias reais eram descartadas por isso",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA, "
        f"matricula SIAPE no 2435442",
        "JOAO DA SILVA",
        "334****",
        dou.IDENTIDADE_NOME,
    ),
    (
        "nome que é PREFIXO de outro não passa pela fórmula: com a matrícula "
        "divergindo, o ato é de outra pessoa e não se aproveita",
        f"Declarar vago o cargo de {CARGO} ocupado pelo servidor JOAO DA SILVA SOUZA, "
        f"matricula SIAPE no 2435442",
        "JOAO DA SILVA",
        "334****",
        "",
    ),
    (
        "sem matrícula no ato e sem fórmula legível, sobra a citação solta",
        "Fica designado JOAO DA SILVA para integrar o grupo de trabalho",
        "JOAO DA SILVA",
        "334****",
        dou.IDENTIDADE_CITACAO,
    ),
    (
        "ato que não cita a pessoa de jeito nenhum não prova nada",
        "Fica designada MARIA APARECIDA SOUZA para integrar o grupo de trabalho",
        "JOAO DA SILVA",
        "334****",
        "",
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
        # Portaria 1.968, de 17/08/2022 — o DOU não pôs a vírgula depois de "a
        # pedido", e o padrão que se ancora nela não casava nada.
        "exoneração sem a vírgula depois de 'a pedido'",
        f"EXONERAR, A PEDIDO LUIZ AUGUSTO DA SILVA ALVES, DO CARGO DE {CARGO.upper()} DA "
        f"CONTROLADORIA-GERAL DA UNIAO, A PARTIR DE 12 DE AGOSTO DE 2022",
        "LUIZ AUGUSTO DA SILVA ALVES",
    ),
    (
        "o preâmbulo NÃO pode entrar no nome: 'A Pedido Fulano' não é gente",
        f"EXONERAR, A PEDIDO JOAO DA SILVA, DO CARGO DE {CARGO.upper()}",
        "JOAO DA SILVA",
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


# O DOU ERROU O NOME, e há prova de que é a mesma pessoa.
#
# O extrator lê o que está escrito no ato — que é exatamente o que se quer dele —
# e o SIAPE guarda a grafia oficial. Quando os dois discordam porque o DOU
# digitou errado, a divergência é um fato sobre o DOU, não um erro de leitura, e
# contá-la como falha esconderia as falhas de verdade.
#
# ENTRAR AQUI EXIGE PROVA DOCUMENTAL de que os dois nomes são a mesma pessoa, e
# só duas servem:
#
#   retificação — a Portaria nº 2.025, de 30/05/2023, declarou vago o cargo de
#     "HENRIQUE DA SILVA KRANZFIELD"; a retificação de 01/06/2023 mandou ler
#     "KRANZFELD". O próprio DOU reconheceu o erro.
#
#   matrícula — a Portaria nº 325, de 02/02/2023, escreve "LUIS PAULO PAGLIONE
#     MARCONDES" e traz o SIAPE 3321195, que é o da pessoa que o Portal chama de
#     "PAGLIONI". A identidade está provada dentro do mesmo ato.
#
# O que NÃO serve é "os dois nomes se parecem". Nome errado sem prova continua
# sendo falha, e é isso que separa esta lista de um afrouxamento da régua.
ERROS_DE_GRAFIA_DO_DOU = {
    ("HENRIQUE DA SILVA KRANZFELD", "HENRIQUE DA SILVA KRANZFIELD"),
    ("LUIS PAULO PAGLIONI MARCONDES", "LUIS PAULO PAGLIONE MARCONDES"),
}


def conferir_nomes_do_corpus() -> tuple[int, str]:
    """
    Refaz a leitura do nome nos atos já arquivados e compara com o SIAPE.

    Não é teste sintético: usa os atos de verdade em `data/dou/atos_saida/` e o nome
    que a busca por nome já casou com uma pessoa no `data/dou/por_pessoa.csv`. É a
    única maneira honesta de medir um extrator de nome — as fórmulas do DOU
    variam mais do que se consegue imaginar de cabeça, e foi assim que
    apareceram a aposentadoria compulsória, a exoneração de ofício e o
    "servidoa".

    Sem rede: só relê arquivo. Devolve (falhas, resumo). Se os dados não
    estiverem à mão, não falha — apenas avisa que não conferiu.
    """
    if not ARQ_POR_PESSOA.is_file() or not DIR_ATOS.is_dir():
        return 0, "sem corpus local — conferência do nome não rodou"

    with open(ARQ_POR_PESSOA, encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.DictReader(fh, delimiter=";"))

    exato = vazio = grafia_do_dou = 0
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
        elif (dou.normalizar(esperado), dou.normalizar(obtido)) in ERROS_DE_GRAFIA_DO_DOU:
            grafia_do_dou += 1
        else:
            divergentes.append((esperado, obtido))

    total = exato + vazio + grafia_do_dou + len(divergentes)
    for esperado, obtido in divergentes:
        print(f"        DIVERGE: SIAPE diz {esperado!r}, ato leu {obtido!r}")
    if vazio:
        print(f"        ({vazio} ato(s) sem nome legível — aceitável, não é falha)")
    if grafia_do_dou:
        print(f"        ({grafia_do_dou} ato(s) em que o DOU errou o nome, com prova documental)")

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

    print("— classificação sem exigir o cargo (é como a busca por nome classifica) —")
    for descricao, texto, esperado in CLASSIFICACAO_SEM_CARGO:
        obtido = dou.classificar(texto, exigir_cargo=False)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— retificação: a frase que acha o ato original —")
    for descricao, texto, esperado in RETIFICACAO:
        frases = dou.frases_do_ato_retificado(texto)
        obtido = frases[0] if frases else ""
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado!r}, obtido {obtido!r}")

    print("— de quem o ato é —")
    for descricao, texto, nome, mascara, esperado in IDENTIDADE:
        obtido = dou.identidade_no_ato(texto, nome, mascara)
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
        len(CLASSIFICACAO) + len(CLASSIFICACAO_SEM_CARGO) + len(RETIFICACAO) + len(IDENTIDADE)
        + len(DESTINO) + len(MATRICULA) + len(EXTRACAO) + len(ORGAO)
        + len(NOME_NO_ATO) + 1  # +1: a conferência do corpus inteiro conta como uma
    )
    print()
    print(f"{total - falhas} de {total} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
