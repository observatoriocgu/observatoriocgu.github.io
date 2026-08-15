#!/usr/bin/env python3
"""
Gera o JSON do card "dias sem perder um Auditor" a partir do índice de atos.

Entrada : data/atos_dou.csv       — o índice único (`atos.py`, alimentado pelos
                                    dois crawlers)
          data/dados.csv          — para saber quais atos o SIAPE já confirmou
          data/serie_mensal.csv   — só para saber a última competência do SIAPE
          data/varredura_dou.txt  — até que dia o DOU já foi varrido
Saída   : public/atos_dou.json

SEM REDE E DETERMINÍSTICO. Este script só derruba dado de arquivo em arquivo:
rodar duas vezes seguidas produz byte a byte o mesmo JSON. Foi por isso que ele
ficou separado do `varrer_dou.py` — e também porque assim o workflow diário
consegue rodá-lo: o `construir_painel.py` depende dos snapshots do Portal, que
não estão no Git, e portanto não existe no CI.

O JSON guarda DATAS, nunca a contagem de dias: quem calcula "faz N dias" é o
navegador, na hora de renderizar. Assim o card não congela no dia em que o
crawler rodou — e continua correto mesmo se a varredura falhar por alguns dias.

AS SAÍDAS QUE O SIAPE AINDA NÃO CONFIRMOU
-----------------------------------------
`saidasRecentes` traz as saídas que só o DOU conhece: o ato está publicado, com
nome lido do próprio texto (`dou.nome_do_ato`), e o Portal da Transparência
ainda não entregou a competência que mostraria a ausência. São elas que fazem a
lista de últimas saídas do painel chegar até hoje, em vez de parar dois meses
atrás.

Cada uma leva `idServidor` quando dá para casar o ato com alguém do `dados.csv`
— por nome, e só quando a matrícula do ato não CONFLITA com a máscara do Portal.
O casamento é feito aqui, e não no navegador, por dois motivos: é aqui que a
matrícula existe, e é aqui que dá para descartar homônimo (D12). Com o id, a
interface sabe que aquela saída já está na lista do SIAPE e não a mostra duas
vezes — foi o que aconteceu com as saídas provisórias de 202606, que o crawler
por nome pula de propósito e a varredura por frase acha assim mesmo.

O que NÃO acontece aqui: nada disso entra em contagem de evasão. Quem conta é o
SIAPE, pela ausência a partir da última presença (D11, D13). Contar ato dobraria
quem tem dois atos e incluiria quem já estava fora do quadro.

Uso:
    python gerar_card_dou.py
    python gerar_card_dou.py --diagnostico   # imprime, não grava
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import atos
import dou

RAIZ = Path(__file__).resolve().parent.parent
ARQ_SERIE = RAIZ / "data" / "serie_mensal.csv"
ARQ_DADOS = RAIZ / "data" / "dados.csv"
ARQ_JSON = RAIZ / "public" / "atos_dou.json"

# O card mostra três tipos. `dou.classificar` também reconhece falecimento, que
# entra no `dados.csv` pelo `enriquecer_saidas.py`; aqui ele é deixado de fora de
# propósito — o card é um contador de dias, não é lugar para essa informação.
TIPOS = ("vacancia", "aposentadoria", "exoneracao")

# Até quando um ato ainda não confirmado pelo SIAPE vale como "saída recente".
# O Portal atrasa ~2 meses; 12 é folga larga. O limite existe para que um ato
# antigo que nunca casou com ninguém não fique para sempre no topo da lista como
# se tivesse acabado de acontecer.
MESES_DE_SAIDA_RECENTE = 12


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        return [
            {(k or "").strip(): (v or "").strip() for k, v in linha.items()}
            for linha in csv.DictReader(fh, delimiter=";")
        ]


def ultima_competencia() -> str:
    """A competência mais nova do SIAPE, lida da série mensal. Vazio se não der."""
    meses = [(linha.get("MES") or "").strip() for linha in ler_csv(ARQ_SERIE)]
    return max((m for m in meses if m), default="")


def recuar_meses(mes: str, quantidade: int) -> str:
    """`AAAAMM` menos N meses. Vazio se `mes` não servir."""
    if len(mes) != 6 or not mes.isdigit():
        return ""
    total = int(mes[:4]) * 12 + int(mes[4:]) - 1 - quantidade
    return f"{total // 12:04d}{total % 12 + 1:02d}"


def casar_com_pessoa(linha: dict, por_nome: dict[str, list[dict]]) -> str:
    """
    O `ID_SERVIDOR_PORTAL` de quem o ato trata, quando dá para saber. Vazio se não.

    Nome NÃO é chave (D12), então duas guardas: nome que casa com mais de uma
    pessoa é descartado, e matrícula do ato que conflita com a máscara do Portal
    elimina o casamento. Na dúvida, vazio — o efeito de errar aqui é mostrar a
    mesma saída duas vezes na lista, o que é bem menos grave que colar o ato de
    uma pessoa no nome de outra.
    """
    if linha.get("ID_SERVIDOR_PORTAL"):
        return linha["ID_SERVIDOR_PORTAL"]

    candidatos = por_nome.get(dou.normalizar(linha.get("NOME", "")), [])
    if len(candidatos) != 1:
        return ""

    pessoa = candidatos[0]
    matricula_ato = linha.get("MATRICULA_SIAPE", "")
    mascara = re.sub(r"\D", "", pessoa.get("MATRICULA", ""))
    if matricula_ato and mascara and not matricula_ato.startswith(mascara):
        return ""
    return pessoa["ID_SERVIDOR_PORTAL"]


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
    varredura = atos.ler_varredura()

    pessoas = ler_csv(ARQ_DADOS)
    por_nome: dict[str, list[dict]] = {}
    for pessoa in pessoas:
        por_nome.setdefault(dou.normalizar(pessoa["NOME"]), []).append(pessoa)
    ja_saiu = {p["ID_SERVIDOR_PORTAL"] for p in pessoas if p.get("MES_SAIDA")}

    # Atos que o painel ainda não está usando, em dois casos distintos:
    #
    #   jaNoSiape = false — saída que SÓ o DOU conhece. O ato existe e o cadastro
    #     ainda não mostrou a ausência. Vira saída nova no painel.
    #
    #   jaNoSiape = true  — o SIAPE já mostrou a pessoa sumir, mas ninguém achou
    #     o ato dela, e ela aparece como "saída sem ato identificado". Acontece
    #     com a saída PROVISÓRIA: `enriquecer_saidas.py` não a consulta no DOU de
    #     propósito (pode ser uma ressurreição), e a varredura por frase acha o
    #     ato assim mesmo. Aqui o ato só COMPLETA o motivo — a competência da
    #     saída continua sendo a do SIAPE, e nada é contado duas vezes.
    #
    # Quem já tem motivo não entra: aquilo o `enriquecer_saidas.py` resolveu.
    sem_motivo = {p["ID_SERVIDOR_PORTAL"] for p in pessoas if p.get("MES_SAIDA") and not p.get("MOTIVO_SAIDA")}
    corte = recuar_meses(mes_siape, MESES_DE_SAIDA_RECENTE)
    saidas_recentes = []
    for linha in atos.posteriores_a_competencia(indice, corte):
        identificador = casar_com_pessoa(linha, por_nome)
        ja_no_siape = identificador in ja_saiu
        if ja_no_siape and identificador not in sem_motivo:
            continue
        saidas_recentes.append(
            {
                "nome": linha["NOME"],
                "tipo": linha["TIPO"],
                "rotulo": linha["ROTULO"],
                "dataPublicacao": linha["DATA_PUBLICACAO"],
                "titulo": linha["TITULO"],
                "urlDou": linha["URL"],
                "arquivo": linha["ARQUIVO"] or None,
                "idServidor": identificador,
                "jaNoSiape": ja_no_siape,
            }
        )
    saidas_recentes.sort(key=lambda s: s["dataPublicacao"], reverse=True)

    mais_recente = max(recentes.values(), key=lambda l: (l["DATA_PUBLICACAO"], l["URL_TITLE"]))

    saida = {
        "fonte": "Diário Oficial da União — in.gov.br",
        "cargo": "Auditor Federal de Finanças e Controle",
        "orgao": "Controladoria-Geral da União",
        "varreduraAte": varredura.strftime("%Y-%m-%d") if varredura else "",
        "ultimaCompetenciaSiape": mes_siape,
        "saidasRecentes": saidas_recentes,
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
        print(f"SIAPE até   : {mes_siape}")
    novas = [s for s in saidas_recentes if not s["jaNoSiape"]]
    completam = [s for s in saidas_recentes if s["jaNoSiape"]]
    print(f"Saídas que só o DOU conhece: {len(novas)}")
    for recente in novas:
        alerta = "" if recente["nome"] else "   <- SEM NOME LEGÍVEL NO ATO"
        print(f"  {recente['dataPublicacao']} {recente['tipo'][:13]:<13} "
              f"{recente['nome'] or '(sem nome)'}{alerta}")
    if completam:
        print(f"Atos que completam o motivo de quem o SIAPE já mostrou sair: {len(completam)}")
        for recente in completam:
            print(f"  {recente['dataPublicacao']} {recente['tipo'][:13]:<13} {recente['nome']}")

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
