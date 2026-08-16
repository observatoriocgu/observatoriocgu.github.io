#!/usr/bin/env python3
"""
Varre o Diário Oficial da União por FRASE e registra toda saída de AFFC da CGU.

Entrada : in.gov.br, busca pela frase "Auditor Federal de Finanças e Controle"
Saída   : data/atos_dou.csv       — o índice único dos atos (ver `atos.py`)
          data/saidas_dou/*.html  — cópia arquivada de cada ato
          data/varredura_dou.txt  — até que dia esta varredura já cobriu

É o sucessor do `dou_saidas_affc.py` — que a D19 removeu em 15/08/2026, então não
procure o arquivo —, e a diferença está em duas linhas do
antigo cabeçalho dele: *"para de varrer assim que acha o ato mais recente de
cada tipo, então nunca soube quantas saídas houve no total"*. Essa parada
precoce fazia sentido quando o único cliente era o card. Agora não: o mesmo
crawl que descobre a data mais recente pode registrar tudo o que passa na
frente, e aí a varredura por frase e a varredura por nome deixam de ser duas
verdades sobre o mesmo assunto.

POR QUE ESTA VARREDURA É NECESSÁRIA, se `enriquecer_saidas.py` já busca no DOU
-----------------------------------------------------------------------------
Porque aquela parte do `dados.csv`, que parte do SIAPE, que vem do Portal da
Transparência com ~2 meses de atraso. Em 15/08/2026 a última competência do
SIAPE era 202606: nenhuma busca por nome poderia achar a vacância publicada em
11/08/2026, porque a pessoa ainda constava do quadro. Só a busca por frase lê o
DOU direto do dia.

As duas continuam existindo e fazendo coisas diferentes:

  frase -> QUANDO e O QUÊ, no dia da publicação, sem saber de quem
  nome  -> DE QUEM, com id do SIAPE, quando o Portal alcançar aquele mês

e as duas escrevem no mesmo índice. A linha ganha `ID_SERVIDOR_PORTAL` quando a
segunda alcança a primeira.

O QUE ESTA VARREDURA NÃO É
--------------------------
Não é fonte de contagem de evasão (D10, D11, D13). Quem conta quantos Auditores
saíram é a base mensal do SIAPE, pela ausência a partir da última presença. Um
ato do DOU prova que uma saída foi publicada; não prova que o quadro diminuiu
naquele mês, e contar ato dobraria quem tem dois atos.

Uso:
    python varrer_dou.py                      # incremental, desde a última varredura
    python varrer_dou.py --diagnostico        # mostra o que acharia, não grava
    python varrer_dou.py --desde 2022-06-14   # backfill completo (demora)
    python varrer_dou.py --meses 12           # janela fixa, ignorando a marca
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

import atos
import dou

# Janela de 15 dias: em janelas mensais alguns meses passam de 50 atos, que é o
# teto por resposta, e atos seriam perdidos silenciosamente. Quando mesmo assim
# a resposta vem cheia, `varrer_janela` reparte a janela ao meio.
DIAS_POR_JANELA = 15

# Quanto a varredura incremental volta atrás da marca da última execução. O DOU
# reindexa ato com alguns dias de atraso, e edição extra sai fora de hora: sem a
# refação dessa faixa, um ato publicado no dia da varredura anterior mas
# indexado depois nunca seria visto.
MARGEM_DIAS = 21

# Quando não há marca nenhuma (primeira execução), varre um ano.
MESES_PADRAO = 12

# Uma frase só — ver nota no cabeçalho de `dou.py`. A busca do DOU ignora acento
# e gênero, então esta frase também traz "Auditora Federal de Finanças e Controle".
FRASE_BUSCA = '"Auditor Federal de Finanças e Controle"'


def varrer_janela(inicio: date, fim: date, usar_cache: bool, profundidade: int = 0) -> list[dict]:
    """
    Os atos da CGU publicados na janela, repartindo a janela se a resposta encher.

    A busca do DOU não pagina: resposta cheia pode estar truncada, e o único
    jeito de ver o resto é pedir um intervalo menor. Sem isto, uma janela cheia
    perderia atos em silêncio — que é o pior modo de falhar aqui.
    """
    resultados = dou.buscar(FRASE_BUSCA, inicio, fim, usar_cache=usar_cache)

    if dou.busca_estourou_teto(resultados) and inicio < fim and profundidade < 4:
        meio = inicio + (fim - inicio) // 2
        print(f"      (resposta cheia em {inicio:%d/%m}–{fim:%d/%m} — repartindo a janela)")
        return varrer_janela(inicio, meio, usar_cache, profundidade + 1) + varrer_janela(
            meio + timedelta(days=1), fim, usar_cache, profundidade + 1
        )

    return [r for r in resultados if dou.e_da_cgu(r)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Varre o DOU por frase e registra as saídas de AFFC da CGU."
    )
    parser.add_argument("--desde", help="Data inicial (AAAA-MM-DD). Vence a marca da varredura.")
    parser.add_argument("--meses", type=int, help="Varre os últimos N meses, ignorando a marca.")
    parser.add_argument("--diagnostico", action="store_true",
                        help="Mostra o que acharia, sem gravar índice, HTML nem marca.")
    parser.add_argument("--sem-cache", action="store_true",
                        help="Ignora o cache em disco e rebaixa tudo do in.gov.br.")
    args = parser.parse_args()
    usar_cache = not args.sem_cache

    hoje = date.today()
    if args.desde:
        desde = datetime.strptime(args.desde, "%Y-%m-%d").date()
        origem = "--desde"
    elif args.meses:
        desde = hoje - timedelta(days=args.meses * 30)
        origem = "--meses"
    elif (marca := atos.ler_varredura()):
        desde = marca - timedelta(days=MARGEM_DIAS)
        origem = f"marca de {marca:%d/%m/%Y} menos {MARGEM_DIAS} dias"
    else:
        desde = hoje - timedelta(days=MESES_PADRAO * 30)
        origem = "primeira varredura"

    indice = atos.ler()
    importados = atos.importar_de_saidas_dou(indice)
    completados = atos.completar_do_arquivo(indice)

    print(f"Frase   : {FRASE_BUSCA}")
    print(f"Órgão   : {dou.ORGAO_CGU}")
    print(f"Período : {desde:%d/%m/%Y} a {hoje:%d/%m/%Y}  ({origem})")
    print(f"Índice  : {len(indice)} ato(s)"
          f"{f', {importados} vindo(s) do saidas_dou.csv' if importados else ''}"
          f"{f', {completados} relido(s) da cópia em disco' if completados else ''}")
    if args.diagnostico:
        print("Modo    : DIAGNÓSTICO — nada será gravado.")
    print()

    novos: list[dict] = []
    ja_no_indice = 0
    nao_publicados = 0
    vistos: set[str] = set()

    fim = hoje
    numero = 0
    while fim >= desde:
        inicio = max(desde, fim - timedelta(days=DIAS_POR_JANELA - 1))
        numero += 1

        candidatos = varrer_janela(inicio, fim, usar_cache)
        print(f"[{numero}] {inicio:%d/%m/%Y}–{fim:%d/%m/%Y}: {len(candidatos)} ato(s) da CGU")

        for resultado in candidatos:
            chave = resultado.get("urlTitle", "")
            if not chave or chave in vistos:
                continue
            vistos.add(chave)

            if chave in indice:
                ja_no_indice += 1
                continue

            _, texto = dou.baixar_ato(chave, usar_cache=usar_cache)
            if not texto:
                continue
            tipo = dou.classificar(texto)
            if tipo is None:
                continue
            if tipo in dou.MOTIVOS_NAO_PUBLICADOS:
                # Reconhecido e deliberadamente não registrado (D18). Some daqui
                # sem link, sem cópia e sem linha no índice.
                nao_publicados += 1
                continue

            linha = atos.registrar(
                indice, resultado, tipo, texto, atos.FONTE_FRASE, arquivar=not args.diagnostico
            )
            if linha:
                novos.append(linha)
                print(f"    + {dou.ROTULOS[tipo]}: {resultado['pubDate']} | {resultado['title'][:56]}")

        fim = inicio - timedelta(days=1)

    print()
    print(f"Atos novos          : {len(novos)}")
    print(f"Já estavam no índice: {ja_no_indice}")
    if nao_publicados:
        print(f"Não publicados (D18): {nao_publicados} — reconhecidos, não registrados")

    recentes = atos.mais_recentes_por_tipo(indice, ("vacancia", "aposentadoria", "exoneracao"))
    print()
    print("Mais recente de cada tipo do card:")
    for tipo in ("vacancia", "aposentadoria", "exoneracao"):
        linha = recentes.get(tipo)
        print(f"  {dou.ROTULOS[tipo]:<34} {linha['DATA_PUBLICACAO'] if linha else '(nenhum)'}")

    if args.diagnostico:
        print("\nModo diagnóstico — nada gravado.")
        return 0

    atos.gravar(indice)
    atos.gravar_varredura(hoje)
    print()
    print(f"  gravado: {atos.ARQ_INDICE.relative_to(atos.RAIZ)} ({len(indice)} linhas)")
    print(f"  gravado: {atos.ARQ_VARREDURA.relative_to(atos.RAIZ)} ({hoje:%Y-%m-%d})")
    print(f"  atos em: {atos.DIR_ATOS.relative_to(atos.RAIZ)}/")
    print()
    print("Rode `python gerar_card_dou.py` para o card refletir o que foi achado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
