# Plano de adaptação — Observatório SEF-MG → Observatório CGU

Cada fase é independente e termina com o site funcionando (`npm run build` OK em `evasao/`).
Regra do CLAUDE.md: **uma fase por vez**.

## Escopo (revisado em 14/08/2026)

O observatório acompanha **apenas Auditores Federais de Finanças e Controle (AFFC)** da CGU, em duas
coortes: `CGU-2021` (concurso FGV) e `VETERANO` (quem já estava na CGU em jun/2022). **Técnicos
Federais de Finanças e Controle (TFFC) ficam fora** — não entram nos dados, nos filtros, nos textos
nem nas contagens.

**Revisão de 14/08/2026 (D11, D16, D17):** a fonte primária passou a ser a **diferença mês a mês do
SIAPE** (Portal da Transparência). O universo é **quem saiu efetivamente da CGU**, apurado pelo
SIAPE e confirmado no DOU. Os 49 snapshots viram uma **base consolidada empilhada**
(`historico_mensal.csv`, **D16**), que é o banco do observatório. A **área do concurso de entrada
fica dentro do escopo** e vem do próprio DOU (**D17**) — o que ficou para a Fase 7 é o concurso de
**destino** ("para onde o fulano foi", "quem está estudando pra sair"). Isso superou a Fase 2 (v1)
e absorveu a Fase 4 — ambas ficam no plano como registro, marcadas.

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
| D11 | Fonte primária do painel | Fases 2-4 | a **diferença mês a mês do SIAPE** (Portal da Transparência) é a espinha do observatório. Todos os arquivos de dado passam a ser **derivados**, nunca editados à mão. *(Revisado em 14/08/2026: o **resultado final do concurso entra**, mas pelo **DOU**, não pelo site da FGV — ver D17. O que fica fora é concurso de **destino**, para onde a pessoa foi depois de sair.)* |
| D16 | Base consolidada para a UI | Fases 2-3 | `historico_transparencia_cgu/` é empilhada em **`data/historico_mensal.csv`** — uma linha por (competência × pessoa), 17 colunas das 43, com `MES`, `CONCURSO` e `AREA` acrescentados. É **a** base do observatório; `dados.csv` e `serie_mensal.csv` passam a ser derivados dela |
| D17 | Área do concurso | Fase 2 | vem do **DOU**, não de crawler de banca: o `Edital CGU nº 5 de 13/06/2022` traz, **numa requisição**, inscrição, nome, nota, classificação, modalidade e área de especialização dos 488 aprovados AFFC. Vale igual para o CGU-2026 quando o edital sair |
| D12 | Chave de identidade | Fases 2-3 | **`Id_SERVIDOR_PORTAL`**, e só ele. **Revoga** a cadeia `INSCRICAO → MASP → HGV-0 → NOME` e o par `CONCURSO + INSCRICAO` da D9. Nome **nunca** é chave (homônimos) |
| D13 | Definição de "saiu da CGU" | Fase 2 | ausência do conjunto CGU (`COD_ORG_LOTACAO = 59000`) **a partir da última presença**, nunca por diff par a par. Saída detectada no snapshot mais novo nasce **provisória** |
| D14 | Procedência da informação | Fases 2-3 | todo campo enriquecido carrega **`FONTE_*`** (SIAPE/DOU/RANKING/BUSCA/MANUAL) e a linha carrega **`VERIFICADO`** (SIM/NÃO, preenchido por gente). **Não existe nota de confiança automática** — a máquina diz de onde tirou e se alguém conferiu; ela não se autoavalia |
| D15 | Atualização mensal | Fase 2 | **um comando local** (`atualizar.py`), resultado commitado; o Actions só builda e publica. Assunção adotada por padrão — migrar para cron no CI é reversível e não muda a arquitetura |
| D19 | Entrada dos atos do DOU | Fase 2.5 + Fase 2 (v2) | **um índice único de atos**, `data/atos_dou.csv`, com chave no ato (`URL_TITLE`), alimentado pelas **duas** varreduras — a por frase (`varrer_dou.py`) e a por nome (`enriquecer_saidas.py`) — e uma pasta única de cópias, `data/saidas_dou/`. O card deixa de ter crawler próprio e passa a ser **derivado** do índice (`gerar_card_dou.py`). Some a pasta `data/dias_sem_perder_AFFC/`. **Ajusta a delimitação da D10**: a varredura por frase continua não sendo fonte de contagem, mas passa a registrar **tudo** o que encontra, em vez de parar no primeiro ato de cada tipo |

**Efeito das decisões novas sobre as antigas:**

- **D9 sobrevive parcialmente.** `CONCURSO` continua coluna própria, separada de `AREA`, com `VETERANO` como valor. Muda a **origem**: a coorte passa a ser derivada da primeira aparição na série mensal, não da lista da FGV. A parte da D9 sobre chave de identidade é revogada pela **D12**.
- **D10 sobrevive inteira.** O card "dias sem perder um Auditor" continua vindo do crawler de frase da Fase 2.5, e seus padrões de classificação — validados ato a ato — são **reaproveitados sem reescrita** pelo crawler por nome da Fase 2.
- **D5 fica em suspenso.** Sem `CADASTRO DE RESERVA`/`DESISTENTE` no universo (**D11**), o card de custo perde parte do sentido original; decidir na Fase 3 se volta e sobre qual base.

**Pendências operacionais que essas decisões geram** (não bloqueiam nenhuma fase):

- D1 — criar/verificar a caixa `observatoriocgu@gmail.com` no FormSubmit; até lá o formulário de colaboração não entrega mensagens.
- D5 — levantar uma estimativa de custo com fonte citável para reativar o card em algum momento futuro.
- D14 — definir quem faz a curadoria e com que cadência; sem gente conferindo, `VERIFICADO` fica `NÃO` para sempre e o selo perde a função.

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
  - Os `fetch` de CSV (`App.tsx:331`, `DetailedTableApp.tsx:188`, `HistoryPage.tsx:281`…) **continuam absolutos de propósito** — têm lista de fallback e mexer neles é lógica de dados (Fase 3, §3.1: a lista de fallback vira uma só, no `lib/dados.ts`).
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

## [x] Fase 2 (v1) — Novo esquema de dados ✅ concluída em 13/08/2026 · ⚠️ **SUPERADA pela D11**

> **Leia isto antes de usar esta seção.** Ela fica no plano como **registro histórico**, não como
> tarefa. Em 14/08/2026 chegaram os 49 snapshots mensais do Portal da Transparência, e a **D11**
> inverteu a fonte primária: o painel deixa de ser preenchido a partir da lista da FGV e passa a ser
> **derivado da diferença mês a mês do SIAPE**. O esquema de 18 colunas descrito abaixo e o
> `dados.csv` de 14 linhas de EXEMPLO **não valem mais** — foram substituídos pelo esquema da
> **Fase 2 (v2)**, logo depois da Fase 2.5.
>
> **O que desta fase continua valendo:** a separação entre `CONCURSO` e `AREA` (**D9**), o
> `types.ts`/`constants.ts` como lugar do catálogo de concursos, e os três achados registrados no
> fim da seção (`vite build` não faz typecheck; os 6 erros de tipagem pré-existentes; o changelog
> falso do `generate-alteracoes.js`).

**Objetivo (histórico):** definir o contrato de dados CGU e um `dados.csv` de EXEMPLO para validar a UI. A UI ainda **não** é adaptada (isso é Fase 3) — esta fase pode deixar o dashboard com números zerados/errados, desde que o build passe.

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
  3.570 remoções + 14 inclusões. ~~Tratar na Fase 4~~ → **resolvido por descarte**: a Fase 2 (v2)
  aposenta o `generate-alteracoes.js`, e o changelog passa a vir do diff mensal do SIAPE.

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
  EXEMPLO. Coerência entre as duas fontes é assunto da **Fase 2 (v2)**.
- [ ] `diasRecorde` (`App.tsx:1289-1298`) ficou **sem uso** depois que o recorde saiu do card.
  Remover na Fase 3.
- [ ] A busca cobre 12 meses por execução. Se a CGU passar mais de 12 meses sem um tipo de saída,
  aquele link some. Aumentar `--meses` se acontecer.
- [x] ~~Empate de data~~ — **decidido em 14/08/2026: tanto faz.** O card mostra um ato por tipo e,
  havendo mais de um na mesma data (em 11/08/2026 houve as Portarias 2.099 e 2.100), fica com o
  primeiro que a busca devolver. O ato serve de exemplo e comprovação da data, não de censo.

