#!/usr/bin/env python3
"""
Teste de regressão do crawler de destinos. Sem rede, sem dependência.

    python testar_ranking.py     # 0 = tudo certo

Cada caso aqui é um erro que já aconteceu de verdade, ou que quase foi ao ar.
Nenhum deles quebra nada: todos produzem um site plausível e errado sobre pessoa
real e nomeada, que é a única coisa que este observatório não pode fazer. Antes
de mexer no catálogo ou na regra de decisão de `ranking.py`, rode isto; depois
de mexer, rode de novo.

O que este arquivo NÃO testa é a precisão da regra contra a realidade — isso é
outra coisa e tem comando próprio, que usa rede:

    python enriquecer_destinos_ranking.py --conferir
"""

from __future__ import annotations

import sys

import ranking

# --------------------------------------------------------------------- catálogo
#
# A razão de o catálogo existir: sem ele o mesmo órgão entra duas vezes na tabela
# de destinos, com grafias diferentes, e o leitor conta dois lugares onde há um.
CANONICO = [
    ("sigla e nome por extenso caem no MESMO órgão",
     "TCU", "Tribunal de Contas da União"),
    ("a edição do concurso não muda o órgão",
     "TCU TI 25", "Tribunal de Contas da União"),
    ("nem o nível do cargo",
     "Camara dos Deputados 25 NS", "Câmara dos Deputados"),
    ("nem o cargo dentro da mesma casa",
     "Camara dos Deputados Consultor", "Câmara dos Deputados"),
    ("duas edições do mesmo tribunal são um órgão só",
     "TCE PE 17", "Tribunal de Contas do Estado de Pernambuco"),
    ("e a outra edição também",
     "TCE PE 25", "Tribunal de Contas do Estado de Pernambuco"),
    ("a Receita publica sob o Ministério da Fazenda, como o DOU já grava",
     "RFB", "Ministério da Fazenda"),
    ("o fisco municipal e a secretaria de fazenda do MESMO município se juntam",
     "ISS Rio de Janeiro", "Prefeitura do Rio de Janeiro"),
    ("...e é o mesmo nome pela outra sigla",
     "SMF RJ", "Prefeitura do Rio de Janeiro"),
    ("procuradoria municipal de São Paulo e ISS SP também",
     "PGM SP", "Prefeitura de São Paulo"),
    ("...idem",
     "ISS SP", "Prefeitura de São Paulo"),
    ("família de UF: a sigla vira o nome do estado por extenso",
     "SEFAZ MG", "Secretaria de Fazenda de Minas Gerais"),
    ("família TRF reproduz a forma que o DOU já usa",
     "TRF 5 24", "Tribunal Regional Federal da 5ª Região"),
    ("TRT guarda a Região: o número NÃO é edição",
     "TRT 13 PB", "Tribunal Regional do Trabalho da 13ª Região"),
    ("...e a 6ª Região é outro tribunal, não o mesmo",
     "TRT 6 PE", "Tribunal Regional do Trabalho da 6ª Região"),
    ("dois espaços e caixa trocada não criam órgão novo",
     "  tcu  ", "Tribunal de Contas da União"),
]

# Rótulo que o catálogo não conhece devolve `""` — nunca um nome inventado.
# Publicar "BLABLA 25" como órgão de destino de pessoa real seria pior que
# calar; devolver vazio é o que faz o enriquecedor mandá-lo para a pauta.
SEM_CATALOGO = ["BLABLA 25", "SEFAZ ZZ", "TCE XX", ""]

# Concurso unificado: aprovação real, órgão indefinido. Não é "desconhecido por
# falha nossa" — o rótulo genuinamente não diz para onde a pessoa foi.
UNIFICADOS = ["CNU", "TSE Unificado"]

ANOS = [
    ("ano de quatro dígitos", "TRE SP 2016", 2016),
    ("ano de dois dígitos no fim", "TJDFT 22", 2022),
    ("ano depois do nível", "Camara dos Deputados 25 NS", 2025),
    ("sem ano é o caso mais comum, e é None", "TCU", None),
    ("o 13 do TRT é Região, não ano", "TRT 13 PB", None),
]


def _linha(nome, concurso, nomeado=False):
    return {"nome": nome, "concurso": concurso, "cargo": "", "nota": "",
            "colocacao": "", "nomeado": nomeado, "dentro_das_vagas": False}


