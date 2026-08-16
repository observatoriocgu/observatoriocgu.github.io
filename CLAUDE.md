# Observatório CGU (fork do Observatório SEF-MG)
Site estático (GitHub Pages) que monitora a evasão de Auditores da CGU.
Versão original: Auditores Fiscais SEF-MG. Esta versão: cargo AFFC — Auditor
Federal de Finanças e Controle, concursos CGU-2021 (concurso FGV) e VETERANO
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
- historico_mensal.csv são os 49 snapshots empilhados: uma linha por
  (competência x pessoa), 88.421 linhas, 17 das 43 colunas, mais MES, CONCURSO e
  AREA. Mora em data/historico_transparencia_cgu/, JUNTO DOS SNAPSHOTS de que é
  feito, e portanto fora do Git. NÃO é a base de nada: quem o escreve é o
  construir_painel.py, e dados.csv e serie_mensal.csv saem dos SNAPSHOTS, não
  dele — nenhum código o lê. Serve para auditar a série à mão. A D16 dizia que
  dados.csv e serie_mensal.csv derivavam dele; nunca derivaram, e versionar o
  arquivo custava 20,7 MB reescritos por competência, publicados no site
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
- Todo campo enriquecido carrega FONTE_* (SIAPE/DOU/RANKING/BUSCA/MANUAL) (D14).
  NÃO existe nota de confiança automática: a máquina diz de onde tirou, e só
- NÃO existe mais VERIFICADO (D20, 15/08/2026). O selo "conferido/não conferido"
  saiu da UI e a coluna saiu do dados.csv. Como quase nada passa por conferência
  humana individual, a tela mostrava "não conferido" ao lado de dado correto
  lido do ato oficial — gerava desconfiança em vez de qualificar. No lugar,
  mostram-se as FONTES que atestam o fato: uma saída com selo SIAPE + DOU está
  atestada pelo cadastro e pelo ato; com DOU sozinho, é ato que o cadastro ainda
  não alcançou. NÃO reintroduzir "conferido" — é decisão editorial, não lacuna
- Selo SIAPE numa saída = a pessoa consta do quadro no mês n-1 e não consta no
  mês n. Isso é a própria definição da D13, não uma checagem à parte: toda linha
  do dados.csv com MES_SAIDA tem o selo por construção
- Nenhum destino ("foi para o TCU") vai ao ar sem fonte registrada e link
- O ATO DE DEMISSÃO NÃO VAI AO AR (D18, alcance revisto em 16/08/2026): é
  penalidade disciplinar, e o observatório mede evasão. O classificador
  reconhece o tipo, e o ato NÃO entra no índice, NÃO é arquivado em saidas_dou/
  e NÃO ganha link em tela nenhuma — o índice e a pasta vão para repositório
  público e para o site. Ver dou.MOTIVOS_NAO_PUBLICADOS
- O DADO grava o motivo real: MOTIVO_SAIDA=Demissão, SITUACAO=DEMITIDO. Até
  15/08/2026 gravava-se DESLIGADO/Desligamento, o que era impreciso —
  desligamento não é o nome do que aconteceu. Quem mascara é a TELA
- Quem mascara é `motivoDe` (lib/painel.ts), e SÓ ela: devolve MOTIVO_OUTRO
  ("Outro motivo") no lugar da demissão. É o caminho PADRÃO de propósito — tela
  nova que chamar motivoDe acerta sem saber que a regra existe. Revelar exige
  pedido explícito, via `motivoDetalhado`, e só dados_detalhados.html o faz.
  NÃO repetir a regra em componente: mascarar caso a caso vaza no primeiro
  componente novo. NÃO confundir MOTIVO_OUTRO com MOTIVO_OUTROS ("Outros"), que
  é o balde-resumo de quatro motivos do card de saídas
- A pessoa CONTINUA CONTADA EM TUDO: card, gráfico, curva, destinos, tabela
  detalhada e histórico, com balde próprio e o mesmo total. O que não vai à tela
  é a palavra, não a pessoa
