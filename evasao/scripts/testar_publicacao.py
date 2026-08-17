#!/usr/bin/env python3
"""
Teste de regressão da mescla que gera os arquivos finais do site. Sem rede.

    python testar_publicacao.py     # 0 = tudo certo

Cada caso aqui é uma guarda que já custou caro. A mescla decide, sobre pessoa
real e nomeada, se ela saiu, quando saiu, por quê e para onde — e erra em
silêncio: nada quebra, a tela só passa a afirmar outra coisa. Antes de mexer em
`publicacao.py`, rode isto; depois de mexer, rode de novo.

Este arquivo NASCEU DE UM GABARITO. Quando a mescla saiu do navegador para o
Python (D29), o TypeScript foi compilado com o esbuild e rodado sobre o
`dados.csv` inteiro: 2.009 linhas x 35 colunas e o log de 729 mudanças em 48
competências saíram idênticos aos do Python. O que ficou aqui são as regras que
aquela conferência exercitou, num tamanho que cabe na cabeça.
"""

from __future__ import annotations

import sys

import publicacao

# --------------------------------------------------------------------- cenário

# Quatro pessoas, uma para cada situação que a mescla precisa distinguir.
ATIVA = {"ID_SERVIDOR_PORTAL": "1", "NOME": "PESSOA ATIVA", "SITUACAO": "EM EXERCÍCIO",
         "UNIDADE": "Sede/DF", "CONCURSO": "CGU-2021", "MES_SAIDA": "", "MOTIVO_SAIDA": "",
         "FONTE_MOTIVO": "", "ORGAO_DESTINO": "", "FONTE_DESTINO": "", "URL_DESTINO": ""}

SAIU_SEM_ATO = {"ID_SERVIDOR_PORTAL": "2", "NOME": "PESSOA SEM ATO", "SITUACAO": "SAÍDA SEM ATO IDENTIFICADO",
                "UNIDADE": "Sede/DF", "CONCURSO": "CGU-2021", "MES_SAIDA": "202606", "MOTIVO_SAIDA": "",
                "FONTE_MOTIVO": "", "ORGAO_DESTINO": "", "FONTE_DESTINO": "", "URL_DESTINO": ""}

SAIU_COM_ATO = {"ID_SERVIDOR_PORTAL": "3", "NOME": "PESSOA COM ATO", "SITUACAO": "VACÂNCIA",
                "UNIDADE": "Sede/DF", "CONCURSO": "VETERANO", "MES_SAIDA": "202601",
                "MOTIVO_SAIDA": "Vacância (posse em outro cargo)", "FONTE_MOTIVO": "DOU",
                "ORGAO_DESTINO": "Tribunal de Contas da União", "FONTE_DESTINO": "DOU", "URL_DESTINO": "u"}

OUTRA = {"ID_SERVIDOR_PORTAL": "4", "NOME": "OUTRA PESSOA", "SITUACAO": "EM EXERCÍCIO",
         "UNIDADE": "CGU-Regional/MG", "CONCURSO": "CGU-2021", "MES_SAIDA": "", "MOTIVO_SAIDA": "",
         "FONTE_MOTIVO": "", "ORGAO_DESTINO": "", "FONTE_DESTINO": "", "URL_DESTINO": ""}

REGISTROS = [ATIVA, SAIU_SEM_ATO, SAIU_COM_ATO, OUTRA]


def ato(identificador: str, *, ja_no_siape: bool = False, tipo: str = "vacancia",
        data: str = "2026-08-11") -> dict:
    return {
        "nome": "QUALQUER", "tipo": tipo, "rotulo": "Vacância (posse em outro cargo)",
        "dataPublicacao": data, "titulo": "PORTARIA N 1", "urlDou": "https://in.gov.br/1",
        "arquivo": "2026-08-11_vacancia_portaria.html",
        "idServidor": identificador, "jaNoSiape": ja_no_siape,
    }


def por_id(linhas: list[dict]) -> dict[str, dict]:
    return {linha["ID_SERVIDOR_PORTAL"]: linha for linha in linhas}