> **REVISADA EM 15/08/2026 PELA D19.** O `dou_saidas_affc.py` não existe mais. A varredura por frase
> virou `varrer_dou.py`, deixou de parar no primeiro ato de cada tipo e passou a registrar tudo no
> índice `data/atos_dou.csv`; o card virou `gerar_card_dou.py`, derivado do índice, sem rede. A pasta
> `data/dias_sem_perder_AFFC/` foi removida — as cópias dos atos moram todas em `data/saidas_dou/`.
>
> **O que motivou:** as duas estruturas guardavam o mesmo ato em pastas diferentes e discordavam
> sobre qual era a última saída, sem que nenhuma estivesse errada — o card lia o DOU do dia
> (11/08/2026) e a lista lia o SIAPE, que ia até 202606. A divergência agora é medida e mostrada,
> não deduzida pelo leitor.
>
> **O que a parada precoce escondia:** ao varrer a mesma janela sem parar, apareceram na primeira
> execução 2 atos de 11/08 (Portarias 2.099 **e** 2.100) e um de 07/08 que o crawler antigo
> descartava por já ter "achado a vacância". Apareceram também 5 atos de **concessão de pensão**
> classificados como falecimento — corrigido em `dou.PADROES_PENSAO`, com 2 casos novos no
> `testar_dou.py` e 3 pessoas reprocessadas (ver §2.5.1).

**Delimitação de escopo (D10):** este crawler existe **só para o número de dias e os 3 links**. Ele
não é — e não precisa virar — fonte de contagem de evasões: para de varrer assim que acha o ato mais
recente de cada tipo, então nunca soube quantas saídas houve no total. A **série completa vem da
base mensal do SIAPE** (Portal da Transparência), na Fase 2 (v2). Consequência prática: não faz sentido
auditar a cobertura do crawler nem medir recall; o que importa é a **precisão** dos 3 atos exibidos,
que foi conferida um a um.

### 2.5.1 Concessão de pensão não é saída *(15/08/2026, achado pela D19)*

Enquanto a varredura por frase parava no primeiro ato de cada tipo, este ato nunca aparecia. Assim
que ela passou a ver tudo, apareceram cinco de uma vez:

> *"Art. 1º Conceder pensão vitalícia a **MARIA DE LOURDES SILVA**, na qualidade de companheira do
> ex-servidor **LUIZ CARLOS DE ALMEIDA**, ocupante do cargo de **Técnico** Federal de Finanças e
> Controle, matrícula SIAPE nº 1538217, [...] **falecido em atividade**, em 16/02/2025"*

O ato cita o cargo e cita falecimento, então casava `PADRAO_CARGO` e `PADROES["falecimento"]`. Mas
ele é sobre **outra pessoa** — a pensionista —, sai meses ou anos depois do óbito, e o instituidor
pode ser aposentado ou, como aqui, **TFFC**, que está fora do observatório (**D7**). Pior: o nome
dele é o mesmo de um Auditor real da base — o caso de homônimo por prefixo já documentado em
`dou.cita_nome`.

**Correção:** `dou.PADROES_PENSAO`, testado antes de qualquer tipo, com dois casos novos no
`testar_dou.py` (pensão vitalícia e temporária).

**Efeito nos dados já publicados.** Três pessoas tinham o motivo apoiado num ato de pensão. Todas as
três foram reprocessadas, e as três acharam o ato **certo**, que existia desde sempre e só perdia a
vez por estar mais longe do mês da saída:

| Pessoa | Ato antes (pensão) | Ato depois (vacância por falecimento) |
|---|---|---|
| WLADIMIR BRAIDOTTI | 12/03/2024 | **01/03/2024** |
| FABIO CARVALHO HANSEM | 13/06/2024 | **11/06/2024** |
| LUIZ CARLOS DE ALMEIDA | 14/03/2025 | **10/03/2025** |

O motivo publicado (`Falecimento`) continua o mesmo nos três casos — o que muda é o ato citado, que
agora é o da pessoa certa. O de LUIZ CARLOS foi conferido à mão: o ato novo declara vago o cargo de
**Auditor** Federal de Finanças e Controle, SIAPE `1538…`, compatível com a máscara `153****` do
Portal; o ato de pensão era de um **Técnico**, SIAPE 1538217.

---

## [x] Fase 2 (v2) — Pipeline SIAPE → saídas → DOU ✅ **concluída em 14/08/2026**

**Resultado.** Todos os critérios de aceitação bateram. Os arquivos de dado do observatório passaram
a ser gerados por um comando, a partir de fonte pública, e cada saída carrega o ato que a comprova.

| | |
|---|---|
| `historico_mensal.csv` | **88.421 linhas**, 19 colunas, 20,8 MB |
| `dados.csv` | **2.009 pessoas**, **268 saídas** (2 provisórias) |
| `serie_mensal.csv` | 49 linhas |
| Saídas **com motivo** | **255 (95%)** |
| Saídas **com destino** | 126 (47%) — camada frágil, ver §2.3.3 |
| `AREA` preenchida | **422 de 450** da coorte CGU-2021 (93,8%) — 410 automáticas + 12 por curadoria |
| Atos arquivados | 251 HTML, 1,2 MB |
| Teste de regressão | **30 invariantes**, todos passando |
| `npm run build` | verde · `tsc --noEmit`: os 6 pré-existentes, **nenhum novo** |

**Motivos das 268 saídas:** 153 vacância por posse em outro cargo · 78 aposentadoria ·
14 exoneração · 6 falecimento · 3 mudança de órgão na carreira (via SIAPE, sem crawler) ·
1 desligamento · 13 sem ato identificado.

**Destinos (126):** TCU 67 · Senado Federal 31 · Câmara dos Deputados 15 · Ministério da Fazenda 5 ·
Executivo Federal 3 · AGU 2 · TRF-3, Transportes e Trabalho 1 cada.

**D18 — a demissão não vai ao ar** *(decisão do usuário, 14/08/2026)*. Demissão é penalidade de
processo disciplinar; o observatório mede **evasão**, e quem é demitido não escolheu sair. O
classificador continua reconhecendo o tipo — sem isso a pessoa cairia em "saída sem ato
identificado", o crawler tentaria de novo todo mês e o site afirmaria não saber o que sabe. O que
muda é o que se **grava**: `SITUACAO = DESLIGADO`, sem motivo detalhado, **sem título, sem URL e sem
cópia arquivada do ato** — porque `saidas_dou.csv` e a pasta `saidas_dou/` vão para o repositório
público e para o site. Implementado em `dou.MOTIVOS_NAO_PUBLICADOS`.
> ⚠️ Efeito colateral a conhecer: `DESLIGADO` é a **única** linha nessa situação entre 268. Um
> leitor atento nota que ela destoa das outras seis categorias. A alternativa — classificá-la como
> "saída sem ato identificado" — foi descartada por ser **falsa**: o ato existe e foi encontrado.

**Curadoria aplicada.** Das 15 sugestões de casamento com o edital, **12 foram conferidas contra o
Edital CGU nº 5 e aplicadas** em `curadoria.csv`, com a razão de cada uma registrada na
`OBSERVACAO` (erro de digitação no edital, partícula omitida, apóstrofo, sobrenome acrescentado ou
trocado após o concurso). **3 foram recusadas** e seguem em `curadoria_sugestoes.csv`:
- `LUIZ AUGUSTO GENTILUCCI ALVES` × `LUIZ AUGUSTO DA SILVA ALVES` — nome do meio **diferente**, não
  é erro de grafia nem acréscimo de sobrenome.
- `LEONARDO VIEIRA E SILVA` — **dois** candidatos no edital, e um deles (`LEONARDO SILVA PINHEIRO`)
  já casou exatamente com outra pessoa do SIAPE.

⚠️ **Pendências que a Fase 3 herda:**
- **Destino é indício, não fato** (§2.3.3) — não usar em número agregado de card sem curadoria.
- **`SITUACAO = DESLIGADO` não pode ganhar rótulo que revele o motivo** na interface (**D18**).
- **3 linhas em `curadoria_sugestoes.csv`** aguardando decisão humana.
- **O dashboard está quebrado até a Fase 3**: o `App.tsx` ainda lê `MASP`, `INSCRICAO` e os dois
  CSVs de outros concursos, que deixaram de existir. O build passa porque o Vite não valida CSV.

---

### Especificação original da fase

**Objetivo:** transformar os 49 snapshots mensais do Portal da Transparência num painel derivado,
com as **268 saídas** identificadas, o **motivo** de cada uma confirmado num ato do DOU e o
**destino** quando houver fonte.

Substitui a Fase 2 (v1). O observatório deixa de depender de lista de aprovados e de preenchimento
manual: quem saiu da CGU passa a ser **deduzido da diferença entre um mês e o outro** (**D11**),
fato verificável e reproduzível a partir de fonte pública.

### Escopo desta rodada

