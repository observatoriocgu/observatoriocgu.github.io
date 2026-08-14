# Plano de adaptação — Observatório SEF-MG → Observatório CGU

Cada fase é independente e termina com o site funcionando (`npm run build` OK em `evasao/`).
Regra do CLAUDE.md: **uma fase por vez**.

## Escopo (revisado em 13/08/2026)

O observatório acompanha **apenas Auditores Federais de Finanças e Controle (AFFC)** do concurso
CGU 2021 (FGV). **Técnicos Federais de Finanças e Controle (TFFC) ficam fora** — não entram nos
dados, nos filtros, nos textos nem nas contagens.

Consequência direta: como só existe um cargo, **não há coluna `CARGO`** e o termo genérico para
pessoa é **"Auditor"**, não "servidor".

O `CLAUDE.md` já reflete este escopo (seção "Escopo de cargos"), inclusive a regra de terminologia —
é ele que impede as próximas sessões de reintroduzirem o TFFC ou o termo "servidor".

## Pré-requisitos (uma vez só)

- [x] `cd evasao && npm install` — `node_modules/` não existe no clone. Node 24.18 / npm 11.16 já instalados.
- [x] Rodar `npm run build` **antes** de qualquer alteração, para registrar o baseline verde. (OK em 13/08/2026, vite 6.4.3, 60 módulos.)

**Sobre o `dist/`:** ~~está commitada e é ela que o Pages serve~~ — **mudou na Fase 1.5**. Hoje `vite.config.ts` usa `base: '/evasao/'`, a pasta `evasao/dist/` é **artefato local ignorado pelo Git**, e quem publica é o workflow `.github/workflows/deploy-pages.yml`, que roda `npm run build` no CI a cada push na `main`. Toda fase que mexer em `evasao/` ainda deve terminar com `npm run build` verde — mas **não há mais `dist/` para commitar**. Nunca editar `dist/` à mão.

---

## Decisões tomadas

Todas as decisões abaixo estão **fechadas**. As fases podem ser executadas sem consulta adicional.

| # | Decisão | Afeta | Resolução |
|---|---|---|---|
| D1 | E-mail de contato do observatório | Fase 1 | `observatoriocgu@gmail.com` — **placeholder**; exige verificação no FormSubmit antes do formulário funcionar |
| D2 | ID do Google Analytics | Fase 1 | **remover** o `G-NZ84J0PJBF` das 4 HTMLs e não colocar substituto |
| D3 | Logo/favicon | Fase 1 | manter a arte atual; apenas renomear os arquivos e ajustar as referências |
| D4 | ~~`CARGO` separado de `AREA`~~ | ~~Fase 2~~ | **REVOGADA pela D7** — com um cargo só, a coluna `CARGO` deixa de existir |
| D5 | Valor do custo por Auditor | Fase 3 | `CUSTO_POR_AUDITOR = null` → card de custo **oculto** enquanto não houver valor com fonte |
| D6 | Destino da pasta `ranking/` | Fase 5 | **remover** a pasta inteira (opção A) |
| D7 | Escopo de cargos | Fases 1-4, 6 | **somente AFFC**. TFFC fora do observatório. Termo em texto: **"Auditor" / "Auditores"** |
| D8 | Publicação do site | Fase 1.5 | GitHub Actions builda e publica; `evasao/dist/` sai do versionamento |
| D9 | Veteranos e múltiplos concursos | Fases 2-4 | coluna **`CONCURSO`** própria (`CGU-2021`, `CGU-2026`, … , `VETERANO`), separada de `AREA`. Tudo num arquivo só. Um concurso novo = um valor novo, não um arquivo novo |
| D10 | Card "dias sem perder um Auditor" | Fase 2.5 | fonte passa a ser o **DOU**, não o `dados.csv`. Conta só atos **da CGU** (exclui AFFC cedidos, cujo ato sai por outro órgão). O trecho arquivado é **HTML** do ato, não PDF. Recorde de dias **removido** do card |

**Pendências operacionais que essas decisões geram** (não bloqueiam nenhuma fase):

- D1 — criar/verificar a caixa `observatoriocgu@gmail.com` no FormSubmit; até lá o formulário de colaboração não entrega mensagens.
- D5 — levantar uma estimativa de custo com fonte citável para reativar o card em algum momento futuro.

---

## [x] Fase 1 — Rebranding superficial ✅ concluída em 13/08/2026 (revisada pela D7)

**Objetivo:** zero menção a SEF-MG/DOE/Minas Gerais na interface. Nenhum arquivo de dados tocado.

### Terminologia (revisada pela D7)

- subtítulo padrão das páginas: **"Auditores Federais de Finanças e Controle — CGU"**
- termo para pessoa: **Auditor / Auditores** — nunca "servidor", nunca "Técnico"
- órgão: **CGU** · diário: **Diário Oficial da União (DOU)**

### Correção da D7 — "servidor" → "Auditor" (feita)

A primeira execução desta fase adotou "servidor" como termo genérico, para cobrir AFFC + TFFC.
A D7 eliminou o TFFC e todo esse vocabulário voltou para "Auditor". Só texto mudou.

- [x] `evasao/App.tsx` — 12 pontos: `:1325` (subtítulo sem "e Técnicos"), `:1332`, `:1346`, `:1354`,
  `:1362`, `:1366`, `:1453-1454`, `:1462` (comentário), `:1465`, `:1467-1468`, `:1490`, `:1497`.
