#!/usr/bin/env python3
"""
O comando único do observatório (D15 do PLANO.md).

Encadeia o pipeline inteiro:

    filtrar_affc      reduz os CSVs brutos do Portal (~420 MB cada) aos AFFC
    concurso          resultado final do concurso, do DOU  (só com --concurso)
    construir_painel  snapshots -> historico_mensal / dados / serie / alterações
    enriquecer_saidas motivo e destino de cada saída nova, buscando por NOME
    varrer_dou        o que o DOU publicou desde a última varredura, por FRASE
    construir_painel  de novo, agora com o que o DOU achou
    resumir_dou       o resumo do DOU para o site (card + saídas recentes),
                      a partir do índice
    enriquecer_destinos_ranking  destino de quem o DOU não disse para onde foi

O segundo `construir_painel` não é engano: o primeiro descobre QUEM saiu, o
enriquecedor descobre POR QUE, e o segundo costura isso no `dados.csv`.

AS DUAS VARREDURAS DO DOU FAZEM COISAS DIFERENTES. A busca por NOME parte de
quem o SIAPE mostra que saiu, e por isso nunca alcança o que foi publicado
depois da última competência do Portal (~2 meses de atraso). A busca por FRASE
lê o DOU do dia e não sabe de quem é o ato. As duas gravam no mesmo índice
(`data/dou/atos_saida.csv`), e é dele que o card sai — não de uma varredura própria,
como era até 15/08/2026, quando o card e a lista de saídas do painel podiam
discordar sem que nenhum dos dois estivesse errado.

ROTINA MENSAL
    1. python baixar_transparencia.py   # baixa e descompacta o que faltar
    2. python atualizar.py
    3. conferir os avisos, revisar `curadoria_sugestoes.csv`, commitar

  O passo 1 substitui o que antes era manual — pegar o ZIP do mês em
  portaldatransparencia.gov.br/download-de-dados/servidores e descompactar o
  `AAAAMM_Cadastro.csv` em evasao/data/historico_transparencia_cgu/. Ele NÃO é
  chamado daqui de propósito: baixa ~4 GB no backfill, e um pipeline que dispara
  isso sozinho surpreende quem só queria reconstruir o painel.

Uso:
    python atualizar.py                 # ciclo completo
    python atualizar.py --concurso      # rebaixa também o edital do concurso
    python atualizar.py --sem-dou       # só a parte offline (rápido)
    python atualizar.py --diagnostico   # não grava nada, só relata
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def rodar(descricao: str, argumentos: list[str], passo: list[int] | None = None) -> bool:
    """Roda um script do pipeline. `passo` é o contador mutável [atual, total]."""
    if passo is not None:
        passo[0] += 1
        descricao = f"{passo[0]}/{passo[1]} {descricao}"
    print()
    print("=" * 72)
    print(f"  {descricao}")
    print("=" * 72)
    resultado = subprocess.run([sys.executable, *argumentos], cwd=AQUI)
    if resultado.returncode != 0:
        print(f"\n! '{descricao}' terminou com código {resultado.returncode}.", file=sys.stderr)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Roda o pipeline de dados do observatório.")
    parser.add_argument("--sem-dou", action="store_true",
                        help="Pula o enriquecimento pelo DOU (só a parte offline).")
    parser.add_argument("--concurso", action="store_true",
                        help="Rebaixa o edital do concurso antes de construir o painel.")
    parser.add_argument("--diagnostico", action="store_true",
                        help="Não grava nada; só confere os snapshots e relata.")
    parser.add_argument("--limite", type=int,
                        help="Passa adiante: no máximo N saídas consultadas no DOU.")
    args = parser.parse_args()

    if args.diagnostico:
        return 0 if rodar("Conferência", ["construir_painel.py", "--diagnostico"]) else 1

    # O total é CALCULADO, não escrito à mão: as duas bandeiras mudam quantos
    # passos existem, e o rótulo fixo "1/7" mentia sempre que `--concurso` ou
    # `--sem-dou` entravam. `passo` é [atual, total], e quem incrementa é `rodar`.
    passo = [0, (3 if args.sem_dou else 7) + (1 if args.concurso else 0)]

    # Sem `--manter-original` os CSVs brutos são apagados depois de filtrados —
    # é o comportamento padrão do script, e o que impede a pasta de crescer para
    # dezenas de GB. Nada a perder: o Portal republica.
    if not rodar("Filtrando os snapshots do Portal", ["filtrar_affc.py"], passo):
        return 1

    if args.concurso and not rodar("Resultado final do concurso (DOU)", ["concurso.py"], passo):
        return 1

    if not rodar("Construindo o painel", ["construir_painel.py"], passo):
        return 1

    if args.sem_dou:
        # O resumo ainda é regerado: `resumir_dou.py` não tem rede, só relê o
        # índice. Sem isto, `--sem-dou` deixaria o JSON apontando para um índice
        # que pode ter mudado por outro caminho.
        rodar("Regerando o resumo do DOU a partir do índice", ["resumir_dou.py"], passo)
        print("\n--sem-dou: motivo e destino das saídas não foram atualizados.")
        return 0

    enriquecer = ["enriquecer_saidas.py"]
    if args.limite:
        enriquecer += ["--limite", str(args.limite)]
    if not rodar("Buscando motivo e destino no DOU, por nome", enriquecer, passo):
        return 1

    if not rodar("Varrendo o DOU por frase (o que o SIAPE ainda não mostra)",
                 ["varrer_dou.py"], passo):
        return 1

    if not rodar("Reconstruindo o painel com o que o DOU achou", ["construir_painel.py"], passo):
        return 1

    if not rodar("Resumindo o índice de atos para o site", ["resumir_dou.py"], passo):
        return 1

    # Por último, e depois do resumo: este crawler lê o `dou.json` que o
    # passo anterior acabou de gerar — é de lá que saem as saídas que só o DOU
    # conhece. Uma falha aqui não invalida nada do que veio antes: o painel
    # apenas segue com menos destino identificado.
    if not rodar("Procurando destino de quem saiu, no Ranking dos Concursos",
                 ["enriquecer_destinos_ranking.py"], passo):
        print("! o painel continua válido; só o destino do ranking não foi atualizado.",
              file=sys.stderr)

    print()
    print("Pronto. Antes de commitar:")
    print("  - confira uma amostra dos ATO_SAIDA_URL em data/dados.csv")
    print("  - revise data/curadoria_sugestoes.csv (nada dali foi aplicado sozinho)")
    print("  - saídas marcadas SAIDA_PROVISORIA=SIM só se confirmam no mês seguinte")
    print("  - atos do índice sem ID_SERVIDOR_PORTAL são os que o SIAPE ainda não")
    print("    confirmou — é a defasagem do Portal, não erro de varredura")
    print("  - em data/destinos_ranking.csv, DECISAO=AMBIGUO é pauta humana: o")
    print("    ranking achou mais de um concurso e não diz qual a pessoa exerceu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