**Quem saiu efetivamente da CGU**, pelo SIAPE e pelo DOU, mais a **área do concurso de entrada**
(**D17**). O que fica para a **Fase 7** é o concurso de **destino**: rankingdosconcursos, bancas
(FGV/Cespe/FCC) e "AFFCs que estão estudando para sair".

Duas consequências que precisam estar claras antes de começar:

- **Somem `CADASTRO DE RESERVA` e `DESISTENTE`** do vocabulário de `SITUACAO`: são situações de quem
  nunca tomou posse. O edital (**D17**) dá o **denominador** (488 aprovados AFFC, 450 empossados =
  92,2%), mas quem nunca entrou **não vira linha** do painel.
- **Sai a seção "aguardando nomeação em outros concursos"** — é exatamente o tema adiado.

### O que a base já mostrou

Números levantados diretamente dos 49 snapshots em 14/08/2026 — **não são estimativas**, e servem
de teste de aceitação do pipeline. Todos os recortes usam **uma regra só**, a da **D13** (primeira e
última presença).

| Fato | Valor |
|---|---|
| Snapshots | 49, `202206`→`202606`, **sem lacunas** |
| Linhas empilhadas na base consolidada (**D16**) | **88.421** |
| Pessoas distintas vistas na CGU no período | 2.009 |
| Efetivo CGU `202206` → `202606` | 1.559 → **1.741** |
| **Saídas confirmadas no período** | **268** |
| Cedidos hoje (`SITUACAO_VINCULO = ATIVO EM OUTRO ORGAO`) | **183** |

> ⚠️ **Correção.** Uma versão anterior desta tabela dizia 319 cedidos. Aquele número contava **todos
> os AFFC**, inclusive os ~825 do Ministério da Fazenda — exatamente o erro contra o qual o achado 1
> adverte. Restrito à CGU (`COD_ORG_LOTACAO = 59000`), são **183**.

| Recorte | Pessoas | Saíram | % |
|---|---|---|---|
| **Entraram depois de `202206`** | 450 | **164** | **36,4%** |
| Leva inicial de posse (`202207`+`202208`) | 296 | 123 | 41,6% |
| Veteranos (já presentes em `202206`) | 1.559 | 104 | 6,7% |
| **Total** | **2.009** | **268** | 13,3% |

> ⚠️ **Correção de 14/08/2026.** Uma versão anterior desta seção trazia *"coorte de 321 pessoas,
> 136 saíram (42,4%)"*. Aquele recorte agrupava por `DATA_INGRESSO_ORGAO`, que é regra **diferente**
> da **D13** e mistura quem tomou posse em 2022 com quem apareceu depois. Os números acima
> substituem aquele — não reintroduzir o 42,4%.

**Quatro achados que a arquitetura tem de respeitar:**

1. **AFFC ≠ CGU.** A carreira é compartilhada: além da CGU (`COD_ORG_LOTACAO = 59000`, ~1.750),
   há ~825 AFFC no Ministério da Fazenda/Economia (`17600`/`17000`). O filtro é pelo **código** —
   o nome muda de grafia entre meses (`Ministério da Economia` → `MINISTERIO DA FAZENDA`, acentos
   somem). Filtrar por nome perde gente em silêncio.
2. **`Id_SERVIDOR_PORTAL` é chave estável** — zero nomes com mais de um id em 49 meses (**D12**).
3. **Existem 6 "ressurreições"** — pessoas que somem por 1 a 6 meses e voltam (uma delas ausente de
   `202302` a `202307`). Um diff par a par publicaria 6 saídas falsas sobre gente que nunca saiu.
   É por isso que a regra é **última presença** (**D13**).
4. **`DATA_INGRESSO_ORGAO` muta para 6 pessoas** em 2.009 — usar o valor **modal** da série, não o
   do último snapshot.

### Três armadilhas que a base consolidada cria

Medidas nesta rodada. As três produzem gráfico plausível e **errado** se ninguém souber delas.

1. **"Mudou de unidade" fica 3× inflado se contado por nome.** `UORG_LOTACAO` muda para **1.229**
   pessoas; `COD_UORG_LOTACAO`, para **410**. A diferença é **regrafia entre meses**, não
   movimentação (34 códigos para 38 grafias). Contar sempre pelo **código**.
2. **`UF_EXERCICIO` não existia até o fim de 2023.** O valor `-1` cobre **100%** das linhas em
   `202206`, 1.839 em `202306`, e cai para 615 hoje. Contado cru, muda para 1.452 pessoas;
   ignorando `-1`, para **114**. Uma série temporal de "auditores por UF" mostraria uma explosão
   fictícia em 2023/2024 que é só o Portal passando a preencher o campo. **Não há série de UF antes
   de 2024**; `-1` é *desconhecido*, não é UF, e não conta como mudança.
3. **Não existe dado de comissão.** `FUNCAO`, `SIGLA_FUNCAO` e `NIVEL_FUNCAO` são
   `Sem informação`/`-1` em **todas** as 88.421 linhas. O análogo federal de `desccomi`/`cdcomi` da
   SEF-MG **não tem fonte** neste arquivo — a análise "auditores em cargo comissionado" não é
   possível, e nenhuma tela deve prometê-la.

### O que o DOU entrega quando se busca por nome (validado na prática)

Uma requisição por `"Rafael Roza de Oliveira"` com `s=todos` devolveu 20 atos de uma vez, entre eles:

- **Portaria CGU 2.331 de 15/09/2022** — *"EXONERAR, a pedido, RAFAEL ROZA DE OLIVEIRA do cargo de
  Auditor Federal de Finanças e Controle"*. O motivo da saída, com ato citável.
- **Portaria CGU 1.293 de 30/06/2022** — a nomeação, com posição e lotação.
- **Edital CGU nº 5 de 13/06/2022** — o resultado final homologado. Ver o quadro abaixo: é a fonte
  da `AREA` (**D17**), e **não é mais assunto de Fase 7**.

### O edital do concurso, medido (D17)

Uma requisição a `edital-cgu-n-5-de-13-de-junho-de-2022-407806622` devolve 41.555 caracteres com o
resultado final inteiro. A estrutura, já verificada:

```
II.1 RESULTADO FINAL DE APROVADOS - AMPLA CONCORRENCIA, POR ORDEM DE CLASSIFICACAO, DE ACORDO
     COM OS CARGOS E AS UNIDADES DE LOTACAO E, NO CASO DE AFFC, AS AREAS DE ESPECIALIZACAO:
  1. AUDITOR FEDERAL DE FINANCAS E CONTROLE - AUDITORIA E FISCALIZACAO
    1.1. AC - REGIAO NORTE - ACRE
      206081364, MAUREEN DA SILVA BRANDAO, 123.5, 1O / 206072821, JAIDIR ALVES COSTA DOS SANTOS, ...
```

| Fato | Valor |
|---|---|
| Registros AFFC no ato | **527** |
| Pessoas distintas | **488** — quem concorre por cota aparece na ampla **e** na cota (39 casos) |
| Distribuição por área (registros) | Auditoria e Fiscalização 273 · Correição 102 · Contabilidade 87 · TI 65 |
| Por modalidade | Ampla Concorrência 402 · Negros 101 · PcD 24 |
| Blocos no ato | **12** = 4 áreas × 3 modalidades (AC/negros/PcD), + **3 blocos TFFC descartados** (**D7**, 212 registros) |
| Tomaram posse (série SIAPE) | 450 de 488 — **92,2%** |
| **Casamento por nome normalizado** | **410 de 450 — 91,1%** |

As 4 áreas batem **exatamente** com a lista do `CLAUDE.md`, o que é uma confirmação independente de
que o ato certo foi encontrado.

> ⚠️ **O edital tem erro de digitação, e ele custa um bloco inteiro.** Um dos cabeçalhos diz
> `AUDITOR FEDERAL DE FINANCAAS E CONTROLE` — com dois "A". Um padrão exato acha **11** blocos em
> vez de 12, perde a Contabilidade Pública da ampla concorrência e **subconta a área sem emitir
> erro nenhum**. Por isso `PADRAO_CARGO_AFFC` usa `FINANCA+S`. Foi assim que a contagem por área
> saiu errada na primeira medição desta fase.

E a armadilha, no mesmo resultado: uma **Portaria PRE 213 do TRE-MG de 12/09/2025** que cita o nome
dele — referindo-se à vacância do cargo que ele deixou no TRE **em 2022**, *antes* de entrar na CGU.
Uma regra ingênua de "ato mais recente depois da saída = destino" publicaria *"foi para o TRE-MG em
2025"*, que é falso, sobre pessoa real e nomeada. O classificador de destino tem de ser
explicitamente defensivo contra isso.

### 2.1 Camadas de dado

O ponto central: **o que é derivado nunca se mistura com o que é enriquecido ou curado.** Senão
rodar o pipeline de novo apaga o trabalho do crawler e da curadoria.

