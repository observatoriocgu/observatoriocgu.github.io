# Os arquivos de dado do observatório

## O que é gerado e o que é escrito à mão

**Nunca edite à mão** os arquivos derivados — eles são reescritos do zero a cada
`python scripts/atualizar.py`, e a edição se perde sem aviso.

| Arquivo | Como nasce | Editar à mão? |
|---|---|---|
| `historico_transparencia_cgu/` | download do Portal + `filtrar_affc.py` | não (fora do git) |
| `historico_mensal.csv` | `construir_painel.py` — 88.421 linhas, base consolidada (D16) | **não** |
| `dados.csv` | `construir_painel.py` — uma linha por Auditor | **não** |
| `serie_mensal.csv` | `construir_painel.py` — uma linha por competência | **não** |
| `concurso_2021.csv` | `concurso.py` — resultado final, do DOU (D17) | **não** |
| `saidas_dou.csv` | `enriquecer_saidas.py` — motivo e destino, do DOU | **não** |
| `saidas_dou/*.html` | `enriquecer_saidas.py` — cópia do ato de cada saída | **não** |
| **`curadoria.csv`** | **você** | **sim — é o único** |
| `curadoria_sugestoes.csv` | `construir_painel.py` — pauta para você conferir | não (é saída) |

Precedência no merge: **curadoria > DOU > concurso > SIAPE**. Qualquer campo
preenchido no `curadoria.csv` vence, e a linha passa a valer `VERIFICADO = SIM`.

## Como corrigir alguma coisa

1. Ache o `ID_SERVIDOR_PORTAL` da pessoa no `dados.csv` (é a chave — nome não é,
   porque homônimos existem).
2. Acrescente uma linha ao `curadoria.csv` com esse id e **só as colunas que quer
   corrigir**. Coluna vazia não sobrescreve nada.
3. Rode `python scripts/construir_painel.py`.

## O que precisa de conferência humana

**`curadoria_sugestoes.csv`** — pessoas cujo nome no SIAPE não casou com o
edital do concurso, mas que têm um candidato parecido. A causa mais comum é
mudança de nome civil entre 2022 e hoje (`VITORIA TEIXEIRA ROCHA` no edital,
`VITORIA TEIXEIRA ROCHA TUMER` no SIAPE). **Nada dali é aplicado sozinho**:
casar por semelhança atribuiria área e nota à pessoa errada quando errasse.
Confirmando, copie para o `curadoria.csv`.

**Os destinos.** `MOTIVO_SAIDA` é leitura direta do ato da CGU e é confiável.
`ORGAO_DESTINO` é **inferência** — ver §2.3.3 do `PLANO.md` para os dez formatos
de falso positivo já encontrados. Todo destino nasce `VERIFICADO = NÃO`; só vira
`SIM` quando alguém abrir o `URL_DESTINO` e confirmar.

## Saídas provisórias

`SAIDA_PROVISORIA = SIM` significa que a pessoa sumiu no snapshot mais novo e
**ainda não há segundo mês confirmando**. Existem 6 casos históricos de gente que
sumiu por 1 a 6 meses e voltou. Essas linhas ficam de fora da consulta ao DOU até
o mês seguinte decidir.
