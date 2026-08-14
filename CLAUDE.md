# Observatório CGU (fork do Observatório SEF-MG)
Site estático (GitHub Pages) que monitora a evasão de Auditores da CGU.
Versão original: Auditores Fiscais SEF-MG. Esta versão: cargo AFFC — Auditor
Federal de Finanças e Controle, coortes CGU-2021 (concurso FGV) e VETERANO
(quem já estava na CGU em jun/2022).

O observatório apura quem saiu da CGU pela diferença mês a mês do SIAPE e
busca no DOU, por nome, o ato que diz por que a pessoa saiu e para onde foi.
As áreas/especialidades (Auditoria e Fiscalização, TI, Contabilidade Pública
e Finanças, Correição e Combate à Corrupção) NÃO estão no SIAPE: vêm do
Edital CGU nº 5 de 13/06/2022, publicado no DOU (D17).

## Escopo de cargos (decisão D7 do PLANO.md)
- APENAS AFFC. O cargo TFFC (Técnico Federal de Finanças e Controle, nível
  médio) está FORA do observatório: não entra em dados, filtros, contagens
  nem textos. Ao carregar o Portal da Transparência (ou, na Fase 7, a lista
  do concurso), filtrar só AFFC.
- Como há um cargo só, NÃO existe coluna CARGO no dados.csv.
- Terminologia nos textos da interface: "Auditor" / "Auditores". Nunca
  "servidor" nem "Técnico". Subtítulo padrão das páginas:
  "Auditores Federais de Finanças e Controle — CGU".

## Regras de adaptação
- Matrícula: MASP (MG) vira SIAPE (federal)
- Diário oficial: DOE-MG vira DOU
- Fonte PRIMÁRIA: a diferença mês a mês do SIAPE (Portal da Transparência do
  Governo Federal), em evasao/data/historico_transparencia_cgu/ (D11)
- Resultado final do concurso (área, inscrição, nota, classificação,
  modalidade): vem do DOU, do Edital CGU nº 5 de 13/06/2022 — UMA requisição,
  488 aprovados AFFC. NÃO usar o site da FGV, NÃO usar crawler de banca (D17)
- O que fica FORA é o concurso de DESTINO (para onde a pessoa foi depois de
  sair, quem está estudando pra sair) — isso é Fase 7
- Homologação do concurso: 14/06/2022 (início da observação)
- Colunas específicas de MG (VAGA FA, CDCOMI, DESCCOMI) devem ser removidas ou
  substituídas por equivalentes federais (unidade CGU/lotação UF)

## Regras de dados (D11-D14 do PLANO.md) — não reintroduzir erros já mapeados
- AFFC != CGU. A carreira é compartilhada com o Ministério da Fazenda/Economia
  (~825 pessoas). Filtrar SEMPRE por COD_ORG_LOTACAO = '59000'. NUNCA filtrar
  por nome de órgão: a grafia muda entre meses ("Ministério da Economia" vira
  "MINISTERIO DA FAZENDA", acentos somem)
- Chave de identidade é Id_SERVIDOR_PORTAL, e só ele (D12). NOME NUNCA é chave
  — homônimos existem. Estão revogadas as cadeias INSCRICAO -> MASP -> HGV-0
  -> NOME e o par CONCURSO + INSCRICAO
- "Saiu da CGU" = ausência a partir da ÚLTIMA PRESENÇA na série (D13), nunca
  diff par a par: há 6 pessoas que somem por 1-6 meses e voltam, e o diff par
  a par publicaria 6 saídas falsas
- historico_mensal.csv é a base consolidada (D16): os 49 snapshots empilhados,
  uma linha por (competência x pessoa), 88.421 linhas, 17 das 43 colunas, mais
  MES, CONCURSO e AREA. dados.csv e serie_mensal.csv derivam DELA
- historico_mensal.csv e dados.csv são DERIVADOS. Nunca editar à mão. Correção
  humana vai em data/curadoria.csv, que vence sobre DOU e SIAPE no merge
- Unidade se conta pelo CÓDIGO (COD_UORG_LOTACAO), nunca pelo nome: o nome
  muda de grafia entre meses e infla "mudou de unidade" de 410 para 1.229
- UF_EXERCICIO = "-1" é DESCONHECIDO, não é UF, e não conta como mudança. O
  Portal só passou a preencher o campo no fim de 2023 (em 202206 são 100% "-1")
  — NÃO existe série de auditores por UF antes de 2024
