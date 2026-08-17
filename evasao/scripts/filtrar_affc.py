#!/usr/bin/env python3
"""
Filtra os CSVs de Cadastro do Portal da Transparência, mantendo apenas as linhas
do cargo AUDITOR FEDERAL DE FINANCAS E CONTROLE (AFFC).

Contexto: os arquivos `AAAAMM_Cadastro.csv` do portal trazem TODOS os servidores
civis federais (~420 MB e ~600 mil linhas cada). O observatório só precisa dos
AFFC da CGU, que são algumas milhares de linhas por mês.

O script faz DUAS reduções, e a segunda passou a existir na D32, quando o
snapshot deixou de ser arquivo de trabalho local e virou dado versionado:

  1. LINHAS  — só as do cargo AFFC (de ~600 mil para ~2,5 mil);
  2. COLUNAS — só as 16 que a derivação lê (`painel.COLUNAS_NO_SNAPSHOT`),
     de 43. Uma das 27 descartadas é o CPF: mascarado (`***.930.011-**`), mas
     com 6 dos 11 dígitos ao lado do nome completo. O observatório não precisa
     dele, e o snapshot vai para repositório PÚBLICO — não republicar é decisão,
     não economia. Saem junto função comissionada, afastamentos e diplomas.

A saída é comprimida: 1.442 KB por competência viram 89 KB. A lista de colunas
NÃO é escrita aqui — vem de `painel.py`, que é quem sabe o que a derivação lê.

Entrada : AAAAMM_Cadastro.csv              (bruto do Portal, ~420 MB, efêmero)
Saída   : ../data/siape/AAAAMM.csv.gz      (versionado, ~89 KB)

ATENÇÃO: por padrão o arquivo original é APAGADO depois que o snapshot é gravado
com sucesso. Use --manter-original para conservá-lo, ou --dry-run para simular.

A pasta de ENTRADA (`evasao/data/historico_transparencia_cgu/`) é ignorada pelo
git — os CSVs do portal somam dezenas de GB e são descartáveis. A pasta de SAÍDA
(`evasao/data/siape/`) é versionada.

Uso (de qualquer diretório):
    python filtrar_affc.py                      # processa a pasta padrão
    python filtrar_affc.py --dry-run            # só relatório, não escreve nada
    python filtrar_affc.py --manter-original    # não apaga os originais
    python filtrar_affc.py 202207_Cadastro.csv  # só um arquivo (nome relativo à pasta)
    python filtrar_affc.py --pasta outra/pasta  # processa outra pasta
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import gzip
import time
import unicodedata
from pathlib import Path

import painel

# O script está em evasao/scripts/, então a raiz do projeto Vite é um nível acima.
RAIZ = Path(__file__).resolve().parent.parent
PASTA_PADRAO = RAIZ / "data" / "historico_transparencia_cgu"

# Cargo alvo, já normalizado (ver `normalizar`). O valor observado nos arquivos é
# "AUDITOR FEDERAL DE FINANCAS E CONTROLE", sem acentos e em caixa alta, mas a
# normalização protege contra variações de acento/espaçamento entre competências.
CARGO_ALVO = "AUDITOR FEDERAL DE FINANCAS E CONTROLE"

COLUNA_CARGO = "DESCRICAO_CARGO"

PASTA_SAIDA = RAIZ / "data" / "siape"
PADRAO_ENTRADA = "*_Cadastro.csv"

# O portal publica em ISO-8859-1. latin-1 nunca falha na decodificação (mapeia
# todos os 256 bytes), então não há risco de perder linha por erro de encoding.
ENCODING_ENTRADA = "latin-1"
ENCODING_SAIDA = "utf-8"

SEPARADOR = ";"


def normalizar(texto: str) -> str:
    """Caixa alta, sem acentos, sem espaços duplicados."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())


def formatar_bytes(n: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} GB"


def listar_entradas(pasta: Path, nomes: list[str]) -> list[Path]:
    if nomes:
        caminhos = [pasta / nome if not Path(nome).is_absolute() else Path(nome) for nome in nomes]
        faltando = [c for c in caminhos if not c.is_file()]
        if faltando:
            sys.exit("Arquivo não encontrado: " + ", ".join(str(c) for c in faltando))
        return caminhos

    return sorted(pasta.glob(PADRAO_ENTRADA))


def competencia(entrada: Path) -> str:
    """`202207_Cadastro.csv` -> `202207`. O nome do Portal sempre começa assim."""
    return entrada.name[:6]


def caminho_do_snapshot(entrada: Path) -> Path:
    return PASTA_SAIDA / f"{competencia(entrada)}.csv.gz"