def main() -> int:
    falhas = 0
    casos = []

    # ------------------------------------------------- saídas que só o DOU conhece
    r = por_id(publicacao.mesclar_saidas_do_dou(REGISTROS, [ato("1")]))
    casos += [
        ("ato sobre quem está ativo vira saída",
         r["1"]["MES_SAIDA"] == "202608"),
        ("...com a competência da PUBLICAÇÃO do ato",
         r["1"]["MES_SAIDA"] == "202608" and r["1"]["DATA_PUBLICACAO_SAIDA"] == "2026-08-11"),
        ("...marcada como ainda não confirmada pelo SIAPE",
         r["1"][publicacao.COLUNA_SAIDA_NO_SIAPE] == "NÃO"),
        ("...com a situação que corresponde ao tipo do ato",
         r["1"]["SITUACAO"] == "VACÂNCIA"),
        ("...e com o selo DOU no motivo",
         r["1"]["FONTE_MOTIVO"] == "DOU"),
        ("quem o ato não menciona fica intacto",
         r["4"] == OUTRA),
        ("quem já saiu pelo SIAPE não ganha marca de 'só no DOU'",
         publicacao.COLUNA_SAIDA_NO_SIAPE not in r["2"] or r["2"][publicacao.COLUNA_SAIDA_NO_SIAPE] != "NÃO"),
    ]

    # ------------------------------------------------- as três guardas da D22
    r = por_id(publicacao.mesclar_saidas_do_dou(REGISTROS, [ato("99")]))
    casos.append(("ato de quem não está no dados.csv não cria linha nova",
                  len(r) == 4 and "99" not in r))

    r = por_id(publicacao.mesclar_saidas_do_dou(REGISTROS, [ato("3")]))
    casos.append(("ato de quem já tem motivo não mexe em nada",
                  r["3"] == SAIU_COM_ATO))

    r = por_id(publicacao.mesclar_saidas_do_dou(REGISTROS, [ato("2", ja_no_siape=False)]))
    casos.append(("ato de quem o SIAPE já mostrou sair, sem jaNoSiape, é ignorado",
                  r["2"] == SAIU_SEM_ATO))

    r = por_id(publicacao.mesclar_saidas_do_dou(REGISTROS, [ato("2", ja_no_siape=True)]))
    casos += [
        ("ato COMPLETA o motivo de quem saiu sem ato identificado",
         r["2"]["MOTIVO_SAIDA"] == "Vacância (posse em outro cargo)"),
        ("...sem mexer na competência, que é a do cadastro",
         r["2"]["MES_SAIDA"] == "202606"),
        ("...e sem tirar dele o selo do SIAPE",
         r["2"].get(publicacao.COLUNA_SAIDA_NO_SIAPE, "") != "NÃO"),
    ]

    casos.append(("sem ato nenhum, os registros saem como entraram",
                  publicacao.mesclar_saidas_do_dou(REGISTROS, []) == REGISTROS))

    # ------------------------------------------------- destino do ranking
    def destino(identificador, orgao="Prefeitura de Santos", fonte="RANKING"):
        return {"ID_SERVIDOR_PORTAL": identificador, "ORGAO_DESTINO": orgao,
                "FONTE_DESTINO": fonte, "URL_DESTINO": "https://exemplo/ficha"}

    r = por_id(publicacao.mesclar_destinos_do_ranking(REGISTROS, [destino("2")]))
    casos += [
        ("destino preenche quem saiu e não tinha órgão",
         r["2"]["ORGAO_DESTINO"] == "Prefeitura de Santos"),
        ("...com a fonte que o CSV declara, não uma fixa",
         r["2"]["FONTE_DESTINO"] == "RANKING"),
    ]

    r = por_id(publicacao.mesclar_destinos_do_ranking(REGISTROS, [destino("2", fonte="DIARIO")]))
    casos.append(("ato em diário municipal não é creditado ao ranking",
                  r["2"]["FONTE_DESTINO"] == "DIARIO"))

    r = por_id(publicacao.mesclar_destinos_do_ranking(REGISTROS, [destino("3")]))
    casos.append(("ranking NÃO sobrepõe destino que o DOU já deu",
                  r["3"]["ORGAO_DESTINO"] == "Tribunal de Contas da União"))

    r = por_id(publicacao.mesclar_destinos_do_ranking(REGISTROS, [destino("1")]))
    casos.append(("quem não saiu não recebe destino",
                  r["1"]["ORGAO_DESTINO"] == ""))

    r = por_id(publicacao.mesclar_destinos_do_ranking(REGISTROS, [destino("2", orgao="")]))
    casos.append(("caso ambíguo (sem órgão no CSV) não vaza para a tela",
                  r["2"]["ORGAO_DESTINO"] == ""))

    # ------------------------------------------------- a ordem das duas mesclas
    r = por_id(publicacao.mesclar_fontes_externas(REGISTROS, [ato("1")], [destino("1")]))
    casos.append(("quem só o DOU conhece também recebe destino do ranking",
                  r["1"]["ORGAO_DESTINO"] == "Prefeitura de Santos"))

    # ------------------------------------------------- o log de alterações
    LOG = {"fonte": "SIAPE", "primeiroMes": "202207", "ultimoMes": "202606",
           "totalChangeCount": 1,
           "history": [{"mes": "202606", "data": "2026-06-01", "changeCount": 1,
                        "changes": [{"id": "2", "nome": "PESSOA SEM ATO", "tipo": "saida",
                                     "fromSituacao": "EM EXERCÍCIO", "toSituacao": "SAÍDA SEM ATO IDENTIFICADO",
                                     "orgaoDestino": "", "unidade": "Sede/DF", "concurso": "CGU-2021"}]}]}

    mesclados = publicacao.mesclar_fontes_externas(REGISTROS, [ato("1")], [])
    log = publicacao.acrescentar_saidas_do_dou(LOG, mesclados)
    casos += [
        ("a saída que só o DOU conhece cria a competência que faltava",
         [m["mes"] for m in log["history"]] == ["202608", "202606"]),
        ("...do mês mais novo para o mais antigo",
         log["history"][0]["mes"] > log["history"][1]["mes"]),
        ("...com a pessoa no bloco do mês do ato",
         log["history"][0]["changes"][0]["id"] == "1"),
        ("...e o total recontado",
         log["totalChangeCount"] == 2),
        ("o último mês passa a ser o do ato",
         log["ultimoMes"] == "202608"),
        ("a fonte deixa de dizer que é só o SIAPE",
         "Diário Oficial da União" in log["fonte"]),
        ("sem saída só do DOU, o log não é tocado",
         publicacao.acrescentar_saidas_do_dou(LOG, REGISTROS) == LOG),
    ]

    # A mesma pessoa não pode ser contada duas vezes no mesmo mês. Só acontece se
    # alguém afrouxar as guardas acima, e é por isso que a checagem fica aqui.
    log_repetido = publicacao.acrescentar_saidas_do_dou(
        {**LOG, "history": [{"mes": "202608", "data": "2026-08-01", "changeCount": 1,
                             "changes": [{"id": "1", "nome": "PESSOA ATIVA", "tipo": "saida",
                                          "fromSituacao": "EM EXERCÍCIO", "toSituacao": "VACÂNCIA",
                                          "orgaoDestino": "", "unidade": "Sede/DF",
                                          "concurso": "CGU-2021"}]}]},
        mesclados,
    )
    casos.append(("pessoa que já está no bloco do mês não entra de novo",
                  log_repetido["history"][0]["changeCount"] == 1))

    # ------------------------------------------------- pureza
    casos.append(("a mescla não altera os registros que recebeu",
                  ATIVA["MES_SAIDA"] == "" and ATIVA["ORGAO_DESTINO"] == ""))
    casos.append(("...nem o log que recebeu",
                  LOG["totalChangeCount"] == 1 and len(LOG["history"]) == 1))

    for descricao, ok in casos:
        falhas += not ok
        print(f"  {'ok  ' if ok else 'FALHA'} {descricao}")

    print()
    print(f"{len(casos) - falhas} de {len(casos)} invariantes OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