- [x] `evasao/components/AnnouncementModal.tsx:44,48`.
- [x] `evasao/components/DetailedTableApp.tsx:583` e `DetailedTable.tsx:210` — subtítulo sem "e Técnicos".
- [x] `evasao/relatorio_impressao.tsx:174,179,184` (títulos das 3 listas) e `:199` (subtítulo).
- [x] `evasao/index.html:8` e `dados_detalhados.html:8` — `<meta description>` só com AFFC.
- [x] `README.md` (raiz) — TFFC removido.

**Efeito colateral bom:** os identificadores herdados do modelo MG (`AuditorDetail`, `AuditorRow`,
`allAuditors`, `mapaAuditoresEmExercicio`) **passaram a estar corretos** e saíram da lista de
renomeação da Fase 3.

### Já concluído em 13/08/2026

- [x] `evasao/App.tsx` — todas as strings visíveis de `1310-1504` reescritas para o contexto CGU:
  - `:1322` — `<h1>OBSERVATÓRIO DAS EVASÕES</h1>` mantido (título é neutro; cor `#E21111` hardcoded permanece)
  - `:1453-1454` — "desistindo de tomar posse na CGU" / "A CGU perdeu…"
  - `:1490` — "Edital 1/2022" → "concurso CGU 2021 (FGV), homologado em 14/06/2022"
  - `:1497` — nota metodológica agora cita o DOU
  - `:1504` — rodapé → "Diário Oficial da União (DOU)"
- [x] `AnnouncementModal.tsx` — rebrandeado. O modal segue **desativado** (`ANNOUNCEMENT_ENABLED = false`), então não é decisão urgente; remover só se ninguém for reativá-lo.
- [x] `CollaborationForm.tsx` — e-mail → `observatoriocgu@gmail.com` (**D1**), `_subject` → `[Observatório CGU]`, texto "evasão na SEF" → "evasão na CGU".
- [x] `DetailedTableApp.tsx` (:583, :829), `DetailedTable.tsx` (:210, :438), `relatorio_impressao.tsx` (:174-184, :199).
  - `HistoryPage.tsx`, `EvasionTable.tsx` e `AprovadosOutrosConcursosTable.tsx` **não tinham texto visível de MG** — as ocorrências contadas eram só identificadores e chaves `MASP`/`HGV-0`. Ver Fase 3.
- [x] `<title>` com sufixo "CGU" e `<meta description>` nas 4 HTMLs (as 3 últimas não tinham description).
- [x] Google Analytics `G-NZ84J0PJBF` (**D2**) — removido das 4 HTMLs do build, sem substituto.
  - ⚠️ Sobrou em `evasao/table.html:24,30` — arquivo **fora do build**, marcado para exclusão na Fase 6.
- [x] `/index.css` inexistente — removido de `index.html`, `dados_detalhados.html` e `historico_alteracoes.html` (estava nas 3). O aviso do build sumiu.
- [x] Links internos absolutos → relativos: `App.tsx:1444,1481`, e o mesmo defeito em `DetailedTableApp.tsx:574` e `HistoryPage.tsx:398`.
  - Os `fetch` de CSV (`App.tsx:331`, `DetailedTableApp.tsx:188`, `HistoryPage.tsx:281`…) **continuam absolutos de propósito** — têm lista de fallback e mexer neles é lógica de dados (Fase 4).
- [x] `README.md` (raiz) — passa a descrever o Observatório CGU. (Conteúdo completo fica na Fase 6.)
- [x] `.gitignore` na raiz — criado.
- [x] ~~`ranking/` — mesmo e-mail FormSubmit~~ — pulado: **D6** remove a pasta inteira na Fase 5.

**Não fazer nesta fase:** nada em `evasao/data/`, `types.ts`, `constants.ts` ou lógica de negócio.

**Adiado de propósito** (não é menção a MG, é dependência de constante):

- As strings "Janeiro/2024" / "Desde Janeiro de 2024" (`App.tsx:1350, 1454, 1490`) espelham `DATA_INICIO_OBSERVACAO`. Mudá-las agora deixaria a UI mentindo sobre a constante — vão junto com a troca para `2022-06-14` (ver Fase 3).

**Concluída quando:** ~~`npm run build` OK, nenhum "SEF", "MG" ou "Minas Gerais" visível na UI, nenhum "servidor" ou "Técnico" nos textos, varredura limpa.~~ ✅ build OK (`vite 6.4.3`, 60 módulos); varredura de `servidor|Técnico|TFFC|SEF|Minas Gerais|Receita Estadual|DOE-MG|G-NZ84J0PJBF|index.css` em `evasao/**/*.{tsx,ts,html}` retorna **só `table.html`** (arquivo morto, fora do build, exclusão na Fase 6). Conferido também nos bundles gerados: zero ocorrências de "servidor"/"técnico" e o subtítulo correto nos 3 pontos onde aparece.

---

## [x] Fase 1.5 — Estrutura de URLs ✅ concluída em 13/08/2026

**Objetivo:** `https://observatoriocgu.github.io/evasao/` abre o painel direto, sem `/dist/` na URL.

**O bug:** o Pages servia a branch crua, então `/evasao/` entregava o `evasao/index.html` de
desenvolvimento do Vite — cujo `<script src="/index.tsx">` o navegador não executa. A página ficava
**em branco**, com 3 favicons 404. A entrada real sempre foi `/evasao/dist/`, e daí vinham os links
absolutos `/evasao/dist/*.html` espalhados pelo código. Comportamento herdado do site original de MG.