- Padrões de regex do DOU já vêm normalizados: NÃO passar por normalizar(),
  senão .upper() transforma \s em \S e o padrão nunca casa (bug real da
  Fase 2.5)

## De quem é o ato, e o que o ato não é (D25, 16/08/2026)
- IDENTIDADE É NÍVEL, NÃO PORTÃO. `dou.identidade_no_ato` devolve SIAPE (a
  matrícula bate), NOME (a fórmula do ato nomeia exatamente esta pessoa) ou
  CITACAO (só o nome solto no texto). Quem chama exige o cargo em tudo que não
  for SIAPE. NÃO voltar a usar `cita_nome` como porta de entrada: ela é
  substring, e casa "LUIZ CARLOS DE ALMEIDA" dentro de "...ALMEIDA SOUZA"
- A MATRÍCULA DIVERGENTE REBAIXA, NÃO VETA — em ato da CGU. O DOU erra os dois
  lados: erra o nome (Portaria 325/2023 escreve "PAGLIONE" onde o SIAPE diz
  "PAGLIONI", com a matrícula batendo) e erra a matrícula (Portarias 1.026/2024,
  2.529/2024 e 2.017/2025 nomeiam a pessoa por extenso e trazem SIAPE de outra;
  a 2.017 diz 2435442 onde a própria CGU lista 3347490). Isso só é seguro porque
  NÃO há nome repetido na base — 2.009 pessoas, zero homônimos. FORA da CGU a
  matrícula continua VETANDO: lá o homônimo é risco real
- "DECLARAR VAGO" É A FORMA, NÃO A CAUSA. O motivo decide o tipo: posse em outro
  cargo → vacância; desistência do estágio probatório → EXONERAÇÃO (art. 33, I).
  Quando o ato só cita a lei, vale o inciso (VIII → vacância, I → exoneração) —
  a Portaria 3.089/2022 saiu TRUNCADA no DOU e o inciso é tudo o que restou.
  Motivo desconhecido NÃO classifica, e o laço segue testando os outros tipos
- RETIFICAÇÃO NÃO É O ATO. Ela costuma ser a única que traz o nome (foi o nome
  que ela veio consertar), mas não tem motivo, às vezes não tem cargo, e tem a
  data do conserto. Lê-se nela a referência e busca-se o ORIGINAL
  (`dou.frases_do_ato_retificado`), que tem motivo, data e URL próprios
- CESSÃO É SAÍDA DO QUADRO, NÃO EVASÃO. A pessoa continua Auditora da CGU (o ônus
  é do órgão cedente), mas muda de lotação e some do recorte 59000. Balde próprio
  (`MOTIVO_CESSAO`), fora de `MOTIVOS_PADRAO`. O ato NÃO cita o cargo: só a busca
  por nome o alcança, com identidade provada pela matrícula
- TRÊS ATOS QUE NÃO SÃO SAÍDA, e os três já foram classificados como uma:
  ato NORMATIVO (regra geral — ancorar no INÍCIO do texto, porque metade das
  vacâncias reais cita "Portaria Normativa" como fundamento), AJUSTAMENTO DE
  CONDUTA (instrumento disciplinar, com nome de gente, que nem deve ir ao índice)
  e REVERSÃO DE APOSENTADORIA. Esta última é a mais grave: "reverter a
  aposentadoria de X para que RETORNE ao quadro" publicava como saída cinco
  Auditores que estavam VOLTANDO
- O `title` da busca do DOU vem com `<span class='highlight'>` nos termos
  procurados. Passar SEMPRE por `dou.titulo_do_ato` — só apareceu quando a busca
  passou a ser pelo título do ato (é assim que se acha o original da retificação)
- Busca por frase exata falha mais do que parece: `"DEBORA CRISTINA PASSOS DE SA"`
  não achava o ato que `"DEBORA CRISTINA PASSOS"` acha. Encurtar o nome afrouxa a
  BUSCA, não a IDENTIFICAÇÃO — quem decide continua sendo `identidade_no_ato`
