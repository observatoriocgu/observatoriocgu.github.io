#!/usr/bin/env python3
"""
Procura no rankingdosconcursos o DESTINO de quem já saiu — e só dele.

Entrada : data/dados.csv        — quem o SIAPE mostra que saiu
          public/atos_dou.json  — as saídas que só o DOU conhece ainda (D22)
Saída   : data/destinos_ranking.csv

A ordem é sempre esta, e é o que separa este crawler de uma máquina de fofoca:

    a pessoa JÁ SAIU (SIAPE ou DOU)  ->  o ranking diz PARA ONDE

Nunca o contrário. Passar em concurso não é sair da CGU — há Auditor com seis
aprovações que continua na CGU, e ele não aparece em lugar nenhum deste arquivo.
Quem não tem saída registrada não é consultado.

POR QUE O RESULTADO NÃO ENTRA NO dados.csv
------------------------------------------
Pelo mesmo motivo da D22: o `construir_painel.py` depende dos snapshots do
Portal, que estão fora do Git e não existem no CI, e quem roda sozinho todo mês
é este crawler. Se a mescla morasse no Python, um destino descoberto hoje
esperaria a próxima execução local. Então o arquivo é lido pelo NAVEGADOR, em
`mesclarDestinosDoRanking` (lib/painel.ts), que preenche apenas o destino VAZIO
— DOU e curadoria continuam vencendo, porque já vêm preenchidos do `dados.csv`.

O QUE VAI À TELA E O QUE VAI PARA A PAUTA
-----------------------------------------
Só `DECISAO = UNICO` vira destino em tela. Ambíguo fica no arquivo com a lista
de candidatos e o link da consulta, para decisão humana — e a decisão humana
tem lugar próprio, `data/curadoria.csv`, que vence tudo (basta a linha com
ID_SERVIDOR_PORTAL, ORGAO_DESTINO, FONTE_DESTINO=MANUAL e URL_DESTINO).

A régua está medida, não estimada: contra os 118 destinos que o DOU já conhece,
a regra publica 45 e acerta 43 (95,6%). Qualquer desempate entre candidatos
múltiplos fica em 27-39%, e por isso não existe desempate aqui. Ver `ranking.py`.

INCREMENTAL
-----------
Cada linha guarda `CONSULTADO_EM`. Quem já ficou resolvido não é consultado de
novo; quem ficou sem resposta é reconsultado depois de `DIAS_PARA_RECONSULTAR`,
porque o site ganha concursos novos toda semana e a ficha de hoje não é a de
daqui a um mês. Saída nova entra na fila na primeira execução seguinte.

Uso:
    python enriquecer_destinos_ranking.py
    python enriquecer_destinos_ranking.py --limite 10    # só os 10 primeiros
    python enriquecer_destinos_ranking.py --refazer      # reconsulta todo mundo
    python enriquecer_destinos_ranking.py --nome "FULANO"  # uma pessoa, com detalhe
    python enriquecer_destinos_ranking.py --conferir     # mede contra o gabarito
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import ranking

RAIZ = Path(__file__).resolve().parent.parent
ARQ_DADOS = RAIZ / "data" / "dados.csv"
ARQ_DESTINOS = RAIZ / "data" / "destinos_ranking.csv"
ARQ_CARD = RAIZ / "public" / "atos_dou.json"

COLUNAS = (
    "ID_SERVIDOR_PORTAL", "NOME", "MES_SAIDA", "DECISAO",
    "ORGAO_DESTINO", "FONTE_DESTINO", "URL_DESTINO",
    "CANDIDATOS", "MARCADOS_NOMEADO", "ROTULOS_SEM_CATALOGO", "CONSULTADO_EM",
)

# Só se procura destino de quem o ato diz ter tomado posse em outro cargo.
#
# Aposentadoria e falecimento não têm destino — não é destino desconhecido, é
# destino inexistente. Exoneração e "saída sem ato identificado" ficam de fora
# por outro motivo: o ato não afirma que a pessoa foi ocupar outro cargo, então
# uma aprovação em concurso não sustenta a frase "foi para o TCU". Nenhum
# exonerado tem destino vindo do DOU tampouco — a exclusão é coerente com o que
# o observatório já faz, não uma restrição nova.
MOTIVO_ALVO = "Vacância (posse em outro cargo)"
TIPO_ATO_ALVO = "vacancia"

FONTE = "RANKING"

DIAS_PARA_RECONSULTAR = 30


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]


def gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUNAS, delimiter=";",
                                  extrasaction="ignore", lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


def saidas_so_do_dou() -> list[dict]:
    """
    As saídas que o DOU já anunciou e o SIAPE ainda não confirmou (D22).

    Vêm de `public/atos_dou.json`, e não do `atos_dou.csv`, por um motivo
    concreto: o `ID_SERVIDOR_PORTAL` do índice é preenchido pelo
    `enriquecer_saidas.py`, que parte do `dados.csv` — logo, só existe para quem
    o SIAPE JÁ mostrou saindo. Quem casa o ato recente com uma pessoa é o
    `gerar_card_dou.py`, na hora de montar o JSON, e o resultado desse
    casamento mora só nele. Ler o mesmo arquivo que o navegador lê é também o
    que garante que esta fila seja exatamente a lista de saídas que está na tela.
    """
    if not ARQ_CARD.is_file():
        return []
    try:
        card = json.loads(ARQ_CARD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [s for s in card.get("saidasRecentes", []) if s.get("idServidor")]


def alvos(pessoas: list[dict], recentes: list[dict]) -> list[dict]:
    """
    Quem saiu por posse em outro cargo e ainda está sem órgão de destino.

    Duas origens, como no resto do observatório: o `dados.csv`, que é o SIAPE, e
    as saídas que só o DOU conhece (D22). A segunda é SOBREPOSTA à pessoa que já
    existe no `dados.csv` — ato sem `idServidor` não entra, porque não se sabe
    de quem é, e ninguém que não esteja no `dados.csv` entra de jeito nenhum.
    """
    por_id = {p["ID_SERVIDOR_PORTAL"]: p for p in pessoas}
    fila: dict[str, dict] = {}

    for pessoa in pessoas:
        if not pessoa.get("MES_SAIDA") or pessoa.get("ORGAO_DESTINO"):
            continue
        if pessoa.get("MOTIVO_SAIDA") != MOTIVO_ALVO:
            continue
        fila[pessoa["ID_SERVIDOR_PORTAL"]] = {
            "ID_SERVIDOR_PORTAL": pessoa["ID_SERVIDOR_PORTAL"],
            "NOME": pessoa["NOME"],
            "MES_SAIDA": pessoa["MES_SAIDA"],
            # O concurso de ENTRADA decide se a âncora é exigível: veterano
            # nunca vai ter a linha da CGU no site. Ver `ranking.exige_ancora`.
            "CONCURSO": pessoa.get("CONCURSO", ""),
        }

    for saida in recentes:
        identificador = saida["idServidor"]
        pessoa = por_id.get(identificador)
        if not pessoa or pessoa.get("ORGAO_DESTINO"):
            continue
        if saida.get("tipo") != TIPO_ATO_ALVO:
            continue
        # Quem já tem MES_SAIDA entrou pelo laço de cima, com a competência do
        # cadastro — que é a boa. Aqui só entra quem o SIAPE ainda não mostrou,
        # e a competência é a da PUBLICAÇÃO, como faz o `mesclarSaidasDoDou`.
        if pessoa.get("MES_SAIDA"):
            continue
        publicacao = saida.get("dataPublicacao") or ""
        if len(publicacao) < 7:
            continue
        fila[identificador] = {
            "ID_SERVIDOR_PORTAL": identificador,
            "NOME": pessoa["NOME"],
            "MES_SAIDA": publicacao[:4] + publicacao[5:7],
            "CONCURSO": pessoa.get("CONCURSO", ""),
        }

    return sorted(fila.values(), key=lambda a: (a["MES_SAIDA"], a["NOME"]))


def precisa_consultar(anterior: dict | None, refazer: bool, hoje: date) -> bool:
    if refazer or not anterior:
        return True
    if anterior.get("DECISAO") == "UNICO" and anterior.get("ORGAO_DESTINO"):
        return False
    try:
        consultado = datetime.strptime(anterior.get("CONSULTADO_EM", ""), "%Y-%m-%d").date()
    except ValueError:
        return True
    return hoje - consultado >= timedelta(days=DIAS_PARA_RECONSULTAR)


def consultar(alvo: dict, usar_cache: bool, verboso: bool = False) -> dict:
    linhas = ranking.buscar_por_nome(alvo["NOME"], usar_cache=usar_cache)

    # `None` é "não conseguimos perguntar", e não pode virar "não achamos nada".
    # A linha fica sem CONSULTADO_EM de propósito: é isso que faz
    # `precisa_consultar` trazê-la de volta na próxima execução, em vez de
    # deixá-la parada por 30 dias com uma resposta que ninguém deu.
    if linhas is None:
        return {
            "ID_SERVIDOR_PORTAL": alvo["ID_SERVIDOR_PORTAL"],
            "NOME": alvo["NOME"],
            "MES_SAIDA": alvo["MES_SAIDA"],
            "DECISAO": "FALHA_NA_CONSULTA",
            "ORGAO_DESTINO": "", "FONTE_DESTINO": "", "URL_DESTINO": "",
            "CANDIDATOS": "", "MARCADOS_NOMEADO": "",
            "ROTULOS_SEM_CATALOGO": "", "CONSULTADO_EM": "",
        }

    achado = ranking.destino_da_pessoa(
        alvo["NOME"], alvo["MES_SAIDA"], linhas, alvo.get("CONCURSO", ""))

    if verboso:
        minhas = ranking.linhas_da_pessoa(alvo["NOME"], linhas)
        print(f"  {len(linhas)} linha(s) na busca, {len(minhas)} da própria pessoa")
        for linha in minhas:
            marca = "NOMEADO" if linha["nomeado"] else ("vagas" if linha["dentro_das_vagas"] else "")
            print(f"    {marca:8} {linha['concurso']:32} {linha['colocacao']:14} "
                  f"-> {ranking.canonico(linha['concurso'])}")

    return {
        "ID_SERVIDOR_PORTAL": alvo["ID_SERVIDOR_PORTAL"],
        "NOME": alvo["NOME"],
        "MES_SAIDA": alvo["MES_SAIDA"],
        "DECISAO": achado["decisao"],
        "ORGAO_DESTINO": achado["orgao"],
        "FONTE_DESTINO": FONTE if achado["orgao"] else "",
        "URL_DESTINO": achado["url"] if achado["orgao"] else "",
        "CANDIDATOS": " | ".join(achado["candidatos"]),
        # Só informativo, para a pauta de curadoria. A tag azul "Nomeado" do
        # site acerta 6 de 18 como desempate — ver `ranking.py`.
        "MARCADOS_NOMEADO": " | ".join(achado["marcados_nomeado"]),
        "ROTULOS_SEM_CATALOGO": " | ".join(achado["rotulos_sem_catalogo"]),
        "CONSULTADO_EM": date.today().isoformat(),
    }


def conferir(pessoas: list[dict], limite: int | None, usar_cache: bool) -> int:
    """
    Mede a regra contra as saídas cujo destino o DOU já conhece.

    É o gabarito desta fonte, e o análogo do `testar_dou.py`: a única maneira de
    saber se "candidato único" acerta é aplicá-lo onde a resposta já existe. Não
    grava nada.
    """
    gabarito = [
        p for p in pessoas
        if p.get("MES_SAIDA") and p.get("MOTIVO_SAIDA") == MOTIVO_ALVO
        and p.get("ORGAO_DESTINO") and p.get("FONTE_DESTINO") == "DOU"
    ]
    if limite:
        gabarito = gabarito[:limite]

    print(f"Conferindo contra {len(gabarito)} destino(s) que o DOU já conhece.\n")
    acertos = erros = 0
    contagem: dict[str, int] = {}

    for i, pessoa in enumerate(gabarito, 1):
        linhas = ranking.buscar_por_nome(pessoa["NOME"], usar_cache=usar_cache)
        if linhas is None:
            contagem["FALHA_NA_CONSULTA"] = contagem.get("FALHA_NA_CONSULTA", 0) + 1
            continue
        achado = ranking.destino_da_pessoa(
            pessoa["NOME"], pessoa["MES_SAIDA"], linhas, pessoa.get("CONCURSO", ""))
        contagem[achado["decisao"]] = contagem.get(achado["decisao"], 0) + 1
        if achado["decisao"] == "UNICO":
            if achado["orgao"] == pessoa["ORGAO_DESTINO"]:
                acertos += 1
            else:
                erros += 1
                print(f"  DIVERGE  {pessoa['NOME'][:36]:36} "
                      f"DOU={pessoa['ORGAO_DESTINO'][:28]:28} ranking={achado['orgao'][:28]}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(gabarito)}", file=sys.stderr)

    publicados = acertos + erros
    print()
    for decisao, quantidade in sorted(contagem.items()):
        print(f"  {quantidade:4}  {decisao}")
    print()
    print(f"Publicaria {publicados}: {acertos} iguais ao DOU, {erros} diferentes"
          f"{f' ({100 * acertos / publicados:.1f}% de acerto)' if publicados else ''}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procura no rankingdosconcursos o destino de quem já saiu da CGU.")
    parser.add_argument("--limite", type=int, help="No máximo N pessoas consultadas.")
    parser.add_argument("--refazer", action="store_true",
                        help="Reconsulta todo mundo, inclusive quem já está resolvido.")
    parser.add_argument("--nome", help="Consulta uma pessoa só, com detalhe, sem gravar.")
    parser.add_argument("--conferir", action="store_true",
                        help="Mede a regra contra os destinos que o DOU já conhece. Não grava.")
    parser.add_argument("--sem-cache", action="store_true", help="Ignora o cache em disco.")
    args = parser.parse_args()

    usar_cache = not args.sem_cache
    pessoas = ler_csv(ARQ_DADOS)
    if not pessoas:
        print(f"! {ARQ_DADOS} não existe ou está vazio.", file=sys.stderr)
        return 1

    if args.conferir:
        return conferir(pessoas, args.limite, usar_cache)

    if args.nome:
        alvo = next((p for p in pessoas if args.nome.upper() in p["NOME"].upper()), None)
        if not alvo:
            print(f"! ninguém no dados.csv casa com {args.nome!r}.", file=sys.stderr)
            return 1
        print(f"{alvo['NOME']}  (saída {alvo['MES_SAIDA'] or '—'})")
        linha = consultar(
            {"ID_SERVIDOR_PORTAL": alvo["ID_SERVIDOR_PORTAL"], "NOME": alvo["NOME"],
             "MES_SAIDA": alvo["MES_SAIDA"], "CONCURSO": alvo.get("CONCURSO", "")},
            usar_cache, verboso=True,
        )
        print(f"  decisão: {linha['DECISAO']}  destino: {linha['ORGAO_DESTINO'] or '—'}")
        print(f"  candidatos: {linha['CANDIDATOS'] or '—'}")
        print(f"  {ranking.url_da_consulta(alvo['NOME'])}")
        print("\n--nome não grava nada.")
        return 0

    fila = alvos(pessoas, saidas_so_do_dou())
    anteriores = {l["ID_SERVIDOR_PORTAL"]: l for l in ler_csv(ARQ_DESTINOS)}
    hoje = date.today()

    a_consultar = [a for a in fila if precisa_consultar(anteriores.get(a["ID_SERVIDOR_PORTAL"]),
                                                        args.refazer, hoje)]
    if args.limite:
        a_consultar = a_consultar[:args.limite]
    pendentes = {a["ID_SERVIDOR_PORTAL"] for a in a_consultar}

    print(f"Saídas por posse em outro cargo sem destino: {len(fila)}")
    print(f"A consultar agora: {len(a_consultar)} "
          f"(as demais já foram consultadas há menos de {DIAS_PARA_RECONSULTAR} dias "
          f"ou já estão resolvidas)\n")

    resultado: list[dict] = []
    for i, alvo in enumerate(a_consultar, 1):
        linha = consultar(alvo, usar_cache)
        resultado.append(linha)
        marca = "->" if linha["DECISAO"] == "UNICO" else "  "
        print(f"  {i:3}/{len(a_consultar)} {marca} {alvo['NOME'][:38]:38} "
              f"{linha['DECISAO']:13} {linha['ORGAO_DESTINO'][:34]}")

    # O arquivo é reescrito a partir da fila ATUAL: quem deixou de ser alvo
    # (porque o DOU achou o destino, ou a curadoria decidiu) sai daqui, e o
    # arquivo continua sendo exatamente "o que o ranking sabe sobre as saídas
    # que seguem sem destino". Quem não foi consultado agora mantém a linha
    # anterior, com a data de quando foi.
    linhas_finais = []
    for alvo in fila:
        identificador = alvo["ID_SERVIDOR_PORTAL"]
        if identificador in pendentes:
            linhas_finais.append(next(l for l in resultado
                                      if l["ID_SERVIDOR_PORTAL"] == identificador))
        elif identificador in anteriores:
            linhas_finais.append(anteriores[identificador])

    gravar_csv(ARQ_DESTINOS, linhas_finais)

    resolvidos = [l for l in linhas_finais if l.get("DECISAO") == "UNICO"]
    # `SEM_ANCORA_CGU` entra na mesma pauta: há um candidato só, e o que falta é
    # a prova de que a ficha é desta pessoa. É decisão de gente, não de máquina —
    # e foi por não ter essa prova que dois destinos errados quase foram ao ar.
    ambiguos = [l for l in linhas_finais
                if l.get("DECISAO") in ("AMBIGUO", "SEM_ANCORA_CGU")]
    falhas = [l for l in linhas_finais if l.get("DECISAO") == "FALHA_NA_CONSULTA"]
    sem_catalogo = sorted({r for l in linhas_finais
                           for r in (l.get("ROTULOS_SEM_CATALOGO") or "").split(" | ") if r})

    print()
    print(f"{ARQ_DESTINOS.name}: {len(linhas_finais)} linha(s)")
    print(f"  destino identificado (vai à tela) : {len(resolvidos)}")
    print(f"  aguardando curadoria              : {len(ambiguos)}")
    print(f"  sem ficha ou sem candidato        : "
          f"{len(linhas_finais) - len(resolvidos) - len(ambiguos) - len(falhas)}")
    if falhas:
        print(f"  ! consulta falhou (será refeita)  : {len(falhas)}")

    if sem_catalogo:
        print()
        print("Rótulos de concurso que o catálogo não conhece — acrescente em")
        print("ranking.ORGAO_POR_ROTULO para que virem destino:")
        for rotulo in sem_catalogo:
            print(f"  - {rotulo}")

    if ambiguos:
        print()
        print("Ambíguos: o ranking mostra mais de um concurso possível e não diz qual")
        print("a pessoa foi exercer. Para decidir, conferir a fonte e registrar em")
        print("data/curadoria.csv (ORGAO_DESTINO, FONTE_DESTINO=MANUAL, URL_DESTINO):")
        for linha in ambiguos[:10]:
            print(f"  - {linha['NOME'][:34]:34} {linha['CANDIDATOS'][:70]}")
        if len(ambiguos) > 10:
            print(f"  ... e mais {len(ambiguos) - 10}, no arquivo")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