| Camada | Arquivo | Git | Quem escreve |
|---|---|---|---|
| Fonte bruta | `data/historico_transparencia_cgu/*.csv` | ignorado (~70 MB) | download manual + `filtrar_affc.py` |
| **Derivado (D16)** | **`data/historico_mensal.csv`** — 88.421 linhas, ~21 MB | commitado | `construir_painel.py` — regenerável do zero, **jamais editado à mão** |
| Derivado | `data/dados.csv` — 2.009 linhas, uma por pessoa | commitado | idem |
| Derivado | `data/serie_mensal.csv` — 49 linhas, uma por mês | commitado | idem |
| **Enriquecido** | `data/saidas_dou.csv` | commitado | `enriquecer_saidas.py` — acumulativo, só acrescenta |
| **Enriquecido (D17)** | `data/concurso_2021.csv` — 488 linhas | commitado | `concurso.py` |
| **Curado** | `data/curadoria.csv` | commitado | **humano**. Vence sobre todos os anteriores |
| Atos | `data/saidas_dou/*.html` | commitado | cópia arquivada do ato de cada saída |
| Cache | `data/cache_dou/` | **ignorado** | páginas do DOU (imutáveis depois de publicadas) |

Precedência do merge: **curadoria > DOU > SIAPE**.

> **Assunção sobre carregamento (reversível, registrar):** o dashboard inicial lê só `dados.csv`
> (~300 KB) e `serie_mensal.csv`; o `historico_mensal.csv` (2,8 MB gzipado) é carregado **sob
> demanda**, nas páginas que precisam da série por pessoa. Se pesar, o mesmo pipeline emite o
> **modelo de vigência** — uma linha por período estável em vez de uma por mês, **10.840 linhas
> (12%)**, mesma informação — sem mudar mais nada no resto da arquitetura.

### 2.2 Esquema do `historico_mensal.csv` (D16) — a base consolidada

Uma linha por **(competência × pessoa)**: 88.421 linhas, 17 colunas das 43 originais.

**Acrescentadas (3):** `MES` (AAAAMM) · `CONCURSO` · `AREA`

**Mantidas da origem (14):** `ID_SERVIDOR_PORTAL` · `NOME` · `MATRICULA` · `CLASSE_CARGO` ·
`PADRAO_CARGO` · `COD_UORG_LOTACAO` · `UORG_LOTACAO` · `COD_UORG_EXERCICIO` · `UORG_EXERCICIO` ·
`COD_ORG_EXERCICIO` · `ORG_EXERCICIO` · `SITUACAO_VINCULO` · `UF_EXERCICIO` · `DATA_INGRESSO_ORGAO`

**Descartadas (29)** — as 23 constantes ou sempre vazias já medidas (`DESCRICAO_CARGO`,
`REFERENCIA_CARGO`, `NIVEL_CARGO`, `SIGLA_FUNCAO`, `NIVEL_FUNCAO`, `FUNCAO`, `CODIGO_ATIVIDADE`,
`ATIVIDADE`, `OPCAO_PARCIAL`, `COD_ORG_LOTACAO`, `ORG_LOTACAO`, `COD_ORGSUP_*`, `ORGSUP_*`,
`COD_TIPO_VINCULO`, `TIPO_VINCULO`, `REGIME_JURIDICO`, `DATA_INICIO_AFASTAMENTO`,
`DATA_TERMINO_AFASTAMENTO`, `DATA_NOMEACAO_CARGOFUNCAO`, `DIPLOMA_*`,
`DOCUMENTO_INGRESSO_SERVICOPUBLICO`, `DATA_DIPLOMA_INGRESSO_SERVICOPUBLICO`), mais `CPF`
(mascarado, sem uso), `JORNADA_DE_TRABALHO` (muda para 10 pessoas em 2.009) e
`DATA_INGRESSO_CARGOFUNCAO`.

Regras de preenchimento:

- `CONCURSO` é **derivado** (**D13**): primeira presença em `202206` → `VETERANO`; depois →
  `CGU-2021`. Quando o CGU-2026 chegar, é só mais um valor (**D9**).
- `AREA` vem do `concurso_2021.csv` (**D17**), por casamento de nome. **Fica vazia quando não
  casar** — não chutar (regra do `CLAUDE.md`).
- `CONCURSO` e `AREA` são atributos da **pessoa**, constantes em todas as linhas dela.
  Ficam **desnormalizados** de propósito: é o que torna a base usável direto pela UI, sem join.
- A base é **CGU por construção** (`COD_ORG_LOTACAO = 59000`), e é por isso que essa coluna sai.
  Os 3 casos de "mudou de órgão na carreira" saem do conjunto e são tratados no `dados.csv`, que lê
  o arquivo AFFC completo.
- Contagens de unidade usam **`COD_UORG_*`**, nunca o nome (armadilha 1). `UF_EXERCICIO = -1` é
  **desconhecido** (armadilha 2).

### 2.2.1 Esquema do `dados.csv` publicado

Uma linha por pessoa que esteve na CGU no período (~2.009). **Derivado do
`historico_mensal.csv`**, não dos snapshots.

- **Identidade e coorte** — `ID_SERVIDOR_PORTAL` (chave, **D12**) · `NOME` · `CONCURSO`
  (`VETERANO` | `CGU-2021`) · `AREA` (**D17**) · `MES_ENTRADA` (AAAAMM) · `DATA_POSSE`
- **Concurso de entrada (D17, vazios para `VETERANO`)** — `INSCRICAO` · `POSICAO_CONCURSO` ·
  `NOTA` · `MODALIDADE` (AC / PcD / negros) · `UF_VAGA`
- **Situação e lotação** — `SITUACAO` · `UNIDADE` (de `UORG_LOTACAO`, normalizada) · `UF` ·
  `CEDIDO` (SIM/NÃO) · `ORGAO_EXERCICIO`
- **Saída** — `MES_SAIDA` · `SAIDA_PROVISORIA` · `MOTIVO_SAIDA` · `FONTE_MOTIVO` · `DATA_SAIDA`
  (data de efeito do ato) · `DATA_PUBLICACAO_SAIDA` · `ATO_SAIDA_TITULO` · `ATO_SAIDA_URL` ·
  `ATO_SAIDA_ARQUIVO`
- **Destino** — `ORGAO_DESTINO` · `CARGO_DESTINO` · `DATA_DESTINO` · `FONTE_DESTINO` · `URL_DESTINO`
- **Procedência (D14)** — `VERIFICADO` (SIM/NÃO) · `VERIFICADO_EM` · `OBSERVACAO`

**Vocabulário novo de `SITUACAO`:** `EM EXERCÍCIO` · `EXONERADO` · `VACÂNCIA` (posse em outro cargo
inacumulável) · `APOSENTADO` · `FALECIDO` · **`DEMITIDO`** (penalidade disciplinar — ver achado 3
da §2.3.1, tem decisão editorial pendente) · `SAÍDA SEM ATO IDENTIFICADO` · `MUDOU DE ÓRGÃO NA
CARREIRA`. Somem `DESISTENTE`, `CADASTRO DE RESERVA`, `AFASTAMENTO PRELIMINAR À APOSENTADORIA`,
`POSSE JUDICIAL` e `INAPTO ADMISSIONAL`.

`FONTE_*` ∈ `SIAPE` | `DOU` | `RANKING` | `BUSCA` | `MANUAL` | vazio.

### 2.3 Tarefas

Tudo **stdlib only**: o CI não roda `pip install`, e nem `requests` nem `bs4` estão instalados na
máquina. Os dois crawlers atuais já são stdlib pura (urllib + fallback `curl`).

- [ ] **`scripts/dou.py`** (nova biblioteca) — extrair de `dou_saidas_affc.py` o que já é genérico e
      **está validado**, sem reescrever: `normalizar()` (`:132-136`), `baixar()` com o fallback
      `curl` (`:139-167`), o parse do JSON embutido em `BuscaDouPortlet_params` (`:187-198`),
      `extrair_texto()` (`:206-215`), `salvar_ato()`/`nome_arquivo()` (`:254-306`). Parametrizar
      `buscar_janela()` (`:170-198`) para receber o `q` e `e_da_cgu()` (`:201-203`) para receber o
      órgão. **Acrescentar o que não existe hoje:** `time.sleep` entre requisições (não há
      **nenhum** rate limit) e cache em disco por `urlTitle` (não há cache algum).
      `dou_saidas_affc.py` passa a importar daqui, com o comportamento da Fase 2.5 intacto.