ALVO = "JOAO DA SILVA"

DECISAO = [
    (
        "um concurso além da CGU: é o destino",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU")],
        ("UNICO", "Tribunal de Contas da União"),
    ),
    (
        "sem linha nenhuma da pessoa",
        ALVO, "202401", [],
        ("SEM_FICHA", ""),
    ),
    (
        # A busca do site casa por PREFIXO. Sem a igualdade exata de nome, as
        # aprovações de "JOAO DA SILVA SANTOS" viravam destino de "JOAO DA
        # SILVA" — duas pessoas diferentes, uma afirmação inventada.
        "homônimo por prefixo não empresta aprovação a ninguém",
        ALVO, "202401",
        [_linha("JOAO DA SILVA SANTOS", "TCU"), _linha("JOAO DA SILVA SANTOS", "CGU")],
        ("SEM_FICHA", ""),
    ),
    (
        "só a CGU: passou no concurso de entrada e em mais nada",
        ALVO, "202401", [_linha(ALVO, "CGU")],
        ("SEM_CANDIDATO", ""),
    ),
    (
        # O ranking sabe o CONJUNTO de concursos, não sabe qual a pessoa foi
        # exercer. Medido: nos 62 ambíguos do gabarito o destino certo estava
        # entre os candidatos nos 62, e mesmo assim nenhum desempate passa de
        # 38,7%. Escolher um seria chutar com cara de dado.
        "dois concursos possíveis: não se escolhe, vai para a curadoria",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU"), _linha(ALVO, "Senado")],
        ("AMBIGUO", ""),
    ),
    (
        # A marca azul "Nomeado" acerta 6 de 18 quando usada para desempatar —
        # ela diz que a pessoa foi nomeada NAQUELE concurso algum dia, e quem
        # passa em vários é nomeado em vários.
        "a marca 'Nomeado' NÃO desempata",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU", nomeado=True), _linha(ALVO, "Senado")],
        ("AMBIGUO", ""),
    ),
    (
        # Sem esta guarda o caso pareceria ter candidato único e o TCU iria ao ar
        # sozinho, escondendo que existe um concurso cujo órgão não se sabe.
        "concurso unificado ao lado de um órgão torna o caso ambíguo",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU"), _linha(ALVO, "CNU")],
        ("AMBIGUO", ""),
    ),
    (
        "rótulo fora do catálogo também impede candidato único",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU"), _linha(ALVO, "ORGAO NOVO 24")],
        ("AMBIGUO", ""),
    ),
    (
        "só rótulo fora do catálogo: não é 'sem candidato', é lacuna do catálogo",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "ORGAO NOVO 24")],
        ("SEM_CATALOGO", ""),
    ),
    (
        # Um concurso cujo resultado saiu DEPOIS da saída não pode ter motivado
        # a saída. Caso real: Câmara municipal de 2026 aparecendo como destino
        # de quem saiu em 11/2025.
        "concurso posterior à saída não é destino",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "Camara São Roque SP 26")],
        ("SEM_CANDIDATO", ""),
    ),
    (
        # Caso real: TJDFT de 2022 como destino de quem saiu em 05/2026.
        "concurso velho demais também não",
        ALVO, "202605",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TJDFT 22")],
        ("SEM_CANDIDATO", ""),
    ),
    (
        "dentro da janela, vale",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TJDFT 22")],
        ("UNICO", "Tribunal de Justiça do Distrito Federal e dos Territórios"),
    ),
    (
        "duas linhas do MESMO órgão são um candidato só, não dois",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU"), _linha(ALVO, "TCU TI 25")],
        ("UNICO", "Tribunal de Contas da União"),
    ),
    (
        "acento e caixa no nome não impedem o casamento",
        "JOAO DA SILVA", "202401",
        [_linha("João da Silva", "CGU"), _linha("João da Silva", "TCU")],
        ("UNICO", "Tribunal de Contas da União"),
    ),
    (
        # A âncora é a linha do concurso da própria CGU. Sem ela, o que se tem é
        # um nome batendo com um nome num site que nem sabe que essa pessoa foi
        # da CGU — e as fichas sem âncora foram justamente as que não conheciam
        # o concurso para o qual a pessoa de fato foi. Custa 2 acertos, corta 2
        # erros: 91,8% -> 95,6% no gabarito.
        "sem a linha da CGU na ficha, candidato único NÃO publica",
        ALVO, "202401",
        [_linha(ALVO, "TCU")],
        ("SEM_ANCORA_CGU", ""),
    ),
    (
        "com âncora e um candidato na janela, publica",
        ALVO, "202601",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU TI 25")],
        ("UNICO", "Tribunal de Contas da União"),
    ),
    (
        # Sem âncora e sem candidato nenhum a resposta continua sendo a de
        # sempre: não há o que a âncora salvasse.
        "sem âncora e sem candidato segue SEM_CANDIDATO",
        ALVO, "202401", [_linha(ALVO, "Senado 26")],
        ("SEM_CANDIDATO", ""),
    ),
]

