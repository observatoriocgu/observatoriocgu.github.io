#!/usr/bin/env python3
"""
Busca no Diário Oficial da União as saídas mais recentes de Auditores Federais
de Finanças e Controle (AFFC) da CGU e alimenta o card "dias sem perder um Auditor".

Três tipos de saída são rastreados, cada um com o seu ato mais recente:
  - vacancia      : vacância do cargo por posse em outro cargo inacumulável
  - aposentadoria : concessão de aposentadoria
  - exoneracao    : exoneração do cargo efetivo de AFFC

Saídas do script:
  - evasao/public/dias_sem_perder_affc.json      -> lido pela interface
  - evasao/data/dias_sem_perder_AFFC/*.html      -> o trecho do DOU de cada ato

O JSON guarda DATAS, nunca a contagem de dias: quem calcula "faz N dias" é o
navegador, na hora de renderizar. Assim o card não congela no dia em que o
crawler rodou.

DELIMITAÇÃO DE ESCOPO (D10 do PLANO.md): este crawler existe só para o número de
dias e os 3 links. Ele NÃO é fonte de contagem de evasões — para de varrer assim
que acha o ato mais recente de cada tipo, então nunca soube quantas saídas houve
no total. A série completa vem da base mensal do SIAPE (`construir_painel.py`).

Toda a mecânica de rede, busca e classificação mora em `dou.py`, compartilhada
com `enriquecer_saidas.py` e `concurso.py`.

Uso:
    python dou_saidas_affc.py --diagnostico   # mostra o que achou, não grava
    python dou_saidas_affc.py                 # grava JSON + HTMLs
    python dou_saidas_affc.py --meses 24      # varre mais fundo
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import dou

RAIZ = Path(__file__).resolve().parent.parent
DIR_ATOS = RAIZ / "data" / "dias_sem_perder_AFFC"
ARQUIVO_JSON = RAIZ / "public" / "dias_sem_perder_affc.json"

# Uma frase só — ver nota no cabeçalho de `dou.py`. A busca do DOU ignora acento
# e gênero, então esta frase também traz "Auditora Federal de Finanças e Controle".
FRASE_BUSCA = '"Auditor Federal de Finanças e Controle"'

# Janela de 15 dias: em janelas mensais alguns meses passam de 50 atos, que é o
# teto por resposta, e atos seriam perdidos silenciosamente.
DIAS_POR_JANELA = 15

# O card mostra três tipos. `dou.classificar` também sabe reconhecer falecimento,
# que entrou para o `enriquecer_saidas.py`; aqui ele é ignorado de propósito —
# o card não é lugar para essa informação.
TIPOS = ("vacancia", "aposentadoria", "exoneracao")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Busca no DOU as saídas mais recentes de AFFC da CGU."
    )
    parser.add_argument(
        "--meses", type=int, default=12, help="Até quantos meses atrás varrer (padrão: 12)."
    )
    parser.add_argument(
        "--diagnostico",
        action="store_true",
        help="Mostra os candidatos e a classificação, sem gravar JSON nem HTML.",
    )
    parser.add_argument(
        "--sem-cache",
        action="store_true",
        help="Ignora o cache em disco e rebaixa tudo do in.gov.br.",
    )
    args = parser.parse_args()
    usar_cache = not args.sem_cache

    encontrados: dict[str, dict] = {}
    fim = date.today()
    janelas = max(1, (args.meses * 30) // DIAS_POR_JANELA)

    print(f"Frase   : {FRASE_BUSCA}")
    print(f"Órgão   : {dou.ORGAO_CGU}")
    print(f"Período : até {args.meses} meses atrás, em janelas de {DIAS_POR_JANELA} dias")
    if args.diagnostico:
        print("Modo    : DIAGNÓSTICO — nada será gravado.")
    print()

    vistos: set[str] = set()

    for numero in range(janelas):
        if len(encontrados) == len(TIPOS):
            break

        inicio = fim - timedelta(days=DIAS_POR_JANELA - 1)
        resultados = dou.buscar(FRASE_BUSCA, inicio, fim, usar_cache=usar_cache)
        candidatos = [r for r in resultados if dou.e_da_cgu(r)]
        print(
            f"[{numero + 1}/{janelas}] {inicio:%d/%m/%Y}–{fim:%d/%m/%Y}: "
            f"{len(resultados)} atos, {len(candidatos)} da CGU"
        )

        for resultado in candidatos:
            chave = resultado.get("urlTitle", "")
            if not chave or chave in vistos:
                continue
            vistos.add(chave)

            if all(t in encontrados for t in TIPOS):
                break

            _, texto = dou.baixar_ato(chave, usar_cache=usar_cache)
            if not texto:
                continue
            tipo = dou.classificar(texto)
            # `tipo not in TIPOS` descarta o falecimento, que este card não mostra.
            if tipo is None or tipo not in TIPOS or tipo in encontrados:
                continue

            registro = {
                "tipo": tipo,
                "rotulo": dou.ROTULOS[tipo],
                "titulo": resultado["title"],
                "dataPublicacao": dou.data_iso(resultado),
                "secao": resultado.get("pubName"),
                "edicao": resultado.get("editionNumber"),
                "pagina": resultado.get("numberPage"),
                "orgao": resultado.get("hierarchyStr"),
                "urlDou": dou.BASE_ATO + chave,
                "arquivo": None,
                "trecho": texto[:400],
            }

            if not args.diagnostico:
                registro["arquivo"] = dou.salvar_ato(resultado, tipo, texto, DIR_ATOS)

            encontrados[tipo] = registro
            print(f"    -> {dou.ROTULOS[tipo]}: {resultado['pubDate']} | {resultado['title'][:60]}")

        fim = inicio - timedelta(days=1)

    print()
    if not encontrados:
        print("Nenhuma saída de AFFC encontrada no período. Nada foi gravado.")
        return 1

    faltando = [t for t in TIPOS if t not in encontrados]
    if faltando:
        print(f"Sem ato recente para: {', '.join(dou.ROTULOS[t] for t in faltando)}")

    mais_recente = max(encontrados.values(), key=lambda r: r["dataPublicacao"])
    print(f"Mais recente: {mais_recente['rotulo']} em {mais_recente['dataPublicacao']}")

    if args.diagnostico:
        print()
        print("=== classificação (confira antes de publicar) ===")
        for tipo in TIPOS:
            registro = encontrados.get(tipo)
            if not registro:
                print(f"  {dou.ROTULOS[tipo]}: (nenhum)")
                continue
            print(f"  {dou.ROTULOS[tipo]} — {registro['dataPublicacao']}")
            print(f"    {registro['trecho'][:260]}")
        return 0

    ARQUIVO_JSON.parent.mkdir(parents=True, exist_ok=True)
    saida = {
        "geradoEm": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fonte": "Diário Oficial da União — in.gov.br",
        "cargo": "Auditor Federal de Finanças e Controle",
        "orgao": "Controladoria-Geral da União",
        "dataMaisRecente": mais_recente["dataPublicacao"],
        "tipoMaisRecente": mais_recente["tipo"],
        "eventos": [encontrados[t] for t in TIPOS if t in encontrados],
    }
    ARQUIVO_JSON.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"JSON gravado: {ARQUIVO_JSON.relative_to(RAIZ)}")
    print(f"Atos salvos : {DIR_ATOS.relative_to(RAIZ)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