- [ ] **`scripts/painel.py`** (nova biblioteca) — a derivação, isolada e testável:
  - filtra `COD_ORG_LOTACAO == '59000'`; `presenca[id]` = meses em que a pessoa aparece
  - `MES_ENTRADA` = primeira presença · `MES_SAIDA` = mês seguinte à **última** presença
  - **saída ⟺ última presença ≠ último snapshot** — as 6 ressurreições dissolvem sozinhas, que é a
    razão de a regra ser essa e não diff par a par (**D13**)
  - `SAIDA_PROVISORIA = SIM` quando `MES_SAIDA` é o snapshot mais novo — um mês de ausência não é
    prova, e os 6 casos históricos provam
  - **subcaso resolvido sem crawler:** some do conjunto CGU mas continua no arquivo AFFC com outro
    `COD_ORG_LOTACAO` (3 casos) → `MOTIVO_SAIDA = MUDOU DE ÓRGÃO NA CARREIRA`, `ORGAO_DESTINO` = o
    órgão novo, `FONTE_DESTINO = SIAPE`
  - coorte: `MES_ENTRADA == 202206` → `VETERANO`; senão `CGU-2021`
  - **empilha** os snapshots em `historico_mensal.csv` (**D16**), com `MES`, `CONCURSO` e `AREA`
  - normalizar `UORG_LOTACAO` (38 grafias para 34 códigos) com tabela de-para explícita:
    `CONTROLADORIA-GERAL DA UNIAO` e `CGU` → mesma unidade sede; `CONTR REGIONAL DO ESTADO - RJ` →
    `CGU-Regional/RJ`. **A identidade da unidade é o `COD_UORG_LOTACAO`** — o nome é só rótulo
    (armadilha 1)