**Opção escolhida: C — o GitHub Actions builda e publica** (**D8**). As alternativas avaliadas foram
(A) mudar o `outDir` para `evasao/`, que exigiria mover as fontes para `evasao/src/`, e
(B) um redirect, que **não resolve** — `meta refresh` leva a barra de endereços para `/evasao/dist/`,
o `/dist/` continua na URL.

### Feito

- [x] `evasao/vite.config.ts` — `base: '/evasao/dist/'` → **`'/evasao/'`**.
- [x] `.github/workflows/deploy-pages.yml` (novo) — `npm ci` → `npm run build` → monta `_site/` → publica.
  - `_site/index.html` = redirect da raiz · `_site/evasao/` = `dist/` · `_site/.nojekyll`
  - **`_site/evasao/data/*.csv`** — cópia explícita: os CSVs são lidos em runtime por
    `/evasao/data/dados.csv` e **não passam pelo build** (não estão em `public/`). Sem esse passo o
    painel carrega vazio.
  - **`_site/ranking/`** — copiado para não sumir do ar por efeito colateral. A Fase 5 (**D6**) o remove.
- [x] `index.html` na raiz do repo — redirect para `/evasao/` (`meta refresh` + `location.replace` + link visível).
- [x] `update-alteracoes.yml` — parou de commitar `evasao/dist/alteracoes*.json`.
  - **Pegadinha resolvida:** push feito com `GITHUB_TOKEN` **não dispara outros workflows**. Sem
    tratamento, uma atualização do `dados.csv` nunca chegaria ao ar. Por isso o `deploy-pages.yml`
    tem também o gatilho `workflow_run` apontando para o workflow de histórico.
- [x] Logos renomeados para CGU, **arte preservada** (**D3**): `observatorio-cgu-logo.png`,
  `observatorio-cgu-logo-mini.png`, `observatorio-cgu-favicon.ico`, `observatorio-cgu-favicon-alt.ico`
  (este último não é referenciado por ninguém). Fonte única: `evasao/public/assets/images/`.
  As duas cópias soltas em `evasao/` eram byte a byte idênticas (md5 conferido) e foram removidas.
  6 referências de favicon no `ranking/` repontadas para `../evasao/assets/images/`.
- [x] Migração executada: Pages trocado para "GitHub Actions", site no ar em `/evasao/`,
  `evasao/dist/` removida do versionamento (17 arquivos) e acrescentada ao `.gitignore`.

**Verificado:** `_site/` montado localmente igual ao workflow, com todas as referências conferidas
uma a uma — 8 caminhos absolutos, 15 relativos, 3 links entre páginas (dentro do bundle) e 5
caminhos de dados em runtime. Nenhum 404.

**URLs públicas:** `/` (redirect) · `/evasao/` · `/evasao/dados_detalhados.html` ·
`/evasao/historico_alteracoes.html` · `/evasao/relatorio_impressao.html` · `/ranking/` (até a Fase 5).

---

## [x] Fase 2 — Novo esquema de dados ✅ concluída em 13/08/2026

**Objetivo:** definir o contrato de dados CGU e um `dados.csv` de EXEMPLO para validar a UI. A UI ainda **não** é adaptada (isso é Fase 3) — esta fase pode deixar o dashboard com números zerados/errados, desde que o build passe.

### O problema do modelo de MG: veteranos e concursos (D9)

Levantamento no `dados.csv` atual (3.570 linhas de dados):

| `AREA` | linhas |
|---|---|
| `FISCALIZAÇÃO` | 2194 |
| **`VETERANO`** | **937** |
| `TI` | 238 |
| `TRIBUTAÇÃO` | 202 |

**`VETERANO` era um valor da coluna `AREA`** — os auditores anteriores ao concurso monitorado
ficavam no **mesmo arquivo**, distinguidos por `POSICAO_CONCURSO` vazio (vale para as 937 linhas,
sem exceção). As situações também são de outra natureza: 838 `EM EXERCÍCIO`, 49 `APOSENTADO`,
49 `AFASTAMENTO PRELIMINAR À APOSENTADORIA`, 1 `EXONERADO` — contra `CADASTRO DE RESERVA` (2095),
`EM EXERCÍCIO` (398), `EXONERADO` (78) e `DESISTENTE` (59) do lado concursado.

Dois defeitos, que a CGU herda se copiarmos o modelo:

1. **Um veterano não pode ter área.** A coluna que diria a especialidade está ocupada dizendo que ele
   é veterano. São duas dimensões espremidas numa. Daí vem todo o `if (areaSelecionada === 'VETERANO')`
   do `DetailedTableApp.tsx` (`:481, 666, 714, 723, 738`) e do `DetailedTable.tsx` (`:253, 288, 297, 310`),
   com tabelas de 7/8 colunas em vez de 11/12.
2. **Não existe coluna de concurso.** O concurso é implícito ("o último"). Com o concurso CGU de 2026
   à vista, isso colapsa: as coortes não se separam e `POSICAO_CONCURSO` fica ambíguo.

**D9 — decisão:** separar as duas dimensões. `CONCURSO` passa a ser coluna própria; `AREA` fica só
com a especialidade e vale **também para veteranos**.

### Esquema proposto para `dados.csv` (separador `;`)

