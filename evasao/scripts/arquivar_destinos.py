#!/usr/bin/env python3
"""
Arquiva o ato de nomeação de quem já tem destino do DOU, mas ainda sem cópia.

Entrada : data/dou/por_pessoa.csv   — as linhas com FONTE_DESTINO = DOU
Saída   : data/dou/atos_destino.csv — o índice dos atos de chegada (D30)
          data/dou/atos_destino/    — a cópia de cada ato
          data/dou/por_pessoa.csv   — preenche ATO_DESTINO_ARQUIVO

POR QUE ESTE SCRIPT EXISTE. O `enriquecer_saidas.py` passou a arquivar o ato de
chegada no momento em que o encontra (D30), sem requisição nova — o texto já está
em mãos. Mas os destinos achados ANTES disso ficaram só com a URL, e o crawler
não volta neles: ele pula quem já tem resposta, e mandá-lo refazer custaria ~50
minutos de busca por nome para reencontrar atos que já se sabe quais são.

Aqui a conta é outra: uma requisição por ATO, direto na página dele, sem busca.

O QUE FICA VAZIO, E POR QUÊ. Quem chega por aqui não tem o resultado da busca,
então SEÇÃO, EDIÇÃO e PÁGINA não são preenchidas — a cópia arquivada traz todas,
e nenhuma tela as usa. A hierarquia crua do órgão também fica vazia: ela serve
para conferir de onde saiu o nome publicado, e preenchê-la com o órgão que já
está no `por_pessoa.csv` seria repetir a resposta no lugar da prova.

IDEMPOTENTE. Roda de novo sem baixar nada: quem já está no índice é pulado, a não
ser com `--refazer`.

Uso:
    python arquivar_destinos.py
    python arquivar_destinos.py --limite 5    # experimenta em 5
    python arquivar_destinos.py --refazer     # rebaixa tudo
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import atos
import atos_destino
import dou

RAIZ = Path(__file__).resolve().parent.parent


def ler_csv(caminho: Path) -> tuple[list[dict], list[str]]:
    if not caminho.is_file():
        return [], []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=";")
        linhas = [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in leitor
        ]
        return linhas, [(c or "").strip() for c in (leitor.fieldnames or [])]


def para_pubdate(iso: str) -> str:
    """`AAAA-MM-DD` -> `DD/MM/AAAA`, que é como `dou.data_iso` espera receber."""
    partes = (iso or "").split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Arquiva os atos de nomeação já identificados.")
    parser.add_argument("--limite", type=int, help="Processa no máximo N atos.")
    parser.add_argument("--refazer", action="store_true", help="Rebaixa o que já está no índice.")
    parser.add_argument("--sem-cache", action="store_true", help="Ignora o cache do DOU.")
    args = parser.parse_args()

    pessoas, colunas = ler_csv(atos.ARQ_POR_PESSOA)
    if not pessoas:
        print(f"! {atos.ARQ_POR_PESSOA.relative_to(RAIZ)} está vazio ou não existe.")
        return 1

    if atos_destino.COLUNA_ARQUIVO not in colunas:
        colunas = colunas + [atos_destino.COLUNA_ARQUIVO]

    indice = atos_destino.ler()

    fila = [
        p for p in pessoas
        if p.get("FONTE_DESTINO") == "DOU" and p.get("URL_DESTINO")
        and (args.refazer or not p.get(atos_destino.COLUNA_ARQUIVO))
    ]
    if args.limite:
        fila = fila[: args.limite]

    print(f"Destinos do DOU no arquivo: "
          f"{sum(1 for p in pessoas if p.get('FONTE_DESTINO') == 'DOU' and p.get('URL_DESTINO'))}")
    print(f"Índice de destinos        : {len(indice)} ato(s)")
    print(f"A arquivar                : {len(fila)}")
    if not fila:
        print("Nada a fazer.")
        return 0
    print(f"Pausa entre requisições   : {dou.PAUSA_SEGUNDOS}s")
    print()

    arquivados = falhas = 0
    for numero, pessoa in enumerate(fila, start=1):
        url_title = pessoa["URL_DESTINO"].replace(dou.BASE_ATO, "")
        print(f"[{numero}/{len(fila)}] {pessoa['NOME'][:40]:<40} -> {pessoa['ORGAO_DESTINO'][:34]}")

        pagina, texto = dou.baixar_ato(url_title, usar_cache=not args.sem_cache)
        if not texto:
            print("        ! não foi possível ler o ato — fica só com a URL")
            falhas += 1
            continue

        # O que se sabe sem a busca: a chave e a data. O título sai da própria
        # página; o órgão vem do que já estava decidido no `por_pessoa.csv`.
        resultado = {"urlTitle": url_title, "pubDate": para_pubdate(pessoa.get("DATA_DESTINO", ""))}
        linha = atos_destino.registrar(
            indice, resultado, texto,
            id_servidor=pessoa["ID_SERVIDOR_PORTAL"],
            nome=pessoa.get("NOME", ""),
            pagina_html=pagina,
            orgao_destino=pessoa.get("ORGAO_DESTINO", ""),
        )
        if linha is None:
            print("        ! ato sem identificador no in.gov.br")
            falhas += 1
            continue

        pessoa[atos_destino.COLUNA_ARQUIVO] = linha["ARQUIVO"]
        arquivados += 1
        print(f"        {linha['TITULO'][:66] or '(sem título legível)'}")

        # Grava a cada ato: uma interrupção no meio de 130 não pode jogar fora o
        # que já foi baixado — o mesmo motivo do `enriquecer_saidas.py`.
        atos_destino.gravar(indice)
        with open(atos.ARQ_POR_PESSOA, "w", encoding="utf-8", newline="") as fh:
            escritor = csv.DictWriter(fh, fieldnames=colunas, delimiter=";",
                                      extrasaction="ignore", restval="")
            escritor.writeheader()
            escritor.writerows(pessoas)

    print()
    print(f"Arquivados: {arquivados}")
    if falhas:
        print(f"Sem cópia : {falhas} (continuam com a URL, que é o que havia antes)")
    print(f"Gravado   : {atos_destino.ARQ_INDICE.relative_to(RAIZ)} ({len(indice)} atos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
