#!/usr/bin/env python3
"""
As fontes que chegam DEPOIS do `construir_painel.py`, aplicadas sobre o que ele
derivou (D29).

BIBLIOTECA PURA: nenhuma função aqui abre arquivo nem toca na rede. Quem lê e
grava é o `gerar_publicacao.py`, e quem prova que as regras continuam valendo é o
`testar_publicacao.py`. É a mesma separação de `painel.py` × `construir_painel.py`.

POR QUE ISTO EXISTE, E POR QUE NÃO ESTÁ NO `construir_painel.py`
---------------------------------------------------------------
O `construir_painel.py` depende dos 49 snapshots do Portal da Transparência, que
somam ~70 MB, estão fora do Git e portanto não existem no CI. Ele roda uma vez
por competência, na máquina de quem tem os snapshots.

Só que duas fontes mudam MUITO mais depressa que isso:

  - `public/atos_dou.json`     — a varredura do DOU, todo dia, no CI
  - `data/destinos_ranking.csv` — o crawler de destinos, toda semana, no CI

Se a mescla morasse no `construir_painel.py`, uma saída publicada hoje no DOU
esperaria a próxima execução local para aparecer no site — que é exatamente a
defasagem que ela existe para eliminar.

Até 16/08/2026 a conclusão disso foi mesclar NO NAVEGADOR (`mesclarFontesExternas`,
em `lib/painel.ts`). Funcionava, mas cobrava um preço: toda página que lesse o
`dados.csv` tinha de LEMBRAR de mesclar, e uma página que esquecesse publicaria
número desatualizado sem erro nenhum — falha silenciosa.

A saída é que a mescla não precisa dos snapshots. Suas três entradas —
`dados.csv`, `atos_dou.json` e `destinos_ranking.csv` — estão TODAS no Git. Logo
ela roda no CI, e roda no lugar mais tarde possível: na hora de publicar o site
(`deploy-pages.yml`), que já dispara a cada push e ao fim da varredura do DOU. O
frescor é o mesmo de antes, e o resultado é um arquivo pronto — o site deixa de
processar dado e passa só a lê-lo.

A PRECEDÊNCIA NÃO MUDOU: CURADORIA > DOU > RANKING. Ela continua garantida pela
ORDEM em que as duas mesclas se aplicam, e é por isso que `mesclar_fontes_externas`
existe em vez de as duas serem chamadas soltas.
"""

from __future__ import annotations

import dou

# Espelha `SITUACAO_EM_EXERCICIO` de `painel.py` e de `constants.ts`. Aqui só
# serve para dizer de onde a pessoa saiu no log de alterações.
SITUACAO_EM_EXERCICIO = "EM EXERCÍCIO"

# Coluna que NÃO existe no `dados.csv` e existe no `painel.csv`: `NÃO` marca a
# saída que só o ato do DOU conhece, e vazio quer dizer que o cadastro mostrou a
# ausência. Toda saída do `dados.csv` nasce do diff mensal do SIAPE (D13), então
# vazio aqui é o mesmo que "atestada pelo SIAPE" — é assim que `fontesDaSaida`
# decide o selo na tela.
COLUNA_SAIDA_NO_SIAPE = "SAIDA_NO_SIAPE"


