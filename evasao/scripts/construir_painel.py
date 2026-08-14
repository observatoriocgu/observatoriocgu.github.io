#!/usr/bin/env python3
"""
Constrói os arquivos de dado do observatório a partir dos snapshots do SIAPE.

    historico_transparencia_cgu/*.csv   (fonte bruta, fora do git)
    concurso_2021.csv                   (enriquecido — concurso.py, D17)
    saidas_dou.csv                      (enriquecido — enriquecer_saidas.py)
    curadoria.csv                       (curado à mão)
              |
              v
    historico_mensal.csv   base consolidada, uma linha por competência x pessoa (D16)
    dados.csv              uma linha por pessoa — é o que a interface lê
    serie_mensal.csv       uma linha por competência
    public/alteracoes-registros.json    o log de alterações

Precedência do merge: CURADORIA > DOU > CONCURSO > SIAPE.

Determinístico e idempotente: rodar duas vezes seguidas produz byte a byte o
mesmo resultado. É por isso que as camadas enriquecida e curada moram em
arquivos separados — se o crawler escrevesse direto no dados.csv, reconstruir o
painel apagaria o trabalho dele.

Uso:
    python construir_painel.py                # gera tudo
    python construir_painel.py --diagnostico  # só confere e relata
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import painel
from painel import normalizar

RAIZ = Path(__file__).resolve().parent.parent
DIR_DADOS = RAIZ / "data"

ARQ_HISTORICO = DIR_DADOS / "historico_mensal.csv"
ARQ_DADOS = DIR_DADOS / "dados.csv"
ARQ_SERIE = DIR_DADOS / "serie_mensal.csv"
ARQ_CONCURSO = DIR_DADOS / "concurso_2021.csv"
ARQ_SAIDAS = DIR_DADOS / "saidas_dou.csv"
ARQ_CURADORIA = DIR_DADOS / "curadoria.csv"
ARQ_SUGESTOES = DIR_DADOS / "curadoria_sugestoes.csv"
ARQ_ALTERACOES = RAIZ / "public" / "alteracoes-registros.json"

COLUNAS_DADOS = (
    # MATRICULA vem mascarada do Portal ("166****"), com 3 dígitos do SIAPE
    # visíveis. Fica aqui porque é o que permite ao enriquecer_saidas.py
    # descartar homônimo conferindo a matrícula citada no ato do DOU.
    "ID_SERVIDOR_PORTAL", "NOME", "MATRICULA", "CONCURSO", "AREA", "MES_ENTRADA", "DATA_POSSE",
    "INSCRICAO", "POSICAO_CONCURSO", "NOTA", "MODALIDADE", "UF_VAGA",
    "SITUACAO", "UNIDADE", "UF", "CEDIDO", "ORGAO_EXERCICIO",
    "CLASSE_CARGO", "PADRAO_CARGO",
    "MES_SAIDA", "SAIDA_PROVISORIA", "MOTIVO_SAIDA", "FONTE_MOTIVO",
    "DATA_SAIDA", "DATA_PUBLICACAO_SAIDA",
    "ATO_SAIDA_TITULO", "ATO_SAIDA_URL", "ATO_SAIDA_ARQUIVO",
    "ORGAO_DESTINO", "CARGO_DESTINO", "DATA_DESTINO", "FONTE_DESTINO", "URL_DESTINO",
    "VERIFICADO", "VERIFICADO_EM", "OBSERVACAO",
)

CAMPOS_DO_CONCURSO = ("AREA", "INSCRICAO", "POSICAO_CONCURSO", "NOTA", "MODALIDADE", "UF_VAGA")

MODALIDADE_AMPLA = "Ampla Concorrência"


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]


def gravar_csv(caminho: Path, colunas, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(colunas), delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def indexar_concurso(registros: list[dict]) -> tuple[dict, dict]:
    """
    (por_nome_normalizado, ambíguos).

    Quem concorre por cota aparece duas vezes no edital: na ampla concorrência e
    na lista da cota. As duas linhas são a mesma pessoa, então consolidamos:
    a classificação geral vem da ampla, e a MODALIDADE registra a cota — que é a
    informação que a ampla não tem.
    """
    por_nome: dict[str, list[dict]] = {}
    for registro in registros:
        por_nome.setdefault(normalizar(registro["NOME"]), []).append(registro)

    consolidado, ambiguos = {}, {}
    for nome, linhas in por_nome.items():
        inscricoes = {linha["INSCRICAO"] for linha in linhas}
        if len(inscricoes) > 1:
            # Duas inscrições diferentes sob o mesmo nome: homônimos. Nome não é
            # chave (D12), então não dá para escolher — fica para a curadoria.
            ambiguos[nome] = linhas
            continue

        amplas = [l for l in linhas if l["MODALIDADE"] == MODALIDADE_AMPLA]
        base = dict(amplas[0] if amplas else linhas[0])
        cotas = [l["MODALIDADE"] for l in linhas if l["MODALIDADE"] != MODALIDADE_AMPLA]
        if cotas:
            base["MODALIDADE"] = cotas[0]
        consolidado[nome] = base

    return consolidado, ambiguos


def sugerir_parecidos(nome: str, indice: dict) -> list[str]:
    """
    Candidatos plausíveis para um nome que não casou exatamente.

    Serve para a curadoria humana, NUNCA para preencher sozinho. O caso real que
    motiva isso é mudança de nome civil entre 2022 e hoje: `VITORIA TEIXEIRA
    ROCHA` no edital virou `VITORIA TEIXEIRA ROCHA TUMER` no SIAPE, e
    `ISABELLE BENLOLO DE AZEVEDO` virou `ISABELLE BENLOLO RODRIGUES`. Aplicar
    isso automaticamente seria atribuir área e nota a pessoa errada.
    """
    partes = nome.split()
    if len(partes) < 2:
        return []
    primeiro, segundo = partes[0], partes[1]
    return sorted(
        candidato
        for candidato in indice
        if candidato.split()[:2] == [primeiro, segundo] or (
            candidato.startswith(primeiro + " ") and partes[-1] in candidato.split()
        )
    )


def aplicar_concurso(pessoas: list[dict], registros: list[dict]) -> dict:
    """Preenche área/inscrição/classificação de quem casou por nome. Relata o resto."""
    indice, ambiguos = indexar_concurso(registros)
    relatorio = {"casados": 0, "sem_casar": [], "ambiguos": len(ambiguos), "sugestoes": []}

    for pessoa in pessoas:
        if pessoa["CONCURSO"] != painel.ID_CONCURSO_2021:
            continue
        nome = normalizar(pessoa["NOME"])
        registro = indice.get(nome)
        if not registro:
            relatorio["sem_casar"].append(pessoa)
            for candidato in sugerir_parecidos(nome, indice):
                relatorio["sugestoes"].append(
                    {
                        "ID_SERVIDOR_PORTAL": pessoa["ID_SERVIDOR_PORTAL"],
                        "NOME_SIAPE": pessoa["NOME"],
                        "NOME_EDITAL": indice[candidato]["NOME"],
                        "AREA_SUGERIDA": indice[candidato]["AREA"],
                        "INSCRICAO_SUGERIDA": indice[candidato]["INSCRICAO"],
                        "MES_ENTRADA": pessoa["MES_ENTRADA"],
                        "CONFIRMADO": "",
                    }
                )
            continue

        for campo in CAMPOS_DO_CONCURSO:
            pessoa[campo] = registro[campo]
        relatorio["casados"] += 1

    return relatorio


def aplicar_saidas_dou(pessoas: list[dict], saidas: list[dict]) -> int:
    por_id = {s["ID_SERVIDOR_PORTAL"]: s for s in saidas}
    aplicadas = 0
    for pessoa in pessoas:
        saida = por_id.get(pessoa["ID_SERVIDOR_PORTAL"])
        if not saida:
            continue
        for campo, valor in saida.items():
            # A camada do DOU nunca sobrescreve com vazio: ausência de achado
            # não é motivo para apagar o que o SIAPE já sabia.
            if campo in pessoa and valor:
                pessoa[campo] = valor
        if saida.get("SITUACAO"):
            pessoa["SITUACAO"] = saida["SITUACAO"]
        aplicadas += 1
    return aplicadas


def aplicar_curadoria(pessoas: list[dict], curadoria: list[dict]) -> int:
    """A camada humana vence todas as outras. Só toca no que estiver preenchido."""
    por_id = {c["ID_SERVIDOR_PORTAL"]: c for c in curadoria if c.get("ID_SERVIDOR_PORTAL")}
    aplicadas = 0
    for pessoa in pessoas:
        correcao = por_id.get(pessoa["ID_SERVIDOR_PORTAL"])
        if not correcao:
            continue
        for campo, valor in correcao.items():
            if campo in pessoa and campo != "ID_SERVIDOR_PORTAL" and valor:
                pessoa[campo] = valor
        pessoa["VERIFICADO"] = correcao.get("VERIFICADO") or "SIM"
        aplicadas += 1
    return aplicadas


def main() -> int:
    parser = argparse.ArgumentParser(description="Constrói o painel a partir dos snapshots do SIAPE.")
    parser.add_argument("--diagnostico", action="store_true", help="Confere e relata, sem gravar.")
    args = parser.parse_args()

    print(f"Snapshots: {painel.PASTA_SNAPSHOTS}")
    meses, cgu, fora = painel.carregar()
    print(f"           {len(meses)} meses, {meses[0]} -> {meses[-1]}")
    for aviso in painel.diagnosticar(meses, cgu):
        print(f"  * {aviso}")

    pessoas = painel.derivar_pessoas(meses, cgu, fora)
    saiu = [p for p in pessoas if p["MES_SAIDA"]]
    print()
    print(f"Pessoas   : {len(pessoas)}")
    print(f"Saídas    : {len(saiu)}"
          f" ({sum(1 for p in saiu if p['SAIDA_PROVISORIA'] == 'SIM')} provisória(s))")
    print(f"Efetivo   : {len(cgu[meses[0]])} ({meses[0]}) -> {len(cgu[meses[-1]])} ({meses[-1]})")

    for rotulo, filtro in (
        ("Entraram depois do 1º mês", lambda p: p["MES_ENTRADA"] != meses[0]),
        (f"Leva inicial ({meses[1]}+{meses[2]})", lambda p: p["MES_ENTRADA"] in meses[1:3]),
        ("Veteranos", lambda p: p["MES_ENTRADA"] == meses[0]),
    ):
        grupo = [p for p in pessoas if filtro(p)]
        saidas = sum(1 for p in grupo if p["MES_SAIDA"])
        pct = 100 * saidas / len(grupo) if grupo else 0
        print(f"  {rotulo:<28} {len(grupo):5d} | saíram {saidas:4d} ({pct:.1f}%)")

    registros_concurso = ler_csv(ARQ_CONCURSO)
    if registros_concurso:
        rel = aplicar_concurso(pessoas, registros_concurso)
        elegiveis = sum(1 for p in pessoas if p["CONCURSO"] == painel.ID_CONCURSO_2021)
        pct = 100 * rel["casados"] / elegiveis if elegiveis else 0
        print()
        print(f"Concurso  : {len(registros_concurso)} registros no edital "
              f"({len({r['INSCRICAO'] for r in registros_concurso})} pessoas distintas)")
        print(f"            casaram {rel['casados']} de {elegiveis} ({pct:.1f}%)")
        if rel["ambiguos"]:
            print(f"            {rel['ambiguos']} nome(s) com duas inscrições — homônimos, "
                  f"não casados de propósito (D12)")
        if rel["sugestoes"]:
            print(f"            {len(rel['sugestoes'])} sugestão(ões) para conferência humana")
    else:
        rel = {"sugestoes": []}
        print(f"\n! {ARQ_CONCURSO.name} não existe — rode `python concurso.py` para preencher a área.")

    saidas_dou = ler_csv(ARQ_SAIDAS)
    if saidas_dou:
        print(f"DOU       : {aplicar_saidas_dou(pessoas, saidas_dou)} saída(s) enriquecida(s)")
    else:
        print(f"! {ARQ_SAIDAS.name} não existe — rode `python enriquecer_saidas.py` para o motivo.")

    curadoria = ler_csv(ARQ_CURADORIA)
    if curadoria:
        print(f"Curadoria : {aplicar_curadoria(pessoas, curadoria)} correção(ões) humana(s)")

    # A pauta de conferência é montada antes do merge, então ainda traz quem a
    # curadoria já resolveu. Sem este filtro o arquivo mandaria refazer o mesmo
    # trabalho todo mês.
    ja_curados = {c["ID_SERVIDOR_PORTAL"] for c in curadoria if c.get("ID_SERVIDOR_PORTAL")}
    rel["sugestoes"] = [s for s in rel["sugestoes"] if s["ID_SERVIDOR_PORTAL"] not in ja_curados]

    sem_motivo = [p for p in pessoas if p["MES_SAIDA"] and not p["MOTIVO_SAIDA"]]
    print()
    print(f"Saídas sem motivo identificado: {len(sem_motivo)}")
    print(f"Saídas com destino            : {sum(1 for p in saiu if p['ORGAO_DESTINO'])}")

    if args.diagnostico:
        print("\nModo diagnóstico — nada gravado.")
        return 0

    historico = painel.gerar_historico(meses, cgu, pessoas)
    gravar_csv(ARQ_HISTORICO, painel.COLUNAS_HISTORICO, historico)
    gravar_csv(ARQ_DADOS, COLUNAS_DADOS, pessoas)
    gravar_csv(ARQ_SERIE, ("MES", "EFETIVO", "ENTRADAS", "SAIDAS", "CEDIDOS"),
               painel.gerar_serie_mensal(meses, cgu))

    ARQ_ALTERACOES.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ALTERACOES.write_text(
        json.dumps(painel.gerar_alteracoes(meses, cgu, pessoas), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if rel["sugestoes"]:
        gravar_csv(
            ARQ_SUGESTOES,
            ("ID_SERVIDOR_PORTAL", "NOME_SIAPE", "NOME_EDITAL", "AREA_SUGERIDA",
             "INSCRICAO_SUGERIDA", "MES_ENTRADA", "CONFIRMADO"),
            rel["sugestoes"],
        )

    print()
    for caminho, quantidade in (
        (ARQ_HISTORICO, len(historico)),
        (ARQ_DADOS, len(pessoas)),
        (ARQ_SERIE, len(meses)),
        (ARQ_ALTERACOES, None),
    ):
        tamanho = caminho.stat().st_size / 1e6
        extra = f", {quantidade} linhas" if quantidade else ""
        print(f"  gravado: {caminho.relative_to(RAIZ)} ({tamanho:.1f} MB{extra})")
    if rel["sugestoes"]:
        print(f"  gravado: {ARQ_SUGESTOES.relative_to(RAIZ)} "
              f"({len(rel['sugestoes'])} linhas — conferir à mão, nada foi aplicado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