| Coluna atual (MG) | Coluna nova (CGU) | Observação |
|---|---|---|
| `MASP` | `SIAPE` | matrícula federal; vazio para quem nunca tomou posse |
| — | **`CONCURSO`** | **nova** (**D9**) — `CGU-2021`, `CGU-2026`, … ou `VETERANO` |
| `INSCRICAO` | `INSCRICAO` | mantém; **vazio para `VETERANO`** |
| `POSICAO_CONCURSO` | `POSICAO_CONCURSO` | mantém; **vazio para `VETERANO`** |
| `AREA` | `AREA` | só a especialidade. Vocabulário **por concurso** (ver `constants.ts`); pode ser preenchida para veteranos |
| `NOME`, `PCD`, `SITUACAO`, `ORGAO_DESTINO` | iguais | mantém |
| `DATA_*` (7 colunas) | iguais | mantém a semântica; publicação passa a ser no **DOU** |
| `OBSERVACAO` | `OBSERVACAO` | mantém |
| `UNIDADE` | `UNIDADE` | passa a ser unidade CGU (CGU-Regional/UF ou unidade da sede) |
| `VAGA` (`FA nnnn`) | **remover** | específico de MG |
| `CDCOMI`, `DESCCOMI` | **remover** | específico de MG |
| `DATA_INICIO` | `DATA_INICIO` | mantém (entrada em exercício) |

**Semântica de `CONCURSO`:**

- `VETERANO` = entrou antes do primeiro concurso monitorado. É um balde **estável**: quando o pessoal
  de 2026 chegar, os de 2021 continuam `CGU-2021` — não viram veteranos.
- Um novo concurso é **um valor novo na coluna**, não um arquivo novo nem uma coluna nova. É isso que
  torna o modelo escalável para N concursos.
- Veteranos e concursados ficam **no mesmo arquivo**: mesma entidade (auditor da CGU), mesmos eventos
  (exoneração, aposentadoria). Separar duplicaria toda a lógica de agregação.

> **Sem coluna `CARGO`** (**D7** revogou a **D4**): o observatório cobre um cargo só, AFFC.

> **Chave de identidade (atenção):** `SIAPE` quando existir, senão o par **`CONCURSO` + `INSCRICAO`**.
> Nunca `INSCRICAO` sozinha — números de inscrição **podem colidir entre concursos diferentes**, e o
> `App.tsx:67` hoje usa `INSCRICAO` como primeira opção. Correção na Fase 3.

> Verificado no código: `VAGA`, `CDCOMI` e `DESCCOMI` **não são lidos por nenhum componente** — podem sair sem quebrar nada. `UNIDADE` é lido em 5 pontos do `App.tsx` (`682, 746, 783, 800, 853`) e alimenta o gráfico "por Unidade".

### Tarefas

- [x] `evasao/types.ts` — de 4 para ~80 linhas: `RegistroAuditor` (as 18 colunas, todas `string`, com as regras de preenchimento da D9 documentadas), `Concurso`, `SituacaoAuditor` e `ColunaRegistroAuditor`. O `App.tsx` ainda usa `any[]` — trocar é Fase 3.
- [x] `evasao/constants.ts`:
  - `DATA_INICIO_OBSERVACAO`: `2024-01-01` → **`2022-06-14`** (homologação do concurso CGU 2021).
    É a data em que **o observatório começa a contar eventos** — vale para veteranos também, não só
    para os concursados de 2021.
  - `COST_PER_AUDITOR = 30000` → renomear para `CUSTO_POR_AUDITOR` e deixar **a definir** (**D5**)
  - **`CONCURSOS`** (**D9**) — catálogo dos concursos monitorados, aqui e não num CSV: é configuração
    que muda uma vez por concurso, e assim fica tipada e sem mais um `fetch` para falhar. Cada entrada:
    `id` (`CGU-2021`), `rotulo` de exibição, `banca`, `ano`, `dataHomologacao` e a **lista de áreas
    daquele concurso**.
    - `CGU-2021` — FGV, homologado em 14/06/2022, áreas: `Auditoria e Fiscalização`, `TI`,
      `Contabilidade Pública e Finanças`, `Correição e Combate à Corrupção`.
    - `CGU-2026` — **entrada a criar quando o edital sair**; banca, data e áreas ainda desconhecidas.
      Não inventar (regra do CLAUDE.md).
    - `VETERANO` — pseudo-concurso, sem banca/homologação/inscrição. Áreas: as mesmas do `CGU-2021`
      enquanto não houver fonte melhor, admitindo vazio.
  - `SITUACOES` — `EM EXERCÍCIO`, `EXONERADO`, `DESISTENTE`, `APOSENTADO`, `CADASTRO DE RESERVA`.
    Revisar na Fase 3 os casos herdados de MG (`AFASTAMENTO PRELIMINAR À APOSENTADORIA`,
    `POSSE JUDICIAL`, `INAPTO ADMISSIONAL`).
  - **Não** criar um enum global `AREAS`: o vocabulário é por concurso, vive dentro de `CONCURSOS`.
  - Extras criados junto: `ID_CONCURSO_VETERANO`, `CONCURSO_POR_ID` (Map), `CONCURSOS_REAIS`,
    `areasDoConcurso(id?)` e `SITUACOES_DE_SAIDA` — a Fase 3 precisa deles para os filtros.
- [x] `evasao/data/dados.csv` novo — 18 colunas, **14 linhas**, todas com `EXEMPLO` na `OBSERVACAO`:
  8 de `CGU-2021` (as 4 áreas × `EM EXERCÍCIO`/`EXONERADO`/`DESISTENTE`/`CADASTRO DE RESERVA`),
  4 de `VETERANO` (2 com `AREA` preenchida, 2 vazias; `EM EXERCÍCIO`, `APOSENTADO`, `EXONERADO`) e
  2 de `CGU-2026` em `CADASTRO DE RESERVA`. Nenhuma linha de TFFC (**D7**).
  - Nomes são `AUDITOR EXEMPLO 01..14` de propósito: nome fictício realista poderia coincidir com
    pessoa real num site público sobre movimentação de carreira.
  - Sem BOM (o código já remove BOM em 11 pontos, mas não depender disso é mais limpo).