- [ ] **`scripts/concurso.py`** (CLI, **D17**) — baixa **um** ato do DOU e produz
      `data/concurso_2021.csv`. Parametrizado por ato, para que o CGU-2026 caia pronto.
  - Ato: `https://www.in.gov.br/web/dou/-/edital-cgu-n-5-de-13-de-junho-de-2022-407806622`.
    Reusar `baixar()` e `extrair_texto()` da `dou.py` — **nada de HTTP novo**.
  - Estrutura já verificada: bloco `N. AUDITOR FEDERAL DE FINANCAS E CONTROLE - <ÁREA>`, depois
    `N.N. <região/UF da vaga>`, depois registros `<inscrição>, <NOME>, <nota>, <classificação>º`
    separados por `/`. A modalidade (AC / PcD / negros) vem do cabeçalho `II.N`.
  - **Descartar os 3 blocos `TECNICO FEDERAL`** (**D7**).
  - Saída: `INSCRICAO` · `NOME` · `AREA` · `NOTA` · `POSICAO_CONCURSO` · `MODALIDADE` · `UF_VAGA`.
  - **Casamento com o SIAPE por nome normalizado.** Fica em **91,1%** (410 de 450).
    ⚠️ **A meta de ">97%" que esta tarefa trazia foi retirada: é inatingível, e não por bug.**
    Os 40 que faltam foram investigados um a um e se dividem em:
    - **nomes que mudaram entre 2022 e hoje** — `VITORIA TEIXEIRA ROCHA` no edital é
      `VITORIA TEIXEIRA ROCHA TUMER` no SIAPE; `ISABELLE BENLOLO DE AZEVEDO` é
      `ISABELLE BENLOLO RODRIGUES`. Casamento aproximado automático resolveria — e atribuiria
      área e nota à pessoa errada quando errasse. **Não fazemos isso** (**D12**/**D14**);
    - **gente que não está no ato mesmo** — 6 com posse em 2016 (vieram por outra via, não pelo
      concurso), e os demais provavelmente de retificação posterior.
    O que não casa fica **vazio**, e cada quase-casamento vira uma linha em
    `data/curadoria_sugestoes.csv` para conferência humana. **Nada dali é aplicado sozinho.**
  - **Homônimo (D12):** nome **não** é chave. Casamento ambíguo (dois aprovados com o mesmo nome
    normalizado) fica vazio e vai para `curadoria.csv` resolver à mão.
- [ ] **`scripts/construir_painel.py`** (CLI) — roda `painel.py`, faz o merge das camadas e escreve
      `historico_mensal.csv` (**D16**), `dados.csv`, `serie_mensal.csv` e
      `public/alteracoes-registros.json`. Determinístico e idempotente.
- [ ] **`scripts/enriquecer_saidas.py`** (CLI) — para cada saída ainda sem `MOTIVO_SAIDA`:
  1. **Uma requisição por pessoa:** `q="<NOME COMPLETO>"`, `s=todos`, `exactDate=all`. Sem
     janelamento — um nome não chega perto do teto de 50 (o caso testado devolveu 20 na vida
     inteira); se vierem exatamente 50, aí sim refazer por janelas. **`s=todos` é obrigatório**:
     atos de pessoal saem na Seção 2, e o crawler da Fase 2.5 varre por frase, não por nome.
  2. **Motivo** — só atos com CGU no `hierarchyList`, que casem `PADRAO_CARGO` e citem o nome.
     Classificar com os padrões **já validados** da Fase 2.5 (`PADROES`, `PADRAO_VACANCIA_MOTIVO`,
     `PADROES_NAO_E_SAIDA`, `PADRAO_EXONERACAO_EFETIVA`), preservando as duas invariantes
     documentadas lá: os padrões já vêm normalizados (não passar por `normalizar()`, senão `\s` vira
     `\S`) e tipo descartado faz `continue`, **nunca** `return None`. Escolher o ato mais próximo de
     `MES_SAIDA`. **Acrescentar `FALECIMENTO`** — publicar "exonerado" para quem morreu seria erro
     grave.
  3. **Guarda de homônimo (barata e real):** o Portal mascara a matrícula como `166****`, ou seja,
     **os 3 primeiros dígitos do SIAPE ficam visíveis**, e os atos do DOU escrevem o SIAPE por
     extenso (*"matrícula SIAPE nº 2576295"*). Quando o ato traz matrícula, exigir que os 3
     primeiros dígitos batam.
  4. **Destino** — um ato só é candidato se **todas** valerem: publicado **depois** do ato de saída;
     `hierarchyList` **sem** CGU; o texto casa nomeação/posse (`NOMEAR`, `EMPOSSAR`, `TOMAR POSSE`)
     com a pessoa como objeto; **não** é `declarar vago`/`dispensar`/`exonerar` (isso é o emprego
     **anterior** liberando a pessoa — a armadilha do TRE); e a data está a **≤ 24 meses** da saída.
     Órgão sai do `hierarchyStr`; `FONTE_DESTINO = DOU`.
  5. Sem destino no DOU → estágio **opcional** `--externo`: `rankingdosconcursos.com.br` e busca web
     → `FONTE_DESTINO = RANKING`/`BUSCA`, `VERIFICADO = NÃO`.
     > ⚠️ **Risco conhecido:** o site tem "Busca por Nome", mas o endpoint **não é descobrível** pela
     > página renderizada. **Fazer um spike antes de programar esse estágio**; se não render, ele
     > fica de fora e o destino segue "não identificado". O resto da fase **não depende dele**.
  6. Gravar em `saidas_dou.csv` + arquivar o HTML do ato em `data/saidas_dou/`.
- [ ] **`scripts/atualizar.py`** (CLI) — o comando único da **D15**: `filtrar_affc` →
      `construir_painel` → `enriquecer_saidas` → `construir_painel`.

**Custo do backfill:** 268 nomes × (1 busca + ~10 atos) ≈ 3.000 requisições. A 1 req/s, ~50 minutos,
uma vez só. Com o cache em disco, reexecutar fica quase instantâneo.

> **Nota de arquitetura (D15):** o CI **não precisa** do histórico de 70 MB, porque o mês novo é
> diffado contra as linhas `EM EXERCÍCIO` do próprio `dados.csv` commitado. Isso deixa a porta
> aberta para automatizar depois sem refazer nada.

### 2.3.1 Achados da execução (14/08/2026)

Cinco defeitos encontrados ao rodar de verdade. **Nenhum quebrava o script** — todos os cinco
produziriam um site plausível e errado, que é o modo de falha que este projeto já conhece.

1. **Zero à esquerda na matrícula anulava a guarda de homônimo — ao contrário.**
   O Portal mascara a matrícula em 7 posições **preservando o zero** (`014****`); o DOU escreve o
   número **sem ele** (`149262`). Comparado cru, o ato certo era tido como *de outra pessoa* e
   descartado. Uma aposentadoria real sumiu por isso. Agora os dois lados vão a `zfill(7)`.
   Medido: 6 de 6 casam com o ajuste, 5 de 6 sem ele.
2. **A posse no destino costuma vir ANTES do ato de saída da CGU.** A pessoa toma posse no TCU em
   outubro, a CGU declara o cargo vago em dezembro. A janela original exigia ato **posterior** à
   saída e perdia justamente os destinos mais bem documentados. Agora a janela é
   **[-6, +24] meses**. Reconferido: a armadilha do TRE (ato de 2025 sobre saída de 2022) continua
   corretamente recusada, porque os atos daquele órgão ou estão fora da janela ou são de
   desligamento (`declarar vago`/`dispensar`), nunca de nomeação.
3. **Faltava o tipo `demissao`.** Demissão é penalidade de processo disciplinar (art. 132 da Lei
   8.112/90), não exoneração, e o ato **não cita o cargo** — diz só "aplicar a penalidade de
   demissão ao servidor Fulano, matrícula SIAPE nº…". Como `classificar` exigia o cargo, esses
   casos caíam em "saída sem ato identificado". Agora existe o tipo, e a prova do cargo é
   dispensada **quando a matrícula já provou a identidade** (sem matrícula, a exigência continua:
   nome sozinho casa homônimo).
   > ⚠️ **Decisão pendente para o usuário:** publicar `DEMITIDO`, com link para o ato, é afirmação
   > pública sobre penalidade disciplinar de pessoa nomeada. O ato é público (DOU), mas a escolha
   > de exibi-lo na interface é editorial, não técnica. Enquanto não se decidir, o dado fica no
   > `dados.csv` e **a Fase 3 decide se e como mostra**.
4. **`SAIDA_PROVISORIA` nunca era marcada.** A condição comparava o mês da saída com o mês
   *seguinte* ao último snapshot — que por construção não existe. As 2 saídas mais recentes eram
   tratadas como definitivas com um único mês de ausência observado. Corrigido para comparar com o
   próprio último snapshot; essas saídas agora ficam **fora do crawl** até o mês seguinte confirmar.
5. **O typo do edital** (`FINANCAAS`) — ver o quadro do D17 acima.
6. **Dois falsos positivos de destino, achados conferindo os 95 à mão.** A distribuição das
   distâncias entre o ato de destino e o mês da saída denunciou os dois: **90 dos 95 caem entre
   −4 e +4 meses** (pico em −1/−2, exatamente o esperado — a posse vem antes da vacância), e havia
   um **vazio limpo entre +4 e +13**. Os 5 do outro lado do vazio não se sustentaram:
   - *"NOMEAR Fulano para exercer o **Cargo Comissionado Executivo**, CCE…"* no COAF/BCB — assumir
     chefia em outro órgão não é "ter ido" para aquele órgão. É a mesma classe de erro que a Fase
     2.5 pegou na exoneração, e a função de destino não tinha essa guarda;
   - um **ato-lista** (resultado de concurso com dezenas de nomes e notas) em que o verbo "NOMEAR"
     casava num canto e o nome da pessoa em outro, sem que o ato a nomeasse.
   Correções: `e_ato_de_nomeacao` passou a rejeitar cargo em comissão e tabela de resultado, e a
   janela superior caiu de **+24 para +6 meses** — corte dentro do vazio, que mantém todo o sinal
   e descarta o ruído.
   > **A primeira tentativa de corrigir isso estava errada, e vale registrar por quê.** Tentei
   > barrar o ato-lista medindo a **distância** entre o verbo "nomear" e o nome: 400 caracteres.
   > Derrubou **63 destinos legítimos** junto. Medindo os 85 destinos válidos, a mediana é de
   > **802 caracteres** e não existe corte limpo — atos de nomeação são longos e trazem o nome
   > bem depois do verbo. Distância era o instrumento errado; o que separa os dois casos é a
   > **forma do ato**, e não o quão longe o nome está. O detector de tabela
   > (`<inscrição>, <NOME>, <nota>` repetido 5+ vezes) resolve sem falso negativo.
7. **`extrair_texto` caía para a página HTML inteira quando não achava a div do ato.** Algumas URLs
   do DOU são **página-índice** (sumário do dia, várias matérias), sem `.texto-dou` — e o fallback
   entregava ~27 mil caracteres de JavaScript de analytics adiante, como se fossem o ato. **Dois
   destinos foram atribuídos a pessoas reais com base nesse lixo.** Medido: das 1.618 páginas de
   ato no cache, **zero** dependiam do fallback. Agora devolve string vazia, e o ato é pulado.
8. **Nome é prefixo de nome — limitação conhecida, não resolvida.** "LUIZ CARLOS DE ALMEIDA" está
   contido em "LUIZ CARLOS DE ALMEIDA SOUZA", que é outra pessoa; foi assim que uma lista de 172 mil
   registros do Judiciário virou "destino" de um auditor. Exigir palavra inteira **não resolve**: o
   texto do DOU vem todo em caixa alta, e aí `ALMEIDA SOUZA` (outra pessoa) e `OLIVEIRA DO CARGO`
   (a pessoa certa) ficam indistinguíveis pelo delimitador. Quem segura esse caso é o **conjunto** —
   detector de tabela, guarda de matrícula e janela de datas —, nunca o casamento de nome sozinho.
   Está documentado em `cita_nome()` para ninguém "consertar" achando que melhora.
9. **Rótulo de destino genérico.** `hierarchyStr` começa pelo poder, não pelo órgão: publicar
   *"foi para o Poder Judiciário"* é verdadeiro e inútil. `orgao_do_ato()` desce um nível quando o
   primeiro é `Poder Legislativo`/`Poder Judiciário`/`Poder Executivo Federal`, e aí sai
   "Senado Federal", "Superior Tribunal Militar".

10. **A auditoria dos 87 destinos, um a um, achou mais 9 errados** — e mostrou que amostrar não
    bastava. A distribuição de datas parecia limpa (todos entre −4 e +4 meses), mas
    **lista de nomeação e lista de classificação são publicadas na mesma época e têm a mesma
    forma**: uma sequência de nomes. A data não separa as duas. O que separa é **o que acompanha
    o nome**:
    ```
    classificação : "BRENO HONORATO NASCIMENTO 346.35 9 PCD"          <- NOTA (decimal)
    nomeação      : "JAIDIR ALVES COSTA DOS SANTOS 388260521 DRF - RIO BRANCO"
                                                   ^matrícula  ^lotação
    ```
    Estar classificado num concurso não é ter sido nomeado nele. Seis auditores tinham destino
    vindo de lista de classificação.
11. **"Decorrente da posse de X" é ambíguo, e o nome desempata.** As duas redações existem:
    - *"cargo VAGO EM DECORRÊNCIA DA POSSE DE **Hyago** em outro cargo"* → é o emprego anterior
      do Hyago dando baixa. **Não é destino.**
    - *"NOMEAR **André**, EM CARGO VAGO DECORRENTE DA POSSE DE (outra pessoa)"* → o André está
      sendo nomeado na vaga que outro deixou. **É destino.**
    Um padrão cego a nome erra os dois lados: rejeitava o André e aceitava o Hyago.
    `descreve_saida_da_pessoa()` testa se **o nome da pessoa vem logo depois** de "posse de".
12. **Rótulo de destino: a AGU pendura sob a Presidência da República.** Quem foi nomeado
    Procurador Federal aparecia como *"foi para a Presidência da República"* — verdadeiro na
    hierarquia do DOU e enganoso para o leitor. `PRESIDENCIA DA REPUBLICA` entrou na lista de
    níveis guarda-chuva, e agora sai "Advocacia-Geral da União".

> **Método que funcionou, para repetir nas próximas fases:** classificar *todos* os registros por
> categoria automática, e conferir à mão **um exemplar de cada categoria** — não uma amostra
> aleatória. Foi assim que os 9 apareceram; a amostra aleatória de 10 tinha passado por 4 deles
> sem que a distribuição de datas denunciasse nada.

### 2.3.3 A camada de DESTINO é a mais frágil das três — e por quê

Isto é o achado mais importante da fase, e vale mais que qualquer número: **motivo e destino não
têm o mesmo grau de confiabilidade, e tratá-los igual seria erro.**

- **Motivo** é uma leitura direta: o ato é *da CGU*, cita a pessoa, e o verbo diz o que aconteceu
  ("exonerar", "conceder aposentadoria", "declarar vago por posse em outro cargo"). 95% de
  cobertura, e as conferências à mão não acharam um único erro.
- **Destino** é uma *inferência*: "um ato publicado pelo órgão Y menciona X perto de um verbo de
  nomeação, logo X foi para Y". Essa inferência é fraca, porque o DOU menciona pessoas por muitos
  motivos além de nomeá-las.

Formatos de falso positivo encontrados, **cada um numa rodada diferente de auditoria** — a lista
não é hipotética, todos ocorreram nos dados reais:

| O ato diz | Por que não é destino |
|---|---|
| "NOMEAR X para exercer o **Cargo Comissionado Executivo**, CCE 1.07" | assumir chefia não é ir para o órgão |
| tabela `<inscrição>, <NOME>, <nota>` | estar classificado não é ser nomeado |
| "CLASSIFICACAO CANDIDATO 10 (AMPLA) X" | idem, outro formato |
| "cargo vago **em decorrência da posse de X**" | é o emprego anterior dando baixa |
| "cargo **anteriormente ocupado por X**" | X é quem saiu; quem entra é outro |
| "em vaga decorrente da **vacância do cargo de X**" | idem |
| "**desistência** de nomeação ... candidatos: ..., X, ..." | o ato diz que X **não** foi |
| "INTERESSADA: X. ASSUNTO: concurso. **Desistência**" | idem, outra redação |
| "**TORNAR SEM EFEITO** a nomeação de X" | a nomeação foi anulada |
| página-índice do DOU (sem `.texto-dou`) | não é ato nenhum |

E um limite que **nenhum padrão resolve**: o `hierarchyStr` do próprio DOU às vezes está errado.
Um ato que começa com "PORTARIA-TCU Nº 49" e nomeia para "Auditor Federal de Controle Externo do
quadro desta Secretaria" vinha indexado sob *Ministério dos Transportes*. O órgão publicado sai da
metadados do DOU, e a metadados erra.

**Consequência prática, e é a razão de a D14 existir:** todo destino vai ao ar com
`FONTE_DESTINO = DOU` e `VERIFICADO = NÃO`. A precisão residual **não está estabelecida** — o que
se sabe é que 10 formatos de erro foram fechados e testados, não que não haja o 11º. A Fase 3 deve
tratar destino como **indício com fonte**, nunca como fato apurado: mostrar o selo, linkar o ato, e
**não** usar destino não verificado em número agregado de card. Quem fecha a conta é a curadoria
humana, via `curadoria.csv`.

### 2.3.2 Teste de regressão

`scripts/testar_dou.py` — **25 invariantes, sem rede, sem dependência**. Cada caso é um erro que já
aconteceu neste projeto. Rodar **sempre** que mexer nos padrões de `dou.py`; o `CLAUDE.md` registra
essa obrigação. Cobre: exoneração de CCE que não é saída, o "declarar vago" que o DOU usa no lugar
de "vacância", a aposentadoria que era engolida pelo teste de vacância, o zero à esquerda da
matrícula, lista de classificação × lista de nomeação, as duas leituras de "decorrente da posse
de", o rótulo de órgão sob poder/Presidência e o fallback de extração.

### 2.4 Aposentar nesta fase

- [ ] `data/processador.ipynb` — pandas (não instalado), reescreve `dados.csv` in place, caminhos
      relativos frágeis. Substituído por `construir_painel.py`.
- [ ] `scripts/generate-alteracoes.js` + `.github/workflows/update-alteracoes.yml` — o changelog
      passa a vir do diff mensal, com data real, em vez de arqueologia de commits git. O script
      já está quebrado de qualquer jeito: não existe mais coluna `MASP`, então `keyForRecord`
      (`:100-105`) cai silenciosamente para `INSCRICAO`.
- [ ] `scripts/reorder_dados.py` — `AREA_ORDER` (`:10`) ainda é de MG e o `dados.csv` passa a nascer
      ordenado pelo pipeline.
- [ ] `data/historico transparencia_legado_sefmg/` (27 CSVs) e `data/mudancas_legado/` (26 `.txt`).
- [ ] `data/outros_concursos.csv` e `data/aprovacoes_outros_concursos.csv` — tema da Fase 7.

**Concluída quando:**

- `atualizar.py` roda de ponta a ponta sobre os 49 snapshots
- `historico_mensal.csv` tem **88.421 linhas** e 17 colunas, e nenhuma das 29 descartadas reaparece
- `dados.csv` tem ~2.009 linhas e 268 saídas; `serie_mensal.csv` tem 49 linhas
- **os totais batem com as tabelas de "O que a base já mostrou"** — 2.009/268, 450/164, 296/123,
  1.559/104. Divergência ali é **bug no pipeline**, não no dado
- `concurso_2021.csv` tem **488 linhas AFFC**, nenhuma TFFC, distribuição 307/94/61/26, e casamento
  com o SIAPE **> 97%**
- **10 saídas conferidas à mão** — `ATO_SAIDA_URL` abre o ato certo, citando a pessoa, com o motivo
  que o texto diz. Foi assim que a Fase 2.5 pegou 3 bugs silenciosos
- **5 áreas conferidas à mão** contra o edital publicado

---

## [ ] Fase 3 — Dashboard sobre dado real *(reescrita em 14/08/2026)*

**Objetivo:** o dashboard deixa de mostrar 14 linhas de EXEMPLO e passa a mostrar os 268 casos
reais. Reaproveita a estrutura da SEF-MG onde ela serve e remove o que a **D11** deixou sem fonte.

### 3.1 Base comum (fazer primeiro)

Hoje existem **5 cópias** do parser de CSV e do parser de data (`App.tsx:83-127` e `:418-466`,
`DetailedTableApp.tsx:196-240` e `:279-323`, `HistoryPage.tsx:80-133`,
`relatorio_impressao.tsx:21-53`), com semânticas **divergentes** — célula vazia vira `null` no
`App.tsx:121` e `''` no `DetailedTableApp.tsx:235`. Com o esquema mudando inteiro, manter 5 cópias
é multiplicar o erro por 5.

- [ ] `evasao/lib/dados.ts` — **um** parser `;`-CSV, **um** parser `DD/MM/AAAA`, e o `fetch` com a
      lista de caminhos alternativos (hoje repetida 4 vezes, com até 10 candidatos cada). Todas as
      páginas importam daqui.
- [ ] `types.ts` — `RegistroAuditor` reescrito para o esquema da 2.2. Hoje o tipo existe e
      **nenhum componente o usa** (tudo é `any`); passar a usá-lo de fato.
- [ ] `constants.ts` — `SITUACOES` com o vocabulário novo; `CONCURSOS` mantém `CGU-2021` e
      `VETERANO`, e as **áreas do `CGU-2021` passam a vir conferidas contra o edital** (**D17**):
      `Auditoria e Fiscalização`, `Correição e Combate à Corrupção`, `TI` e `Contabilidade Pública
      e Finanças` — as 4 que o ato traz, com 307/94/61/26 aprovados. Hoje só `DATA_INICIO_OBSERVACAO` é
      importado de lá; os outros 7 símbolos não têm consumidor nenhum.

### 3.2 Cards

| # | Card | Fonte |
|---|---|---|
| 1 | **Dias sem perder um Auditor** | inalterado — DOU, Fase 2.5 (**D10**) |
| 2 | **Saíram da CGU** — 268 desde jun/2022 | `dados.csv`; rodapé com a quebra por motivo |
| 3 | **Evasão de quem entrou depois de jun/2022** — **36,4% (164 de 450)** | `dados.csv` filtrado por `CONCURSO` |
| 4 | **Efetivo atual** — 1.741 (era 1.559 em jun/2022) | `serie_mensal.csv` |

Sai o card "aguardando nomeação em outros concursos". `CounterCard.tsx` não muda — é puramente
apresentacional.

### 3.3 Gráficos

- [ ] **Efetivo mensal + entradas/saídas** — `EvasionChart` sobre `serie_mensal.csv`. O componente
      já empilha 4 séries e já tem modo de rótulo rotacionado; aproveitar.
- [ ] **Saídas por motivo** — exoneração / vacância / aposentadoria / sem ato identificado.
- [ ] **Destinos** — `EvasionTable`, agora com dado real. Cada destino exibe os **dois selos da
      D14**: de onde veio a informação e se foi verificada por gente. Corrigir "DOE" → "DOU"
      (`EvasionTable.tsx:99,101,103`).
- [ ] **Por unidade / UF** — `agregarPorUnidade` (`App.tsx:849-920`) aproveitável quase como está;
      hoje só considera `EXONERADO` (`App.tsx:1228`) e passa a considerar toda saída.
- [ ] **Curva de permanência da coorte 2022** (novo) — % remanescente por mês desde a posse. É a
      visualização que um observatório de evasão existe para mostrar, e a base agora dá.

### 3.4 Tabela detalhada e histórico

- [ ] `DetailedTableApp.tsx` — colunas do esquema novo; chave React por `ID_SERVIDOR_PORTAL`.
      O **filtro de área continua existindo** (**D17** dá a fonte), mas com as áreas reais do
      CGU-2021 — `Auditoria e Fiscalização` · `Correição e Combate à Corrupção` · `TI` ·
      `Contabilidade Pública e Finanças` — e mais a opção "sem área" para veteranos e não-casados.
      Entram também **coorte**, **unidade**, **motivo de saída** e **verificado**. Cai o layout
      duplo `VETERANO` (9 colunas) × padrão (11) de `:669-707` — vira uma tabela só — e o default
      `'FISCALIZAÇÃO'` (`:6`, `:415`, `:420`) some.
- [ ] `HistoryPage.tsx` — `alteracoes-registros.json` passa a ser gerado pelo diff mensal; o bloco
      `commit` (hash/autor/mensagem) vira `{ mes, data }`. Some o conteúdo de MG que **hoje aparece
      na tela** (`observatoriosefmg`, `ISS BH`, `SEFAZ PE`) e que já não casa com nenhuma linha do
      `dados.csv` atual.
- [ ] `relatorio_impressao.tsx` — listas passam a ser por motivo de saída.
- [ ] Limpar `console.log` de produção — `EvasionChart.tsx:189-192` dispara **a cada hover**;
      `HistoryPage.tsx` tem ~15.

### 3.5 Remover

- [ ] `AprovadosOutrosConcursosTable.tsx` (335 linhas) · `agregarPorAprovacaoOutroConcurso`
      (`App.tsx:983-1166`) · `contarAuditoresEmExercicioAguardandoNomeacao` (`App.tsx:1170-1221`)
- [ ] `DetailedTable.tsx` (445 linhas, **não importado por ninguém**) · `Navigation.tsx` (idem)
- [ ] `table.html` + `table.tsx` — **fora do build** (`vite.config.ts:15-20`) e ainda carregam o GA
      `G-NZ84J0PJBF` que a **D2** mandou remover
- [ ] Código morto de KPI: `diasDesdeUltimaEvasao` (`App.tsx:237`, `:392-399`),
      `dataUltimaExoneracaoFormatada` (`:1326-1328`), `diasRecorde` (`:1354-1379` — pendência aberta
      da Fase 2.5)

### 3.6 Deploy

- [ ] `deploy-pages.yml` copia `evasao/data/*.csv` com glob **raso** — subpasta não entra.
      Acrescentar `data/saidas_dou/` do mesmo jeito que já se fez com `dias_sem_perder_AFFC/`,
      senão os links dos atos dão 404.
- [ ] Remover o `workflow_run` de `update-alteracoes.yml` junto com o workflow.

**Concluída quando:** `npm run build` OK, `npx tsc --noEmit` sem erro **novo** (os 6 pré-existentes
seguem para a Fase 6), os 4 cards e os 5 gráficos batem com `dados.csv`/`serie_mensal.csv`, e
**nenhum destino aparece sem os dois selos da D14**.

---

## [x] ~~Fase 4 — Pipeline de dados~~ — **absorvida pela Fase 2 (v2)** em 14/08/2026

Esta fase existia para "repor a esteira de atualização contra fontes federais". Com a **D11**, a
esteira **é** o assunto da Fase 2 (v2) e foi especificada lá em detalhe. O que restava aqui:

- `processador.ipynb`, `generate-alteracoes.js`, `reorder_dados.py`, as pastas de legado de MG e os
  dois CSVs de outros concursos → **§2.4 da Fase 2 (v2)** ("Aposentar nesta fase").
- Regenerar `alteracoes-registros.json` → passa a ser produto do `construir_painel.py`, a partir do
  diff mensal, com data real em vez de arqueologia de commits git.
- **Carregar a lista da FGV** e **derivar os veteranos por cruzamento de nome** → **cancelado**.
  A coorte passa a ser derivada da primeira aparição na série mensal (**D11**/**D13**), que é dado
  direto e não depende de casar nome normalizado entre duas pontas — cruzamento que a própria fase
  já reconhecia como arriscado por homônimos, e que a **D12** agora proíbe.