- Nome que o DOU escreve diferente e não há como provar de dentro do ato é PAUTA
  HUMANA, não automação: coluna opcional `NOME_NO_DOU` do `curadoria.csv`
  (`construir_painel.py` a ignora). É o caso de LUIZ AUGUSTO GENTILUCCI ALVES,
  que o Edital CGU nº 5 e a Portaria 1.968/2022 chamam de LUIZ AUGUSTO DA SILVA
  ALVES, sem matrícula em nenhum dos dois

## Pipeline de dados (evasao/scripts/)
- atualizar.py         comando único: filtra -> constrói -> DOU -> reconstrói
- baixar_transparencia.py  baixa do Portal os snapshots que faltam e chama o
                       filtro. NÃO é chamado pelo atualizar.py — roda à parte,
                       antes dele, no lugar dos passos 1-2 da rotina mensal
- dou.py               biblioteca: rede, busca, cache, classificação de atos
- atos.py              biblioteca: o índice único dos atos (data/atos_dou.csv)
- painel.py            biblioteca: derivação dos snapshots (sem rede)
- construir_painel.py  gera historico_mensal / dados / serie / alteracoes
- concurso.py          resultado final do concurso, a partir de 1 ato do DOU
- enriquecer_saidas.py motivo e destino de cada saída, buscando por NOME no DOU
- varrer_dou.py        varre o DOU por FRASE e registra toda saída de AFFC
- gerar_card_dou.py    card "dias sem perder um Auditor", derivado do índice
- filtrar_affc.py      reduz o CSV bruto do Portal aos AFFC
- ranking.py           biblioteca: rankingdosconcursos, catálogo de órgãos e a
                       regra de decisão do destino (D24)
- enriquecer_destinos_ranking.py  destino de quem já saiu e o DOU não disse para
                       onde. `--conferir` mede a regra contra o gabarito do DOU
- testar_dou.py        regressão da classificação, sem rede. RODAR SEMPRE que
                       mexer nos padrões de dou.py: cada caso ali é um erro que
                       já foi ao ar ou quase foi
- testar_ranking.py    regressão do catálogo de órgãos e da regra de decisão,
                       sem rede. RODAR SEMPRE que mexer em ranking.py

## As duas varreduras do DOU escrevem no mesmo índice (D19, 15/08/2026)
- `data/atos_dou.csv` é o índice ÚNICO dos atos de saída, com chave no ato
  (URL_TITLE do in.gov.br), e `data/saidas_dou/` é a pasta única das cópias.
  NÃO recriar uma segunda pasta nem um segundo JSON para o card: era assim
  antes, e o card e a lista de saídas divergiam sem que nenhum estivesse errado
- Por NOME (`enriquecer_saidas.py`): parte do dados.csv, logo do SIAPE. Desde
  16/08/2026 a fila inclui TAMBÉM as saídas que só o DOU conhece (lidas do
  `public/atos_dou.json`), e para ELAS grava só o DESTINO — motivo e situação
  quem põe é `mesclarSaidasDoDou`, no navegador, senão o dados.csv afirmaria
  que alguém saiu sem dizer quando. Antes disso essas pessoas NUNCA tinham o
  destino procurado no DOU: a busca não falhava, ela não era feita. Foi assim
  que a PORTARIA-TCU nº 117 de 04/08/2026, que nomeia três Auditores da CGU
  para o TCU, ficou fora do observatório estando a uma busca de distância
  (~2 meses de atraso). É quem preenche o ID_SERVIDOR_PORTAL da linha
- Por FRASE (`varrer_dou.py`): lê o DOU do dia e não sabe de quem é o ato.
  É incremental — `data/varredura_dou.txt` guarda até onde já cobriu, e a
  execução seguinte volta 21 dias, porque o DOU reindexa com atraso
- O card sai de `gerar_card_dou.py`, que só relê arquivo: sem rede, sem
  snapshot do Portal, determinístico. É por isso que o workflow diário
  consegue rodá-lo — `construir_painel.py` não roda no CI, depende dos
  snapshots, que estão fora do Git