- [x] `dados.csv` original **preservado** em `evasao/data/_legado_sefmg/dados.csv` (via `git mv`,
  então o histórico do arquivo segue rastreável). Não é publicado: o `deploy-pages.yml` copia
  `evasao/data/*.csv`, sem recursão em subpastas.
- [x] `aprovacoes_outros_concursos.csv` (5 linhas) e `outros_concursos.csv` (4 linhas) — cabeçalhos
  preservados byte a byte, conteúdo real de MG substituído por EXEMPLO. Os nomes referenciam
  `AUDITOR EXEMPLO 01/02/07/09` do `dados.csv`, para o card "aguardando nomeação" ter o que mostrar —
  inclusive um veterano e uma pessoa aprovada em dois concursos.
  - ⚠️ Não confundir: esses dois arquivos são sobre concursos **de outros órgãos** em que auditores da
    CGU foram aprovados. Nada a ver com a coluna `CONCURSO` nova, que é a coorte de entrada **na CGU**.

**Concluída quando:** ~~`npm run build` OK, o site carrega o CSV de exemplo sem erro no console.~~
✅ build OK (`vite 6.4.3`, 60 módulos). Validação executada nos 3 CSVs: contagem de campos por linha
bate com o cabeçalho em **todas** as linhas (18/9/10 colunas), as 3 coortes aparecem (8/4/2), nenhuma
linha `VETERANO` tem `INSCRICAO` ou `POSICAO_CONCURSO` preenchidos, e nenhuma linha ficou sem a marca
`EXEMPLO`.

### Achados desta fase (não bloqueiam, mas precisam de dono)

- ⚠️ **`vite build` não faz typecheck.** Ele só apaga os tipos via esbuild — build verde **não** prova
  que a tipagem está correta. Rodar `npx tsc --noEmit` à parte. Vale para todas as fases seguintes.
- ⚠️ **6 erros de tipagem pré-existentes** (confirmado: idênticos antes e depois da Fase 2, com
  `types.ts`/`constants.ts` restaurados da versão anterior para comparar):
  - 3× `Property 'env' does not exist on type 'ImportMeta'` (`App.tsx:569`, `HistoryPage.tsx:317`,
    `relatorio_impressao.tsx:15`) — causa: `tsconfig.json:13-15` declara `"types": ["node"]` sem
    `vite/client`.
  - 3× `Type 'unknown' is not assignable to type 'ReactNode'` (`App.tsx:1205`,
    `DetailedTable.tsx:427`, `DetailedTableApp.tsx:653`).
  - Correção agendada na Fase 6.
- ⚠️ **`generate-alteracoes.js` vai gerar um changelog falso** no primeiro commit do `dados.csv` novo:
  ele diffa o histórico git do arquivo, e a troca de 3.570 linhas de MG por 14 de EXEMPLO parece
  3.570 remoções + 14 inclusões. Tratar na Fase 4, junto com a regeneração dos JSONs.

---

## [x] Fase 2.5 — Card "dias sem perder um Auditor" via DOU ✅ concluída em 13/08/2026

**Objetivo:** o card deixa de contar a partir do `dados.csv` e passa a contar a partir dos atos
publicados no **Diário Oficial da União**, com link para o ato de cada tipo de saída (**D10**).

### Como a busca do DOU se comporta (levantado na marra, não há documentação)

- Endpoint público, **sem autenticação e sem chave**: `in.gov.br/consulta/-/buscar/dou`.
- Os resultados vêm num JSON embutido em `<script id="..._BuscaDouPortlet_params">`, com data,
  título, tipo de ato, seção, edição, página, hierarquia do órgão e `urlTitle` (monta o permalink).
- **Aceita UMA frase entre aspas.** Frase + termo solto devolve **zero**; termos soltos viram OU
  (`vacância Auditor Federal...` → 311 mil resultados). Não dá para pedir "AFFC E vacância".
- `delta` funciona até 50; acima disso o servidor volta a 20.
- **Nenhum parâmetro de paginação funciona** (`currentPage`, `pagina`, `_cur` foram testados e
  devolvem sempre a primeira página).
- ⇒ a varredura é feita por **janelas de 15 dias**, andando para trás. Janela mensal estoura o teto
  de 50 em vários meses e perderia atos em silêncio.
- O campo `content` da busca é só um trecho de ~200 caracteres e **não serve para classificar** o
  ato — o verbo costuma cair fora da janela. É preciso baixar o texto completo de cada ato.

### Feito

- [x] `evasao/scripts/dou_saidas_affc.py` — busca a frase `"Auditor Federal de Finanças e Controle"`,
  filtra os atos cujo órgão hierárquico é a CGU (**D10**), baixa o texto completo, classifica em
  `vacancia` / `aposentadoria` / `exoneracao` e para quando acha o mais recente de cada tipo.
- [x] `evasao/public/dias_sem_perder_affc.json` — guarda **datas, nunca a contagem de dias**. Quem
  calcula "faz N dias" é o navegador, ao renderizar; assim o card não congela no dia do crawler.