- A lista de aprovados volta na **Fase 7**, e por um caminho melhor: ela está publicada no próprio
  DOU (Edital CGU nº 5 de 13/06/2022), com inscrição, nota e classificação.

**Registro que continua valendo** (não repetir levantamento):

- **Série da CGU baixada e filtrada** — `evasao/data/historico_transparencia_cgu/`, 49 snapshots
  mensais (`202206`–`202606`), reduzidos aos AFFC por `evasao/scripts/filtrar_affc.py`.
- Os CSVs brutos do portal têm **~420 MB cada** (o GitHub recusa acima de 100 MB); filtrados, os 49
  somam ~70 MB. A pasta está **no `.gitignore`**: dado de trabalho regenerável, não pertence ao repo.
- O filtro casa `AUDITOR FEDERAL DE FINANCAS E CONTROLE` normalizado (sem acento, espaços
  colapsados), o que exclui o TFFC por construção (**D7**). Encoding de entrada é **latin-1** — ler
  como UTF-8 quebra no primeiro "ç".
- ⚠️ **Mas o filtro de cargo não basta:** o arquivo filtrado tem ~825 AFFC do Ministério da
  Fazenda/Economia além dos ~1.750 da CGU. Ver achado 1 da Fase 2 (v2).

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
- [x] ~~`.github/workflows/update-alteracoes.yml` — revisar caminhos~~ e ~~`generate-alteracoes.js:8` — ainda escreve em `['public', 'dist']`~~ → **caem por descarte**: os dois são aposentados na Fase 2 (v2), §2.4.
- [ ] `evasao/tsconfig.json:13-15` — acrescentar `"vite/client"` ao `types` (hoje só `"node"`), que resolve os 3 erros de `import.meta.env`. Corrigir também os 3 `unknown → ReactNode` (`App.tsx:1205`, `DetailedTable.tsx:427`, `DetailedTableApp.tsx:653`). Meta: `npx tsc --noEmit` limpo.
- [ ] Considerar rodar `tsc --noEmit` no `deploy-pages.yml` antes do build — hoje um erro de tipo passa direto para produção.
- [ ] Remover `evasao/table.html` e `evasao/table.tsx` — **não estão no build** (`vite.config.ts` declara só 4 entradas), é código morto. `table.html:24,30` ainda carrega o GA `G-NZ84J0PJBF` e `:41` o `/index.css` inexistente — a remoção do arquivo resolve os dois.
- [x] ~~Reavaliar `base: '/evasao/dist/'`~~ — **resolvido na Fase 1.5**.
- [ ] Varredura final: `grep -ri "sef\|minas\|masp\|doe-mg\|tffc\|técnico" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist .` deve voltar vazio (fora de arquivos de legado explicitamente arquivados).