- NÃO existe dado de comissão/função: FUNCAO, SIGLA_FUNCAO e NIVEL_FUNCAO são
  "Sem informação"/"-1" nas 88.421 linhas. O análogo de desccomi/cdcomi da
  SEF-MG não tem fonte — não prometer essa análise em tela nenhuma
- Todo campo enriquecido carrega FONTE_* (SIAPE/DOU/RANKING/BUSCA/MANUAL) e a
  linha carrega VERIFICADO (SIM/NÃO, preenchido por gente) (D14). NÃO existe
  nota de confiança automática: a máquina diz de onde tirou e se alguém
  conferiu — ela não se autoavalia
- Nenhum destino ("foi para o TCU") vai ao ar sem fonte registrada e link
- DEMISSÃO NÃO É PUBLICADA (D18): é penalidade disciplinar, e o observatório
  mede evasão. O classificador reconhece o tipo, mas grava SITUACAO=DESLIGADO,
  sem motivo detalhado e SEM link nem cópia do ato — saidas_dou.csv e a pasta
  saidas_dou/ vão para repositório público e para o site. Ver
  dou.MOTIVOS_NAO_PUBLICADOS. Não dar a DESLIGADO rótulo que revele o motivo
- Padrões de regex do DOU já vêm normalizados: NÃO passar por normalizar(),
  senão .upper() transforma \s em \S e o padrão nunca casa (bug real da
  Fase 2.5)

## Pipeline de dados (evasao/scripts/)
- atualizar.py         comando único: filtra -> constrói -> DOU -> reconstrói
- dou.py               biblioteca: rede, busca, cache, classificação de atos
- painel.py            biblioteca: derivação dos snapshots (sem rede)
- construir_painel.py  gera historico_mensal / dados / serie / alteracoes
- concurso.py          resultado final do concurso, a partir de 1 ato do DOU
- enriquecer_saidas.py motivo e destino de cada saída, buscando por nome no DOU
- filtrar_affc.py      reduz o CSV bruto do Portal aos AFFC
- dou_saidas_affc.py   card "dias sem perder um Auditor" (Fase 2.5)
- testar_dou.py        regressão da classificação, sem rede. RODAR SEMPRE que
                       mexer nos padrões de dou.py: cada caso ali é um erro que
                       já foi ao ar ou quase foi

## Ferramentas
- Scripts Python são STDLIB ONLY: o CI não roda pip install, e requests/bs4/
  pandas não estão instalados. Usar urllib + fallback curl, como os crawlers
  atuais já fazem
- A matrícula do Portal vem mascarada em 7 posições COM zero à esquerda
  ("014****"); o DOU escreve o SIAPE SEM ele ("149262"). Comparar sempre com
  zfill(7), senão o ato certo é descartado como se fosse de homônimo
- Ao procurar o DESTINO de quem saiu: a posse no novo órgão costuma ser
  publicada ANTES do ato de vacância da CGU. Janela [-6, +6] meses da saída
- MOTIVO e DESTINO não têm a mesma confiabilidade. Motivo é leitura direta do
  ato da CGU (95%, sem erro nas conferências). Destino é INFERÊNCIA e tem uma
  cauda longa de falsos positivos: cargo comissionado, lista de classificação,
  "vago em decorrência da posse de X", "anteriormente ocupado por X",
  "vacância do cargo de X", desistência, "tornar sem efeito a nomeação".
  Todos fechados e cobertos por testar_dou.py — mas a precisão residual NÃO
  está estabelecida. Destino é INDÍCIO COM FONTE, não fato apurado: nunca usar
  destino não verificado em número agregado de card
- O hierarchyStr do DOU às vezes erra o órgão do ato (visto: PORTARIA-TCU
  indexada sob Ministério dos Transportes). Não há padrão que resolva

## Regras de trabalho
- NUNCA alterar mais de uma fase por vez (ver PLANO.md)
- Sempre rodar npm run build em evasao/ antes de encerrar uma tarefa
- vite build NÃO faz typecheck — rodar npx tsc --noEmit à parte
- Não tocar em evasao/dist/ manualmente (é artefato de build, ignorado pelo
  Git; quem publica é .github/workflows/deploy-pages.yml)
- Não inventar dados: onde não houver dado real da CGU, usar placeholder
  claramente marcado como EXEMPLO
- Ao publicar afirmação sobre pessoa real e nomeada (motivo de saída, destino),
  conferir o ato à mão antes de dar a fase por concluída