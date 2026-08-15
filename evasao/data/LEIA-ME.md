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
| `concurso_2021.csv` | `concurso.py` — resultado final do DOU (D17) + os sub judice | **não** |
| **`concurso_2021_subjudice.csv`** | **você** — aprovados por decisão judicial | **sim** |
| `saidas_dou.csv` | `enriquecer_saidas.py` — motivo e destino, uma linha por **pessoa** | **não** |
| `atos_dou.csv` | as duas varreduras do DOU — o índice único, uma linha por **ato** | **não** |
| `saidas_dou/*.html` | as duas varreduras do DOU — cópia do ato | **não** |
| `varredura_dou.txt` | `varrer_dou.py` — até que dia o DOU já foi varrido | **não** |
| **`curadoria.csv`** | **você** | **sim** |
| `curadoria_sugestoes.csv` | `construir_painel.py` — pauta para você conferir | não (é saída) |

Precedência no merge: **curadoria > DOU > concurso > SIAPE**. Qualquer campo
preenchido no `curadoria.csv` vence.

## Como corrigir alguma coisa

1. Ache o `ID_SERVIDOR_PORTAL` da pessoa no `dados.csv` (é a chave — nome não é,
   porque homônimos existem).
2. Acrescente uma linha ao `curadoria.csv` com esse id e **só as colunas que quer
   corrigir**. Coluna vazia não sobrescreve nada.
3. Rode `python scripts/construir_painel.py`.

## Os aprovados sub judice

O Edital CGU nº 5, de 13/06/2022, é a foto de um dia. Depois dele a CGU
publicou dezenas de atos incluindo candidatos no resultado final **por decisão
judicial** — e são justamente esses que foram nomeados nas levas de 2024 e 2025.
Eles não estão no DOU do Edital nº 5 e não têm como estar, então entram por
`concurso_2021_subjudice.csv`, escrito à mão a partir dos atos publicados pela
FGV em <https://conhecimento.fgv.br/concursos/concursocgu21>.

Cada linha carrega `FONTE_URL`, o PDF do ato. O `concurso.py` mescla o arquivo
ao gravar o `concurso_2021.csv`, e **o DOU vence**: nome já presente no Edital
nº 5 não é sobrescrito.

Só entra quem tem ato de **inclusão no resultado final**. Fora ficam, de
propósito:

- os **TFFC** — o cargo está fora do observatório (D7);
- quem passou só de fase (2ª etapa, prova objetiva) e nunca foi incluído no
  resultado final;
- quem teve a inclusão **tornada sem efeito** por sentença posterior.

`INSCRICAO`, `NOTA` e `POSICAO_CONCURSO` ficam em branco de propósito: os PDFs
da FGV embaralham as colunas da tabela, e há pelo menos um caso em que o número
impresso no ato pertence a outra candidata na lista da prova objetiva. O painel
usa área e UF, que vêm do texto corrido do ato e batem com o Resultado
Definitivo da Prova Objetiva de 04/05/2022.

## O que precisa de conferência humana

**`curadoria_sugestoes.csv`** — pessoas cujo nome no SIAPE não casou com o
edital do concurso, mas que têm um candidato parecido. A causa mais comum é
mudança de nome civil entre 2022 e hoje (`VITORIA TEIXEIRA ROCHA` no edital,
`VITORIA TEIXEIRA ROCHA TUMER` no SIAPE). **Nada dali é aplicado sozinho**:
casar por semelhança atribuiria área e nota à pessoa errada quando errasse.
Confirmando, copie para o `curadoria.csv`.

**Os destinos.** `MOTIVO_SAIDA` é leitura direta do ato da CGU e é confiável.
`ORGAO_DESTINO` é **inferência** — ver §2.3.3 do `PLANO.md` para os dez formatos
de falso positivo já encontrados. O painel mostra o destino com o selo da fonte
ao lado e link para o ato, para que dê para conferir; ele nunca entra em número
agregado de card.

## Os selos: quem atesta cada saída

Não existe selo de "conferido" (**D20**). Como quase nada passa por conferência
humana individual, ele aparecia como "não conferido" ao lado de dado correto
lido do ato oficial — o que gerava desconfiança em vez de qualificar. No lugar,
a tela mostra **as fontes que atestam o fato**:

| Selos | O que significa |
|---|---|
| `SIAPE` + `DOU` | o cadastro mostra a ausência **e** há ato publicado dizendo por quê — duas fontes independentes |
| `SIAPE` sozinho | a pessoa sumiu do cadastro e o ato ainda não foi encontrado no DOU |
| `DOU` sozinho | o ato está publicado e o Portal ainda não entregou a competência |

`SIAPE` numa saída quer dizer exatamente isto: a pessoa consta do quadro no mês
n-1 e não consta no mês n. É a definição da **D13**, não uma checagem à parte.

## Por que a lista de saídas mistura as duas fontes

Não é erro de nenhum dos dois. São dois relógios:

- o **DOU** publica o ato no dia. `varrer_dou.py` varre por frase e registra
  tudo em `atos_dou.csv`. É daí que sai o card "dias sem perder um Auditor";
- o **SIAPE** chega ao Portal da Transparência com ~2 meses de atraso, e é ele
  quem diz **quem** saiu, pela ausência a partir da última presença (D13). É daí
  que sai a lista de últimas saídas, o gráfico e todas as contagens.

Enquanto o Portal não alcança, o nome de quem saiu é lido do **texto do próprio
ato** (`dou.nome_do_ato`) e a saída é **sobreposta ao registro da pessoa**, que
já está no `dados.csv` — ativa. Por isso ela conta **em tudo** (**D22**): cards,
gráficos, curva de permanência, destinos, tabela detalhada, histórico e
relatório impresso, com coorte, área e unidade de verdade, respondendo aos
filtros como qualquer outra. O que a distingue na tela é o selo: `DOU` sozinho
até o cadastro alcançar o mês.

Contar ato **como se fosse pessoa** é que seria errado duas vezes — uma pessoa
pode ter dois atos, e um ato pode ser de quem já estava fora do quadro. Daí as
três guardas: casa-se por `ID_SERVIDOR_PORTAL` (nome **mais** matrícula), só se
aplica a quem ainda não tem competência de saída, e ato que não casa com
ninguém do `dados.csv` não entra.

Quando o Portal alcança, `enriquecer_saidas.py` casa o ato com a pessoa,
preenche o `ID_SERVIDOR_PORTAL` e a linha ganha o selo `SIAPE` ao lado.

**Caso separado:** às vezes o SIAPE já mostrou a pessoa sumir mas ninguém achou
o ato dela — acontece com a saída provisória, que o `enriquecer_saidas.py` não
consulta no DOU de propósito. Aí o ato encontrado pela varredura por frase só
**completa o motivo**: a competência continua sendo a do cadastro, e a saída não
é contada de novo.

## Saídas provisórias

`SAIDA_PROVISORIA = SIM` significa que a pessoa sumiu no snapshot mais novo e
**ainda não há segundo mês confirmando**. Existem 6 casos históricos de gente que
sumiu por 1 a 6 meses e voltou. Essas linhas ficam de fora da consulta ao DOU até
o mês seguinte decidir.