- [x] `evasao/data/dias_sem_perder_AFFC/*.html` — cópia arquivada do ato de cada saída, com título,
  data, seção, edição, página, órgão, texto e link para o original. É o destino dos links do card.
- [x] `App.tsx` — card reescrito: número = dias desde a saída mais recente entre os 3 tipos;
  **o "Nosso recorde é N dias" saiu**; entram 3 links, um por tipo, com a data de cada um. Tipo sem
  ato no período aparece apagado, como `Vacância: —`.
- [x] `.github/workflows/atualizar-saidas-dou.yml` — cron diário às 09:00 UTC (06:00 Brasília).
- [x] `deploy-pages.yml` — passou a copiar `data/dias_sem_perder_AFFC/` (sem isso os links dão 404)
  e a reagir também a este workflow no `workflow_run`.

### Validação da classificação (o ponto de risco desta fase)

Publicar "0 dias sem perder um Auditor" por causa de um ato mal classificado seria afirmar coisa
errada sobre pessoa real. Por isso a classificação foi conferida ato a ato:

- ✅ **Aposentadoria, 03/08/2026** — *"Conceder aposentadoria voluntária [...] ao servidor [...]
  ocupante do cargo de Auditor Federal de Finanças e Controle [...] do Quadro de Pessoal da CGU"*.
- ✅ **Exoneração, 25/02/2026** — *"EXONERAR, a pedido, [...] do cargo de Auditor Federal de Finanças
  e Controle da Controladoria-Geral da União"*.
- ❌ **Falso positivo capturado e corrigido:** *"EXONERAR [...], Auditor Federal de Finanças e
  Controle, do **Cargo Comissionado Executivo** de Chefe de Setor, código **CCE 1.02**"* — isso é
  saída de uma chefia, não da CGU. O filtro cobria `DAS` e `FCPE`, mas não o `CCE`, que é a
  nomenclatura nova. Agora a exoneração exige **duas provas**: nenhum marcador de chefia
  (`CCE`/`FCE`/`FCPE`/`DAS`/cargo em comissão) **e** a exoneração ser explicitamente *do cargo* de
  AFFC (`PADRAO_EXONERACAO_EFETIVA`).
- ✅ **Vacância, 11/08/2026** — *"Declarar vago o cargo de Auditor Federal de Finanças e Controle
  ocupado pelo servidor [...] por motivo de posse em outro cargo inacumulável"*.

**Três bugs encontrados no caminho — todos eram silenciosos, nenhum quebrava o build:**

1. **`\s` virando `\S`.** O `normalizar()` fazia `.upper()` no próprio regex, e `\s` (espaço) virava
   `\S` (não-espaço). O padrão do cargo nunca casava: zero saídas em 161 atos da CGU. Os padrões
   agora são declarados já normalizados.
2. **O DOU não escreve "vacância".** A redação real é *"Declarar vago o cargo [...] por motivo de
   posse em outro cargo inacumulável"* (art. 33, VIII, da Lei 8.112/90). Procurar por `VACANCIA`
   perdia **todos** os atos desse tipo — havia 4 só na primeira janela de 15 dias, e a conclusão
   anterior de "nenhuma vacância em 12 meses" estava errada.
   - Cuidado embutido: a exoneração a pedido diz *"ficando vago o cargo"*. Um padrão frouxo como
     `VAGO O CARGO` classificaria exoneração como vacância. O padrão ancora em `DECLARAR VAGO` e
     exige o motivo `POSSE EM OUTRO CARGO`.
3. **`return None` onde cabia `continue`.** Os atos se sobrepõem no vocabulário: uma aposentadoria
   termina com *"declarar vago o referido cargo"*. Como a vacância é testada primeiro, ela casava,
   falhava no teste de motivo e **abortava a classificação inteira** — a aposentadoria de 03/08/2026
   sumia e o card exibia uma de 10/10/2025 no lugar. Agora cada tipo descartado apenas passa ao
   próximo.

**Concluída quando:** ✅ build OK, `tsc --noEmit` sem erro novo (seguem os 6 pré-existentes da
Fase 2), YAML dos 2 workflows válido, e `_site` montado localmente com **os 2 links do card
resolvendo para arquivo existente**.

### Pendências

- [ ] O número do card vem do DOU; os outros 3 cards e as tabelas continuam vindo do `dados.csv` de
  EXEMPLO. Coerência entre as duas fontes é assunto da Fase 4.
- [ ] `diasRecorde` (`App.tsx:1289-1298`) ficou **sem uso** depois que o recorde saiu do card.
  Remover na Fase 3.
- [ ] A busca cobre 12 meses por execução. Se a CGU passar mais de 12 meses sem um tipo de saída,
  aquele link some. Aumentar `--meses` se acontecer.
- [x] ~~Empate de data~~ — **decidido em 14/08/2026: tanto faz.** O card mostra um ato por tipo e,
  havendo mais de um na mesma data (em 11/08/2026 houve as Portarias 2.099 e 2.100), fica com o
  primeiro que a busca devolver. O ato serve de exemplo e comprovação da data, não de censo.

**Delimitação de escopo (D10):** este crawler existe **só para o número de dias e os 3 links**. Ele
não é — e não precisa virar — fonte de contagem de evasões: para de varrer assim que acha o ato mais
recente de cada tipo, então nunca soube quantas saídas houve no total. A **série completa vem da
base mensal do SIAPE** (Portal da Transparência), na Fase 4. Consequência prática: não faz sentido
auditar a cobertura do crawler nem medir recall; o que importa é a **precisão** dos 3 atos exibidos,
que foi conferida um a um.

