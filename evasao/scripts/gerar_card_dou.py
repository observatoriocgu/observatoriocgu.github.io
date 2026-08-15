#!/usr/bin/env python3
"""
Gera o JSON do card "dias sem perder um Auditor" a partir do índice de atos.

Entrada : data/atos_dou.csv       — o índice único (`atos.py`, alimentado pelos
                                    dois crawlers)
          data/serie_mensal.csv   — só para saber a última competência do SIAPE
          data/varredura_dou.txt  — até que dia o DOU já foi varrido
Saída   : public/dias_sem_perder_affc.json

SEM REDE E DETERMINÍSTICO. Este script só derruba dado de arquivo em arquivo:
rodar duas vezes seguidas produz byte a byte o mesmo JSON. Foi por isso que ele
ficou separado do `varrer_dou.py` — e também porque assim o workflow diário
consegue rodá-lo: o `construir_painel.py` depende dos snapshots do Portal, que
não estão no Git, e portanto não existe no CI.

O JSON guarda DATAS, nunca a contagem de dias: quem calcula "faz N dias" é o
navegador, na hora de renderizar. Assim o card não congela no dia em que o
crawler rodou — e continua correto mesmo se a varredura falhar por alguns dias.

O CAMPO QUE EXPLICA A DIVERGÊNCIA
---------------------------------
`atosDepoisDaUltimaCompetencia` conta os atos que o DOU já publicou depois do
último mês que o SIAPE entregou. Não é erro nem pendência: é a defasagem do
Portal da Transparência, de ~2 meses. Era ela que fazia o card mostrar agosto
enquanto a lista de "últimas saídas registradas" parava em junho, e as duas
estavam certas. Agora o número está na tela, em vez de virar suspeita.

Uso:
    python gerar_card_dou.py
    python gerar_card_dou.py --diagnostico   # imprime, não grava
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import atos
import dou

RAIZ = Path(__file__).resolve().parent.parent
ARQ_SERIE = RAIZ / "data" / "serie_mensal.csv"
ARQ_JSON = RAIZ / "public" / "dias_sem_perder_affc.json"

# O card mostra três tipos. `dou.classificar` também reconhece falecimento, que
# entra no `dados.csv` pelo `enriquecer_saidas.py`; aqui ele é deixado de fora de
# propósito — o card é um contador de dias, não é lugar para essa informação.
TIPOS = ("vacancia", "aposentadoria", "exoneracao")


def ultima_competencia() -> str:
    """A competência mais nova do SIAPE, lida da série mensal. Vazio se não der."""
    if not ARQ_SERIE.is_file():
        return ""
    with open(ARQ_SERIE, encoding="utf-8-sig", newline="") as fh:
        meses = [(linha.get("MES") or "").strip() for linha in csv.DictReader(fh, delimiter=";")]
    return max((m for m in meses if m), default="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o JSON do card a partir do índice de atos.")
    parser.add_argument("--diagnostico", action="store_true", help="Imprime o JSON, sem gravar.")
    args = parser.parse_args()

    indice = atos.ler()
    if not indice:
        print(f"{atos.ARQ_INDICE.name} está vazio ou não existe. "
              f"Rode `python varrer_dou.py` antes.")
        return 1

    recentes = atos.mais_recentes_por_tipo(indice, TIPOS)
    if not recentes:
        print("Nenhum ato dos tipos do card no índice. Nada foi gravado.")
        return 1

    mes_siape = ultima_competencia()
    adiantados = atos.posteriores_a_competencia(indice, mes_siape)
    varredura = atos.ler_varredura()

    mais_recente = max(recentes.values(), key=lambda l: (l["DATA_PUBLICACAO"], l["URL_TITLE"]))

    saida = {
        "fonte": "Diário Oficial da União — in.gov.br",
        "cargo": "Auditor Federal de Finanças e Controle",
        "orgao": "Controladoria-Geral da União",
        "varreduraAte": varredura.strftime("%Y-%m-%d") if varredura else "",
        "ultimaCompetenciaSiape": mes_siape,
        "atosDepoisDaUltimaCompetencia": len(adiantados),
        "dataMaisRecente": mais_recente["DATA_PUBLICACAO"],
        "tipoMaisRecente": mais_recente["TIPO"],
        "eventos": [
            {
                "tipo": linha["TIPO"],
                "rotulo": linha["ROTULO"],
                "titulo": linha["TITULO"],
                "dataPublicacao": linha["DATA_PUBLICACAO"],
                "secao": linha["SECAO"],
                "edicao": linha["EDICAO"],
                "pagina": linha["PAGINA"],
                "orgao": linha["ORGAO"],
                "urlDou": linha["URL"],
                "arquivo": linha["ARQUIVO"] or None,
            }
            for tipo in TIPOS
            if (linha := recentes.get(tipo))
        ],
    }

    print(f"Índice   : {len(indice)} ato(s) em {atos.ARQ_INDICE.name}")
    for tipo in TIPOS:
        linha = recentes.get(tipo)
        print(f"  {dou.ROTULOS[tipo]:<34} {linha['DATA_PUBLICACAO'] if linha else '(nenhum)'}")
    print(f"Mais recente: {mais_recente['ROTULO']} em {mais_recente['DATA_PUBLICACAO']}")
    if mes_siape:
        print(f"SIAPE até   : {mes_siape}  "
              f"({len(adiantados)} ato(s) do DOU ainda não confirmados por ele)")

    faltando = [t for t in TIPOS if t not in recentes]
    if faltando:
        print(f"! Sem ato de: {', '.join(dou.ROTULOS[t] for t in faltando)}")

    if args.diagnostico:
        print()
        print(json.dumps(saida, ensure_ascii=False, indent=2))
        return 0

    ARQ_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARQ_JSON.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"  gravado: {ARQ_JSON.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