**Concluída quando:** `npm run build` OK e a varredura final está limpa.

---

## [ ] Fase 7 — Concursos e bancas *(nova, adiada por decisão de 14/08/2026)*

**Objetivo:** o concurso de **destino** — para onde a pessoa foi, e quem ainda está na CGU mas já
está aprovado ou inscrito em outro concurso ("quem está estudando para sair").

Fase **independente** e posterior: nada na Fase 2 (v2) ou na Fase 3 depende dela, e ela não reabre
nenhuma decisão daquelas fases — só acrescenta colunas e telas.

> **Encolheu em 14/08/2026.** A lista de aprovados do CGU-2021, a `AREA` e o cruzamento
> aprovado × posse **saíram desta fase e entraram na Fase 2** (**D17**): estão todos no
> `Edital CGU nº 5` publicado no DOU, a uma requisição de distância, e não precisavam de crawler de
> banca nenhum. O que sobrou aqui é só o lado do **destino**.

- [ ] **Crawlers de banca (FGV/Cespe/FCC) e `rankingdosconcursos.com.br`** — AFFCs inscritos ou
      aprovados em outros concursos. É o tema dos antigos `outros_concursos.csv` /
      `aprovacoes_outros_concursos.csv`, que a Fase 2 (v2) removeu; se voltar, volta com **fonte e
      selo de verificação** (**D14**), não como planilha preenchida à mão.
- [ ] **Aprovados do CGU-2021 que nunca tomaram posse** — 38 pessoas (488 aprovados − 450
      empossados). Devolveria `CADASTRO DE RESERVA` e `DESISTENTE` ao vocabulário de `SITUACAO`.
      Decidir se viram linha do painel: eles nunca foram da CGU, e o denominador do concurso
      (92,2% de aproveitamento) já sai do `concurso_2021.csv` sem precisar disso.
- [ ] **Concurso CGU 2026** — quando o edital sair, vira mais um valor na coluna `CONCURSO`
      (**D9**) e uma entrada em `CONCURSOS` no `constants.ts`. A `AREA` e a classificação saem do
      mesmo `concurso.py` (**D17**), só apontando para o ato novo. Nenhuma coluna nova, nenhum
      arquivo novo, nenhum código novo.

> ⚠️ Esta fase publica **previsão e intenção** ("fulano foi aprovado em X, pode sair"), não fato
> consumado. Diferente das Fases 2-3, que só afirmam o que já aconteceu. A **D14** vale em dobro
> aqui: nada sem fonte registrada.