---

## [ ] Fase 3 — Adaptar `App.tsx` e componentes ao novo esquema

**Objetivo:** dashboard coerente com os dados de exemplo da Fase 2.

- [ ] **Situações** (`App.tsx:1145-1148`) — revisar os literais `EXONERADO`, `DESISTENTE`, `APOSENTADO`, `AFASTAMENTO PRELIMINAR À APOSENTADORIA`. Verificar se "afastamento preliminar à aposentadoria" existe no regime federal ou se some. `POSSE JUDICIAL` e `INAPTO ADMISSIONAL` também aparecem no CSV atual.
- [ ] **Filtro de área** (`App.tsx:1414-1425`) — hoje monta os botões a partir de `FISCALIZAÇÃO / TI / TRIBUTAÇÃO / VETERANO`, misturando as duas dimensões. Passa a listar só as áreas, e **as áreas dependem do concurso selecionado** (**D9**). Idem `DetailedTableApp.tsx:6,415-424`, que tem `'FISCALIZAÇÃO'` hardcoded como área padrão.
- [ ] **Filtro de concurso** (novo, **D9**) — segundo seletor: `Todos` · `CGU-2021` · `VETERANO` · (`CGU-2026` quando existir). Define quais áreas o filtro de área oferece.
- [ ] **"VETERANO"** — deixa de ser valor de `AREA` e vira `CONCURSO = 'VETERANO'` (**D9**). Os `if (areaSelecionada === 'VETERANO')` do `DetailedTableApp.tsx` (`:481, 666, 714, 723, 738`) e do `DetailedTable.tsx` (`:253, 288, 297, 310`) viram uma regra honesta: **se o concurso é `VETERANO`, esconder as colunas `INSCRICAO` e `POSICAO_CONCURSO`** (que são sempre vazias), em vez de trocar o layout inteiro da tabela.
- [ ] **Agregadores por concurso** — cards e gráficos precisam decidir, um a um, se contam só concursados, só veteranos ou os dois. No modelo MG isso era acidental (dependia de a linha ter `POSICAO_CONCURSO`); agora é escolha explícita.
- [ ] **Card de custo** (`CounterCard`) — usar `CUSTO_POR_AUDITOR`; ocultar o card enquanto o valor for `null` (**D5**).
- [ ] **Gráfico por Unidade** (`agregarPorUnidade`, `App.tsx:783-853`) — validar com as unidades CGU do CSV de exemplo.
- [ ] `DetailedTableApp.tsx` (836 linhas) e `DetailedTable.tsx` — colunas exibidas, ordenação e filtros passam a refletir `SIAPE`.
- [ ] `relatorio_impressao.tsx` — mesmas colunas.
- [ ] `chave` de identificação: `App.tsx:67` usa `INSCRICAO → MASP → HGV-0 → NOME`. Trocar `MASP` por `SIAPE`, eliminar o `'HGV-0'` (resíduo sem origem no CSV) e — **importante (D9)** — nunca usar `INSCRICAO` sozinha: com dois concursos os números **colidem**. A chave passa a ser `SIAPE`, senão `CONCURSO + INSCRICAO`. O mesmo padrão se repete em `HistoryPage.tsx:88,150,200,213,232,241` e `:433`.
- [ ] **Strings de data herdadas da Fase 1** — "Desde Janeiro de 2024" (`App.tsx:1350`), "desde Janeiro/2024" (`:1454`) e "a partir de Janeiro de 2024" (`:1490`) precisam acompanhar a troca de `DATA_INICIO_OBSERVACAO` para `2022-06-14`. Ideal: derivar da constante em vez de repetir o texto.

> Renomear identificadores `Auditor*` **saiu desta fase**: com a D7, `AuditorDetail`, `AuditorRow`,
> `allAuditors` e `mapaAuditoresEmExercicio` passaram a descrever corretamente o domínio.

**Concluída quando:** `npm run build` OK e os 4 cards, o gráfico e as 3 tabelas mostram números consistentes com as ~10 linhas de exemplo.

---

## [ ] Fase 4 — Pipeline de dados

**Objetivo:** repor a esteira de atualização, agora contra fontes federais.

- [ ] `evasao/data/processador.ipynb` — hoje consome os snapshots `Auditores_YYYYMM.csv` do portal de MG (43 colunas, `masp,nome,descsitser,...`). Reescrever para o **Portal da Transparência federal** (formato de "Servidores Civis" — layout e nomes de coluna totalmente diferentes). **Filtrar só AFFC** (**D7**).
- [ ] `evasao/data/historico transparencia_legado_sefmg/` — 27 CSVs mensais de MG (`202312`–`202602`). Remover ou arquivar; a série da CGU já recomeçou (ver abaixo).
- [x] **Série da CGU já baixada e filtrada** — `evasao/data/historico_transparencia_cgu/` tem 49 snapshots mensais (`202206`–`202606`) do Portal da Transparência, reduzidos a só os AFFC por `evasao/scripts/filtrar_affc.py`.
  - Os CSVs brutos do portal têm **~420 MB cada** (o GitHub recusa acima de 100 MB); filtrados, os 49 somam ~70 MB. A pasta está **no `.gitignore`**: é dado de trabalho regenerável, não pertence ao repo.
  - O filtro casa o cargo `AUDITOR FEDERAL DE FINANCAS E CONTROLE` de forma normalizada (sem acento, espaços colapsados), o que exclui o TFFC por construção (**D7**). Encoding de entrada é **latin-1** — ler como UTF-8 quebra no primeiro "ç".
  - É esta base, e não o crawler do DOU da Fase 2.5, que deve produzir a contagem de evasões (**D10**).