def mesclar_saidas_do_dou(registros: list[dict], saidas_recentes: list[dict]) -> list[dict]:
    """
    Traz para dentro do painel as saídas que só o DOU conhece (D22).

    O ato já foi publicado; o Portal da Transparência é que ainda não entregou a
    competência que mostraria a ausência (~2 meses de atraso). A pessoa JÁ ESTÁ no
    `dados.csv` — ativa —, então aqui não se cria linha nova: sobrepõe-se a saída
    ao registro que já existe. É por isso que ela chega à tela com concurso, área
    e unidade, e responde aos filtros como qualquer outra.

    TRÊS GUARDAS CONTRA CONTAR ERRADO, que era o motivo de estas saídas ficarem
    fora das contagens até 15/08/2026:

      - sobrepõe-se por `ID_SERVIDOR_PORTAL`, que o `gerar_card_dou.py` casou por
        nome MAIS matrícula (D12 — nome não é chave). Ato sem id casado não entra;
      - só se aplica a quem NÃO tem `MES_SAIDA`. Quem o SIAPE já mostrou saindo
        fica com a versão do SIAPE, e uma pessoa com dois atos não vira duas
        saídas;
      - quem não está no `dados.csv` não entra de jeito nenhum — é o caso do ato
        sobre servidor de outro cargo ou já fora do quadro. Repare que isto sai
        de graça da forma como o laço é escrito: percorrem-se os REGISTROS, e o
        ato que não casa com nenhum simplesmente não é usado.
    """
    por_id = {s["idServidor"]: s for s in saidas_recentes if s.get("idServidor")}
    if not por_id:
        return [dict(registro) for registro in registros]

    mesclados: list[dict] = []
    for registro in registros:
        saida = por_id.get(registro.get("ID_SERVIDOR_PORTAL", ""))
        if not saida:
            mesclados.append(dict(registro))
            continue

        # O que o ato diz, e que vale nos dois casos abaixo.
        do_ato = {
            "SITUACAO": dou.SITUACAO_POR_TIPO.get(saida["tipo"], registro.get("SITUACAO", "")),
            "MOTIVO_SAIDA": saida["rotulo"],
            "FONTE_MOTIVO": "DOU",
            "DATA_PUBLICACAO_SAIDA": saida["dataPublicacao"],
            "ATO_SAIDA_TITULO": saida["titulo"],
            "ATO_SAIDA_URL": saida["urlDou"],
            "ATO_SAIDA_ARQUIVO": saida.get("arquivo") or "",
        }

        if registro.get("MES_SAIDA"):
            # O SIAPE já mostrou esta pessoa sumindo, mas ninguém tinha achado o
            # ato dela — ela aparecia como "saída sem ato identificado". O ato
            # COMPLETA o motivo e não mexe na competência: quem sabe quando ela
            # saiu é o cadastro, e o selo continua sendo SIAPE + DOU.
            if registro.get("MOTIVO_SAIDA") or not saida.get("jaNoSiape"):
                mesclados.append(dict(registro))
                continue
            mesclados.append({**registro, **do_ato})
            continue

        publicacao = saida["dataPublicacao"]
        mesclados.append(
            {
                **registro,
                **do_ato,
                # A competência da PUBLICAÇÃO. Não é a data do fato — o ato costuma
                # dizer "a contar de" alguns dias antes —, mas é a única que se tem
                # antes de o SIAPE confirmar, e erra por dias, não por meses.
                "MES_SAIDA": publicacao[:4] + publicacao[5:7],
                COLUNA_SAIDA_NO_SIAPE: "NÃO",
            }
        )
    return mesclados


def mesclar_destinos_do_ranking(registros: list[dict], destinos: list[dict]) -> list[dict]:
    """
    Preenche o órgão de destino que o rankingdosconcursos identificou (D24).

    Recebe as linhas do `destinos_ranking.csv` como o CSV as traz.

    SÓ PREENCHE O QUE ESTÁ VAZIO. Quem já tem destino tem porque o DOU ou a
    curadoria o deram, e essas duas fontes valem mais: o DOU é ato publicado, a
    curadoria é gente que conferiu. O ranking nunca sobrepõe nem corrige nenhuma
    das duas — é a camada de baixo, e a precedência do observatório continua
    sendo CURADORIA > DOU > RANKING.

    O QUE O ARQUIVO JÁ RESOLVEU ANTES DE CHEGAR AQUI. O crawler só escreve
    `ORGAO_DESTINO` em duas situações: sobrou UM candidato só, ou sobrou mais de
    um e a marca azul "Nomeado" do site aponta exatamente um deles (D26). Caso
    ambíguo fica no arquivo sem órgão, aguardando curadoria, e a guarda
    `not destino.get("ORGAO_DESTINO")` abaixo é o que garante que ele não vaze
    para a tela por descuido.

    `FONTE_DESTINO` vem do próprio CSV, e não é fixada aqui: o arquivo carrega
    DUAS fontes desde a D27 — a aprovação em concurso (`RANKING`), o ato em diário
    municipal (`DIARIO`) e, desde a D28, a posse no sítio do órgão (`GOOGLE`).
    Fixá-la daria ao ranking o crédito de um ato publicado.

    Recebe os registros JÁ MESCLADOS por `mesclar_saidas_do_dou`: quem saiu e só o
    DOU sabe também merece destino, e só depois daquela mescla essa pessoa tem
    `MES_SAIDA`.
    """
    por_id = {
        d["ID_SERVIDOR_PORTAL"]: d
        for d in destinos
        if d.get("ID_SERVIDOR_PORTAL") and d.get("ORGAO_DESTINO")
    }
    if not por_id:
        return [dict(registro) for registro in registros]

    mesclados: list[dict] = []
    for registro in registros:
        destino = por_id.get(registro.get("ID_SERVIDOR_PORTAL", ""))
        # Sem saída registrada não há destino a preencher, e destino já preenchido
        # veio de fonte melhor.
        if not destino or not registro.get("MES_SAIDA") or registro.get("ORGAO_DESTINO"):
            mesclados.append(dict(registro))
            continue

        mesclados.append(
            {
                **registro,
                "ORGAO_DESTINO": destino["ORGAO_DESTINO"],
                "FONTE_DESTINO": destino.get("FONTE_DESTINO") or "RANKING",
                "URL_DESTINO": destino.get("URL_DESTINO", ""),
            }
        )
    return mesclados