# A âncora exigida de quem NÃO pode tê-la excluía uma categoria inteira. O
# ranking só conhece o concurso da CGU de 2022; quem entrou antes (VETERANO)
# jamais terá aquela linha na ficha. Caso real: veterano com vacância em
# 08/2026 e uma única aprovação no site (TCU), que ficava fora do painel só
# por isso. Medido: veterano sem âncora acerta 2 de 2; concursado sem âncora,
# 0 de 2 — a falta só é informativa para quem poderia tê-la.
DECISAO_VETERANO = [
    (
        "veterano sem a linha da CGU publica, porque nunca poderia tê-la",
        ALVO, "202608", [_linha(ALVO, "TCU")], "VETERANO",
        ("UNICO", "Tribunal de Contas da União"),
    ),
    (
        "o mesmo caso vindo do concurso NÃO publica",
        ALVO, "202608", [_linha(ALVO, "TCU")], "CGU-2021",
        ("SEM_ANCORA_CGU", ""),
    ),
    (
        "concurso não informado cai no caminho estrito",
        ALVO, "202608", [_linha(ALVO, "TCU")], "",
        ("SEM_ANCORA_CGU", ""),
    ),
    (
        "veterano ambíguo continua ambíguo — a âncora não era o que faltava",
        ALVO, "202608",
        [_linha(ALVO, "TCU"), _linha(ALVO, "Senado")], "VETERANO",
        ("AMBIGUO", ""),
    ),
]

# A tag azul é registrada para a pauta e NUNCA decide. Ver a medição em
# ranking.py: 6 de 18 como desempate, porque a tag não tem data — ela marca
# quem foi nomeado naquele concurso em algum momento da vida, inclusive ANTES
# de entrar na CGU.
TAG = [
    (
        "a tag entra na resposta, para a pauta",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU", nomeado=True), _linha(ALVO, "Senado")],
        ["Tribunal de Contas da União"],
    ),
    (
        "sem tag nenhuma, lista vazia",
        ALVO, "202401",
        [_linha(ALVO, "CGU"), _linha(ALVO, "TCU"), _linha(ALVO, "Senado")],
        [],
    ),
]

# A página de bloqueio do site vem com status 200 e sem tabela. Lida como
# resultado, ela virava "esta pessoa não está no ranking" — e gravava SEM_FICHA
# para quem tem ficha. O eco do nome no formulário é a prova de que a busca rodou.
PAGINA_BLOQUEIO = (
    '<!DOCTYPE html><html><head><title>Muitas Consultas</title></head>'
    '<body><div class="container"><h1>Muitas Consultas</h1></div></body></html>'
)
PAGINA_BUSCA = (
    '<form><input type="text" id="pesquisarInput" name="nome_candidato" '
    'value="JOAO DA SILVA" placeholder="Digite o nome do candidato"></form>'
)

RESPOSTA_VALIDA = [
    ("página de bloqueio 'Muitas Consultas' NÃO é resposta de busca",
     PAGINA_BLOQUEIO, "JOAO DA SILVA", False),
    ("página de busca com o nome ecoado é resposta",
     PAGINA_BUSCA, "JOAO DA SILVA", True),
    ("página que ecoa OUTRO nome não é resposta a esta consulta",
     PAGINA_BUSCA, "MARIA DE SOUZA", False),
    ("página vazia não é resposta", "", "JOAO DA SILVA", False),
]