- [ ] `evasao/data/mudancas/` — 26 diffs `.txt` derivados dos anteriores. Idem.
- [ ] `evasao/scripts/reorder_dados.py` — ajustar à nova ordem de colunas.
- [ ] `evasao/scripts/generate-alteracoes.js` (249 linhas) — lê o histórico **git** do `dados.csv` para montar o log de alterações. Verificar as referências a colunas (`MASP`) e o comportamento no primeiro commit do CSV novo.
- [ ] Regenerar `evasao/public/alteracoes.json` e `alteracoes-registros.json` — os atuais contêm 182 commits com autor `observatoriosefmg` e mensagens do projeto antigo.
- [ ] Carregar a lista de aprovados do **Resultado Final FGV de 13/06/2022** (fonte no CLAUDE.md) para popular o `dados.csv` real — **apenas as listas de AFFC**, descartando as de TFFC (**D7**). Essas linhas nascem com `CONCURSO = CGU-2021`.
- [ ] **Derivar os veteranos** (**D9**) — regra: quem aparece como AFFC da CGU no Portal da Transparência e **não** está na lista da FGV entrou antes, logo `CONCURSO = VETERANO`, com `INSCRICAO` e `POSICAO_CONCURSO` vazios. O cruzamento é por nome normalizado enquanto não houver SIAPE nas duas pontas — validar a taxa de acerto antes de confiar, porque homônimos existem.
  - Fonte para a `AREA` dos veteranos: verificar se o Portal expõe algo aproveitável. Se não expuser, deixar vazio — **não inventar** (regra do CLAUDE.md). O modelo suporta o campo vazio.

**Concluída quando:** `npm run build` OK e o `dados.csv` real (não-EXEMPLO) renderiza corretamente.

---

## [ ] Fase 5 — Destino da pasta `ranking/`

**Contexto:** 3 páginas HTML estáticas (`index.html` 3708 linhas, `composicao.html` 746, `ranking-verbas-indenizatorias.html` 378) + `dados-grafico.json` (872 KB) + 27 bandeiras estaduais. Compara remuneração de **fiscos estaduais** — sem paralelo no contexto federal da CGU. Não compartilha código com `evasao/` (só os favicons, por caminho relativo).

Decisão **D6: opção A — remover**.

- [ ] Apagar a pasta `ranking/` inteira. Nada em `evasao/` depende dela.
- [ ] Remover a cópia de `ranking/` do `deploy-pages.yml` (passo "Montar o site"), que existe só para não derrubar a pasta antes desta fase.

**Concluída quando:** pasta removida, nenhum link morto apontando para `ranking/`, workflow ajustado e `npm run build` OK.

---

## [ ] Fase 6 — Metadados, Actions e limpeza final

- [ ] `README.md` — escrever de verdade: o que é o observatório, fonte dos dados, como rodar, como contribuir.
- [ ] `CLAUDE.md` — atualizar a nota sobre `dist/`, que mudou na Fase 1.5 (a pasta agora é artefato ignorado pelo Git; a regra "não tocar à mão" segue válida). O escopo de cargos (**D7**) já está registrado lá.
- [ ] `evasao/README.md` — hoje é o boilerplate do Google AI Studio (banner, link para `ai.studio`, instrução de `GEMINI_API_KEY`). Substituir.
- [ ] `evasao/metadata.json` — `name` e `description`.
- [ ] `evasao/package.json:2` — `"name": "evasão-auditores-fiscais-mg"` → `observatorio-cgu`.
- [ ] `evasao/vite.config.ts` — remover o `define` de `process.env.API_KEY` / `GEMINI_API_KEY`: **não há nenhum uso de Gemini no código**, é resto do scaffold.
- [ ] `.github/workflows/update-alteracoes.yml` — nome do workflow e mensagem de commit em português já servem; revisar caminhos se a Fase 4 mudar a estrutura. (Os caminhos de `dist/` já saíram na Fase 1.5.)
- [ ] `evasao/scripts/generate-alteracoes.js:8` — ainda escreve em `['public', 'dist']`. Como `dist/` virou artefato de build ignorado, deixar só `public`.
- [ ] `evasao/tsconfig.json:13-15` — acrescentar `"vite/client"` ao `types` (hoje só `"node"`), que resolve os 3 erros de `import.meta.env`. Corrigir também os 3 `unknown → ReactNode` (`App.tsx:1205`, `DetailedTable.tsx:427`, `DetailedTableApp.tsx:653`). Meta: `npx tsc --noEmit` limpo.
- [ ] Considerar rodar `tsc --noEmit` no `deploy-pages.yml` antes do build — hoje um erro de tipo passa direto para produção.
- [ ] Remover `evasao/table.html` e `evasao/table.tsx` — **não estão no build** (`vite.config.ts` declara só 4 entradas), é código morto. `table.html:24,30` ainda carrega o GA `G-NZ84J0PJBF` e `:41` o `/index.css` inexistente — a remoção do arquivo resolve os dois.
- [x] ~~Reavaliar `base: '/evasao/dist/'`~~ — **resolvido na Fase 1.5**.
- [ ] Varredura final: `grep -ri "sef\|minas\|masp\|doe-mg\|tffc\|técnico" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist .` deve voltar vazio (fora de arquivos de legado explicitamente arquivados).

**Concluída quando:** `npm run build` OK e a varredura final está limpa.