def mesclar_fontes_externas(
    registros: list[dict], saidas_recentes: list[dict], destinos: list[dict]
) -> list[dict]:
    """
    O `dados.csv` mais tudo o que chegou depois dele. **É ESTA que se chama** —
    nunca as duas mescladas soltas.

    A ORDEM importa e fica garantida aqui: DOU antes do ranking, porque o ranking
    preenche o destino de quem tem saída, e quem só o DOU conhece só ganha
    `MES_SAIDA` na mescla anterior.

    Os dois argumentos aceitam lista vazia: o painel funciona sem nenhum dos dois
    arquivos, mostrando só o que o SIAPE sabe. Falta de fonte externa degrada a
    tela, não a derruba.
    """
    return mesclar_destinos_do_ranking(
        mesclar_saidas_do_dou(registros, saidas_recentes), destinos
    )


def acrescentar_saidas_do_dou(log: dict, registros: list[dict]) -> dict:
    """
    Põe no histórico de alterações as saídas que só o DOU conhece (D22).

    O `alteracoes-registros.json` nasce do diff mês a mês do SIAPE, no
    `construir_painel.py`, e por isso vai só até a última competência do Portal.
    Quem saiu depois disso não aparecia em lugar nenhum daquela página — nem como
    saída, nem como pendência. Aqui elas entram no bloco do mês correspondente,
    criando o mês se ele ainda não existir.

    Recebe os registros JÁ MESCLADOS por `mesclar_saidas_do_dou`: é de lá que vêm
    `SAIDA_NO_SIAPE`, a situação e a unidade.
    """
    so_do_dou = [
        r for r in registros if r.get(COLUNA_SAIDA_NO_SIAPE) == "NÃO" and r.get("MES_SAIDA")
    ]
    if not so_do_dou:
        return dict(log)

    por_mes: dict[str, dict] = {}
    for mes in log.get("history", []):
        por_mes[mes["mes"]] = {**mes, "changes": list(mes.get("changes", []))}

    for registro in so_do_dou:
        competencia = registro["MES_SAIDA"]
        mes = por_mes.get(competencia) or {
            "mes": competencia,
            # `AAAA-MM-01` — o dia é convenção, o fato é mensal.
            "data": f"{competencia[:4]}-{competencia[4:]}-01",
            "changeCount": 0,
            "changes": [],
        }
        # Uma pessoa só aparece uma vez no mês: se o SIAPE já a tivesse registrado
        # saindo, ela não teria sido mesclada — mas a guarda é barata e o efeito de
        # errar seria a mesma saída contada duas vezes na tela.
        if not any(m["id"] == registro["ID_SERVIDOR_PORTAL"] for m in mes["changes"]):
            mes["changes"].append(
                {
                    "id": registro["ID_SERVIDOR_PORTAL"],
                    "nome": registro["NOME"],
                    "tipo": "saida",
                    "fromSituacao": SITUACAO_EM_EXERCICIO,
                    "toSituacao": registro.get("SITUACAO", ""),
                    "orgaoDestino": registro.get("ORGAO_DESTINO", ""),
                    "unidade": registro.get("UNIDADE", ""),
                    "concurso": registro.get("CONCURSO", ""),
                }
            )
        por_mes[competencia] = mes

    # O JSON vem do mês mais novo para o mais antigo, e a página conta com isso.
    history = sorted(
        ({**mes, "changeCount": len(mes["changes"])} for mes in por_mes.values()),
        key=lambda mes: mes["mes"],
        reverse=True,
    )

    return {
        **log,
        # O log deixou de ser só do SIAPE: dizer que a fonte é uma só passaria a
        # ser falso justamente nas linhas mais recentes da página.
        "fonte": f"{log.get('fonte', '')}, e Diário Oficial da União para as saídas "
                 f"que o cadastro ainda não registrou",
        "ultimoMes": history[0]["mes"] if history else log.get("ultimoMes", ""),
        "totalChangeCount": sum(mes["changeCount"] for mes in history),
        "history": history,
    }