# A tabela do site, como ela é. Guarda contra o layout mudar em silêncio.
TABELA = """
<table class="table"><thead><tr><th></th><th>Nome</th></tr></thead><tbody>
<tr class='odd'>
  <td style='text-align:center;'><span style="background-color: #3b82f6;"></span></td>
  <td>Jo&atilde;o da Silva</td>
  <td style='text-align:center;'>TCU</td>
  <td style='text-align:center;'>Auditor <a href='x'><img src='y'></a></td>
  <td style='text-align:center;'>134.75</td>
  <td style='text-align:center;'>43&ordm; (Ampla)</td>
  <td style='text-align:center;'>33&ordm; CGU</td>
</tr>
</tbody></table>
"""


def main() -> int:
    falhas = 0

    print("— catálogo de órgãos: grafias diferentes, um destino só —")
    for descricao, rotulo, esperado in CANONICO:
        obtido = ranking.canonico(rotulo)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        {rotulo!r}: esperado {esperado!r}, obtido {obtido!r}")

    print("— rótulo sem regra devolve vazio, nunca um nome inventado —")
    for rotulo in SEM_CATALOGO:
        obtido = ranking.canonico(rotulo)
        ok = obtido == ""
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {rotulo!r} -> {obtido!r}")

    print("— concurso unificado não identifica órgão —")
    for rotulo in UNIFICADOS:
        obtido = ranking.canonico(rotulo)
        ok = obtido is None
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {rotulo!r} -> {obtido!r}")

    print("— edição do concurso —")
    for descricao, rotulo, esperado in ANOS:
        obtido = ranking.ano_do_rotulo(rotulo)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        {rotulo!r}: esperado {esperado!r}, obtido {obtido!r}")

    print("— decisão: o que vira destino e o que vira pauta —")
    for descricao, nome, mes, linhas, (decisao, orgao) in DECISAO:
        obtido = ranking.destino_da_pessoa(nome, mes, linhas)
        ok = obtido["decisao"] == decisao and obtido["orgao"] == orgao
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {(decisao, orgao)}, "
                  f"obtido {(obtido['decisao'], obtido['orgao'])}")

    print("— a âncora só é exigida de quem pode tê-la (veterano) —")
    for descricao, nome, mes, linhas, concurso, (decisao, orgao) in DECISAO_VETERANO:
        obtido = ranking.destino_da_pessoa(nome, mes, linhas, concurso)
        ok = obtido["decisao"] == decisao and obtido["orgao"] == orgao
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {(decisao, orgao)}, "
                  f"obtido {(obtido['decisao'], obtido['orgao'])}")

    print("— a tag 'Nomeado' é registrada, mas não decide —")
    for descricao, nome, mes, linhas, esperado in TAG:
        obtido = ranking.destino_da_pessoa(nome, mes, linhas)
        ok = obtido["marcados_nomeado"] == esperado and obtido["orgao"] == ""
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")
        if not ok:
            print(f"        esperado {esperado}, obtido {obtido['marcados_nomeado']} "
                  f"orgao={obtido['orgao']!r}")

    print("— a resposta do site é mesmo uma resposta? —")
    for descricao, pagina, nome, esperado in RESPOSTA_VALIDA:
        obtido = ranking.pagina_respondeu_a_busca(pagina, nome)
        ok = obtido == esperado
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    print("— leitura da tabela —")
    linhas = ranking.analisar(TABELA)
    casos = [
        ("uma linha lida", len(linhas) == 1),
        ("nome com entidade HTML resolvida", linhas and linhas[0]["nome"] == "João da Silva"),
        ("concurso", linhas and linhas[0]["concurso"] == "TCU"),
        ("nota", linhas and linhas[0]["nota"] == "134.75"),
        ("colocação com º", linhas and linhas[0]["colocacao"] == "43º (Ampla)"),
        ("marca de nomeado lida da cor", linhas and linhas[0]["nomeado"] is True),
        ("sem tabela devolve lista vazia", ranking.analisar("<p>nada</p>") == []),
    ]
    for descricao, ok in casos:
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    total = (len(CANONICO) + len(SEM_CATALOGO) + len(UNIFICADOS) + len(ANOS)
             + len(DECISAO) + len(DECISAO_VETERANO) + len(TAG)
             + len(RESPOSTA_VALIDA) + len(casos))
    print()
    print(f"{total - falhas} de {total} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