def filtrar_arquivo(entrada: Path, dry_run: bool, manter_original: bool) -> tuple[int, int]:
    """Devolve (linhas_lidas, linhas_mantidas)."""
    saida = caminho_do_snapshot(entrada)
    saida.parent.mkdir(parents=True, exist_ok=True)
    # Grava num temporário e só renomeia no fim: se o script for interrompido,
    # não fica um arquivo pela metade parecendo completo.
    temporario = saida.with_suffix(saida.suffix + ".parcial")

    alvo = normalizar(CARGO_ALVO)
    lidas = 0
    mantidas = 0
    inicio = time.time()

    fh_saida = None
    escritor = None
    try:
        with open(entrada, encoding=ENCODING_ENTRADA, newline="") as fh_entrada:
            leitor = csv.reader(fh_entrada, delimiter=SEPARADOR, quotechar='"')

            try:
                cabecalho = next(leitor)
            except StopIteration:
                print(f"  ! {entrada.name} está vazio — pulando.")
                return 0, 0

            if COLUNA_CARGO not in cabecalho:
                print(
                    f"  ! {entrada.name} não tem a coluna {COLUNA_CARGO} — pulando "
                    f"(colunas: {len(cabecalho)})."
                )
                return 0, 0

            # As colunas que sobrevivem, na ordem em que `painel.py` as pede. Uma
            # que o Portal deixe de publicar aborta AQUI, e não meses depois com
            # a coluna vazia no site.
            faltando = [c for c in painel.COLUNAS_NO_SNAPSHOT if c not in cabecalho]
            if faltando:
                print(f"  ! {entrada.name} nao tem: {', '.join(faltando)} — pulando.")
                return 0, 0

            indice_cargo = cabecalho.index(COLUNA_CARGO)
            indices = [cabecalho.index(c) for c in painel.COLUNAS_NO_SNAPSHOT]

            if not dry_run:
                fh_saida = gzip.open(
                    temporario, "wt", encoding=ENCODING_SAIDA, newline="", compresslevel=9
                )
                escritor = csv.writer(
                    fh_saida, delimiter=SEPARADOR, quotechar='"', quoting=csv.QUOTE_ALL
                )
                escritor.writerow(list(painel.COLUNAS_NO_SNAPSHOT))

            for linha in leitor:
                lidas += 1
                if len(linha) <= indice_cargo:
                    continue  # linha truncada/corrompida: não dá para classificar
                if normalizar(linha[indice_cargo]) == alvo:
                    mantidas += 1
                    if escritor is not None:
                        escritor.writerow(
                            [linha[i] if i < len(linha) else "" for i in indices]
                        )
    finally:
        if fh_saida is not None:
            fh_saida.close()

    duracao = time.time() - inicio

    if dry_run:
        print(
            f"  [simulação] {entrada.name}: {lidas:,} linhas lidas, "
            f"{mantidas:,} AFFC ({duracao:.1f}s) — nada gravado, nada apagado."
        )
        return lidas, mantidas

    # Só substitui o definitivo depois de fechar o temporário por completo.
    os.replace(temporario, saida)

    tamanho_saida = saida.stat().st_size
    tamanho_entrada = entrada.stat().st_size
    print(
        f"  {entrada.name}: {lidas:,} linhas -> {mantidas:,} AFFC "
        f"({formatar_bytes(tamanho_entrada)} -> {formatar_bytes(tamanho_saida)}, {duracao:.1f}s)"
    )

    if mantidas == 0:
        print(
            f"  ! Nenhuma linha AFFC em {entrada.name}. O original NÃO será apagado "
            f"— confira o arquivo antes."
        )
        return lidas, mantidas

    if manter_original:
        print(f"    original conservado: {entrada.name}")
        return lidas, mantidas

    # Só apaga com a saída já no lugar, não vazia e com pelo menos uma linha AFFC.
    if saida.is_file() and tamanho_saida > 0:
        entrada.unlink()
        print(f"    original apagado: {entrada.name}")
    else:
        print(f"  ! Saída inválida para {entrada.name} — original preservado.")

    return lidas, mantidas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filtra os CSVs de Cadastro do Portal da Transparência, mantendo só os AFFC."
    )
    parser.add_argument(
        "arquivos",
        nargs="*",
        help="Arquivos específicos. Sem isso, processa todo *_Cadastro.csv da pasta do script.",
    )
    parser.add_argument(
        "--pasta",
        type=Path,
        default=PASTA_PADRAO,
        help=f"Pasta a processar (padrão: {PASTA_PADRAO.name}/ dentro de evasao/data).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Conta as linhas e mostra o resultado, sem gravar nem apagar nada.",
    )
    parser.add_argument(
        "--manter-original",
        action="store_true",
        help="Não apaga o CSV original depois de gerar o filtrado.",
    )
    args = parser.parse_args()

    # Os campos do portal são curtos, mas o limite padrão do módulo csv é baixo
    # para arquivos deste porte; uma linha malformada derrubaria a execução.
    csv.field_size_limit(10 * 1024 * 1024)

    pasta = args.pasta.resolve()
    if not pasta.is_dir():
        sys.exit(f"Pasta não encontrada: {pasta}")

    entradas = listar_entradas(pasta, args.arquivos)
    if not entradas:
        print(f"Nenhum arquivo {PADRAO_ENTRADA} para processar em {pasta}")
        return 0

    total_bytes = sum(caminho.stat().st_size for caminho in entradas)

    print(f"Entrada : {pasta}")
    print(f"Saída   : {PASTA_SAIDA}")
    print(f"Arquivos: {len(entradas)} ({formatar_bytes(total_bytes)})")
    print(f"Cargo   : {CARGO_ALVO}")
    if args.dry_run:
        print("Modo    : SIMULAÇÃO — nada será gravado nem apagado.")
    elif args.manter_original:
        print("Modo    : gravar o filtrado e CONSERVAR os originais.")
    else:
        print("Modo    : gravar o filtrado e APAGAR os originais.")
    print()

    total_lidas = 0
    total_mantidas = 0
    processados = 0

    for indice, entrada in enumerate(entradas, start=1):
        if caminho_do_snapshot(entrada).is_file() and not args.dry_run:
            print(f"[{indice}/{len(entradas)}] {entrada.name}: snapshot já existe — pulando.")
            continue

        print(f"[{indice}/{len(entradas)}] processando {entrada.name}...")
        lidas, mantidas = filtrar_arquivo(entrada, args.dry_run, args.manter_original)
        total_lidas += lidas
        total_mantidas += mantidas
        processados += 1

    print()
    print(f"Arquivos processados: {processados}")
    print(f"Linhas lidas        : {total_lidas:,}")
    print(f"Linhas AFFC         : {total_mantidas:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