- Saída que o DOU já anunciou e o SIAPE ainda não confirmou CONTA EM TUDO
  (D22, revoga o recorte da D21): cards, gráficos, curva, destinos, tabela
  detalhada e histórico. Ela não é linha nova — é
  SOBREPOSTA ao registro da pessoa, que já está no dados.csv como ativa, e por
  isso chega à tela com concurso, área e unidade e responde aos filtros
- Quem faz a sobreposição é `mesclarSaidasDoDou` (lib/painel.ts), NO NAVEGADOR,
  e não o construir_painel.py. Não é preferência: o construir_painel depende dos
  snapshots do Portal, que estão fora do Git e não existem no CI. Quem roda todo
  dia é a varredura do DOU. Se a mescla morasse no Python, uma saída descoberta
  hoje esperaria a próxima execução local — a defasagem que ela existe para
  eliminar. Toda página que lê dados.csv TEM de passar por ela
- Três guardas contra contar errado, e nenhuma pode sair: casa por
  ID_SERVIDOR_PORTAL (nome + matrícula, no Python, D12); só se aplica a quem
  NÃO tem MES_SAIDA, senão quem tem dois atos vira duas saídas; quem não está no
  dados.csv não entra de jeito nenhum
- Ato de quem o SIAPE JÁ mostrou sair, mas sem motivo (caso da saída
  provisória, que o enriquecer_saidas pula de propósito) só COMPLETA o motivo:
  a competência continua sendo a do cadastro, e nada é contado duas vezes
- Selo de fonte se calcula com `fontesDaSaida`, e só com ela. Três componentes
  já duplicaram a regra `MES_SAIDA ? 'SIAPE' : ''` e passaram a creditar o
  SIAPE por saída que só o DOU conhecia
- O nome de quem saiu é lido do TEXTO do ato (dou.nome_do_ato), com fórmulas
  ancoradas e terminador explícito. Isso publica nome de pessoa real a partir de
  leitura de máquina: se nenhuma fórmula casar, a resposta é VAZIO — a lista
  mostra o ato sem nome, nunca um nome chutado. Os padrões são conferidos contra
  os 251 atos já casados com pessoa pelo SIAPE, em testar_dou.py, e a meta é
  ZERO divergente (vazio é aceitável, nome errado não)
- Cache: página de ato é imutável e vale para sempre; resposta de BUSCA, não.
  Janela que alcança o presente e busca sem data (`exactDate=all`) valem 6h.
  Sem isso a varredura devolve para sempre o resultado do dia em que rodou
- CONCESSÃO DE PENSÃO NÃO É SAÍDA. "Conceder pensão vitalícia a X, na qualidade
  de cônjuge do ex-servidor Y, [...] falecido em atividade" cita o cargo e cita
  falecimento, e era classificado como falecimento — mas o ato é sobre o
  pensionista, sai muito depois do óbito e o instituidor pode ser aposentado ou
  TFFC (fora do escopo, D7). Ver dou.PADROES_PENSAO

## O destino pelo Ranking dos Concursos (D24, 15/08/2026)
- A ordem é SEMPRE `já sabendo que a pessoa saiu (SIAPE/DOU) -> procurar para
  onde`. NUNCA o contrário: passar em concurso não é sair da CGU. Há Auditor com
  seis aprovações que continua na casa, e ele não pode aparecer em lugar nenhum
  do `destinos_ranking.csv`. Só quem tem saída registrada é consultado
- O ranking sabe o CONJUNTO de concursos em que a pessoa passou; NÃO sabe qual
  ela foi exercer. Por isso só se publica quando sobra UM órgão candidato.
  Ambíguo vai para pauta humana, com a lista e o link — nunca para a tela
- NÃO INVENTAR DESEMPATE. Todos foram medidos contra os 118 destinos que o DOU
  já conhece e todos reprovaram: marca "Nomeado" 6 de 18 (33,3%), melhor
  colocação 24 de 62 (38,7%), colocação até 100º 26,7%. Nos 62 ambíguos o
  destino certo estava entre os candidatos nos 62 — o que falta não é dado, é o
  critério, e ele não existe
