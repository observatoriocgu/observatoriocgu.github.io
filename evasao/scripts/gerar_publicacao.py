#!/usr/bin/env python3
"""
Gera os arquivos FINAIS que o site lê (D29).

Entrada : data/dados.csv                  — o derivado do SIAPE (construir_painel.py)
          public/atos_dou.json             — as saídas que só o DOU conhece (D22)
          data/destinos_ranking.csv        — o destino de quem saiu (D24, D27, D28)
          public/alteracoes-registros.json — o log do diff mensal do SIAPE
Saída   : data/painel.csv                  — dados.csv + DOU + ranking, mesclado
          public/alteracoes.json           — o log com as saídas que só o DOU conhece

OS DOIS ARQUIVOS DE SAÍDA NÃO VÃO PARA O GIT. São artefato de publicação, como o
`dist/`: nascem na hora de montar o site, a partir de quatro arquivos que estão
versionados. Versioná-los custaria 425 KB reescritos a cada varredura do DOU e
criaria uma segunda verdade — alguém teria de LEMBRAR de regerá-los depois de
mexer nas entradas, e quem esquecesse publicaria dado velho em silêncio.

SEM REDE E DETERMINÍSTICO: só derruba arquivo em arquivo. Rodar duas vezes
seguidas produz byte a byte o mesmo resultado. É por isso que ele cabe no
`deploy-pages.yml` e no `prebuild` do npm, ao contrário do `construir_painel.py`,
que depende dos snapshots do Portal (fora do Git, ~70 MB).

O QUE ISTO SUBSTITUIU. Até 16/08/2026 a mescla acontecia no NAVEGADOR, em
`mesclarFontesExternas` (lib/painel.ts), e cada uma das três páginas tinha de
lembrar de chamá-la. Agora não há o que lembrar: a página lê o `painel.csv`, e
`dados.csv` não é mais servido ao site. Ver o cabeçalho de `publicacao.py` para
o porquê de a mescla não estar no `construir_painel.py`.

Uso:
    python gerar_publicacao.py
    python gerar_publicacao.py --diagnostico   # imprime o resumo, não grava
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import publicacao

RAIZ = Path(__file__).resolve().parent.parent
ARQ_DADOS = RAIZ / "data" / "dados.csv"
ARQ_DESTINOS = RAIZ / "data" / "destinos_ranking.csv"
ARQ_ATOS = RAIZ / "public" / "atos_dou.json"
ARQ_LOG = RAIZ / "public" / "alteracoes-registros.json"

ARQ_PAINEL = RAIZ / "data" / "painel.csv"
ARQ_ALTERACOES = RAIZ / "public" / "alteracoes.json"


def ler_csv(caminho: Path) -> tuple[list[dict], list[str]]:
    """Linhas e cabeçalhos. `([], [])` se o arquivo não existir."""
    if not caminho.is_file():
        return [], []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=";")
        linhas = [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in leitor
        ]
        return linhas, [(c or "").strip() for c in (leitor.fieldnames or [])]


def ler_json(caminho: Path) -> dict:
    if not caminho.is_file():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_csv(caminho: Path, colunas: list[str], linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(
            fh, fieldnames=colunas, delimiter=";", extrasaction="ignore", restval=""
        )
        escritor.writeheader()
        escritor.writerows(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera os arquivos finais que o site lê.")
    parser.add_argument("--diagnostico", action="store_true", help="Imprime o resumo, sem gravar.")
    args = parser.parse_args()

    registros, colunas = ler_csv(ARQ_DADOS)
    if not registros:
        print(f"! {ARQ_DADOS.relative_to(RAIZ)} está vazio ou não existe.")
        print("  Rode `python scripts/construir_painel.py` (precisa dos snapshots do Portal).")
        return 1

    # As duas fontes externas são OPCIONAIS por decisão, não por descuido: sem
    # elas o site mostra o que o SIAPE sabe, que é menos, mas não é errado.
    atos = ler_json(ARQ_ATOS)
    saidas_recentes = atos.get("saidasRecentes", [])
    if not atos:
        print(f"! {ARQ_ATOS.relative_to(RAIZ)} não existe — o painel sai sem as saídas do DOU.")

    destinos, _ = ler_csv(ARQ_DESTINOS)
    if not destinos:
        print(f"! {ARQ_DESTINOS.relative_to(RAIZ)} não existe — o painel sai sem os destinos do ranking.")

    mesclados = publicacao.mesclar_fontes_externas(registros, saidas_recentes, destinos)

    # A coluna extra existe só no arquivo publicado: ela é o que a tela usa para
    # dizer que aquela saída tem selo do DOU e ainda não tem o do SIAPE.
    colunas_painel = colunas + [publicacao.COLUNA_SAIDA_NO_SIAPE]

    log = ler_json(ARQ_LOG)
    log_final = publicacao.acrescentar_saidas_do_dou(log, mesclados) if log else {}
    if not log:
        print(f"! {ARQ_LOG.relative_to(RAIZ)} não existe — a página de histórico sai vazia.")

    # === Resumo, para quem lê o log do deploy ===
    saidas_antes = sum(1 for r in registros if r.get("MES_SAIDA"))
    saidas_depois = sum(1 for r in mesclados if r.get("MES_SAIDA"))
    so_do_dou = sum(1 for r in mesclados if r.get(publicacao.COLUNA_SAIDA_NO_SIAPE) == "NÃO")
    motivos_completados = sum(
        1
        for antes, depois in zip(registros, mesclados)
        if not antes.get("MOTIVO_SAIDA") and depois.get("MOTIVO_SAIDA")
        and depois.get(publicacao.COLUNA_SAIDA_NO_SIAPE) != "NÃO"
    )
    destinos_antes = sum(1 for r in registros if r.get("ORGAO_DESTINO"))
    destinos_depois = sum(1 for r in mesclados if r.get("ORGAO_DESTINO"))

    print(f"Pessoas          : {len(registros)}")
    print(f"Saídas           : {saidas_antes} no SIAPE  ->  {saidas_depois} com o DOU "
          f"(+{saidas_depois - saidas_antes} que só o DOU conhece)")
    print(f"  sobrepostas    : {so_do_dou} com selo DOU e sem selo SIAPE")
    print(f"  motivo completado por ato, sem mudar a competência: {motivos_completados}")
    print(f"Destinos         : {destinos_antes} do DOU/curadoria  ->  {destinos_depois} "
          f"(+{destinos_depois - destinos_antes} do ranking/diário/busca)")
    if log_final:
        print(f"Histórico        : {log_final['totalChangeCount']} mudanças em "
              f"{len(log_final['history'])} competências, até {log_final['ultimoMes']}")

    if args.diagnostico:
        print()
        print("(--diagnostico: nada foi gravado)")
        return 0

    gravar_csv(ARQ_PAINEL, colunas_painel, mesclados)
    print()
    print(f"  gravado: {ARQ_PAINEL.relative_to(RAIZ)}")
    if log_final:
        ARQ_ALTERACOES.parent.mkdir(parents=True, exist_ok=True)
        ARQ_ALTERACOES.write_text(
            json.dumps(log_final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"  gravado: {ARQ_ALTERACOES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