- A ÂNCORA: só se publica se a ficha do site tiver também a linha do concurso da
  própria CGU. É a prova de que aquela ficha é desta pessoa, e não de um
  homônimo perfeito, e sinal de que a lista de concursos dela ali está completa.
  Os 2 erros que ela remove são fichas que não conheciam o concurso para o qual
  a pessoa de fato foi
- MAS A ÂNCORA SÓ VALE PARA QUEM PODE TÊ-LA (`ranking.exige_ancora`). O site só
  conhece o concurso da CGU de 2022; quem é VETERANO entrou antes e JAMAIS terá
  aquela linha. Exigi-la dele não filtra ficha incompleta — exclui a categoria
  inteira, para sempre. Foi um defeito real: veterano com vacância em 08/2026 e
  uma aprovação única no TCU ficava fora do painel só por isso. Medido:
  CGU-2021 com âncora 43 de 45 (95,6%); CGU-2021 SEM âncora 0 de 2; VETERANO
  (sempre sem âncora) 2 de 2. A regra final publica 47 e acerta 45 (95,7%)
- A TAG AZUL "Nomeado" NÃO DESEMPATA, e a tentação de usá-la é forte porque
  parece a resposta. Ela NÃO TEM DATA: marca quem foi nomeado naquele concurso
  em algum momento da vida, inclusive ANTES de entrar na CGU. Medido: 6 de 18
  (33,3%). Os 12 erros são quase todos tag em SEFAZ/ISS/TCE estadual de alguém
  que foi para Câmara, Senado ou TCU. Dois casos com a MESMA tag `ISS Aracaju`
  foram, na verdade, para TCU e para o Senado. A tag é gravada na coluna
  MARCADOS_NOMEADO só para a pauta de curadoria
- O quadradinho azul do site é "Nomeado" e o verde é "Dentro das Vagas". O azul
  parece a resposta e não é: quem passa em vários é nomeado em vários. São
  lidos e guardados para a curadoria, e não entram na decisão
- Nome NUNCA basta: a busca do site casa por PREFIXO, então "MARIA DE SOUZA
  LIMA" traz "Mariana de Souza Lima Velasco" junto. `linhas_da_pessoa` exige
  igualdade EXATA do nome normalizado. Sem isso, aprovação de uma pessoa vira
  destino de outra
- O nome do órgão NUNCA vem do rótulo do site — vem de `ranking.ORGAO_POR_ROTULO`.
  "TCU", "TCU TI 25" e "Tribunal de Contas da União" são a mesma casa; publicar
  os três rótulos criaria três destinos onde há um. Rótulo fora do catálogo NÃO
  vira destino: `canonico` devolve `""`, o caso fica ambíguo e o rótulo aparece
  no relatório para alguém acrescentar. Órgão que também vem do DOU é escrito
  EXATAMENTE como o DOU escreve, senão a tabela racha pela outra ponta
- Concurso UNIFICADO (CNU, TSE Unificado) é aprovação real com órgão indefinido:
  `canonico` devolve `None` e o caso vira AMBÍGUO. Descartá-lo em silêncio faria
  "TCU + CNU" parecer candidato único
- O site tem limitador de ritmo que responde uma página "Muitas Consultas" COM
  STATUS 200. Ela não tem tabela, então era lida como "pessoa não está no
  ranking" e gravava SEM_FICHA para quem tem ficha — 13 das 43 saídas na
  primeira varredura. `pagina_respondeu_a_busca` exige que o formulário ecoe o
  nome consultado; sem eco, não é resposta. Pausa de 3s e `None` (nunca `[]`)
  quando não se consegue perguntar
- O resultado NÃO entra no `dados.csv`: é mesclado no NAVEGADOR, por
  `mesclarDestinosDoRanking`, pelo mesmo motivo da D22. Só preenche destino
  VAZIO — a precedência é CURADORIA > DOU > RANKING
- Toda página que lê `dados.csv` chama `mesclarFontesExternas`, e não as duas
  mescladas soltas: são duas agora, e uma regra que depende de quatro páginas
  lembrarem da mesma sequência é uma regra que a quinta página quebra

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