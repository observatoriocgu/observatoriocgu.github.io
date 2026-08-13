# Plano de adaptação — Observatório SEF-MG → Observatório CGU

Cada fase é independente e termina com o site funcionando (`npm run build` OK em `evasao/`).
Regra do CLAUDE.md: **uma fase por vez**.

## Pré-requisitos (uma vez só)

- [x] `cd evasao && npm install` — `node_modules/` não existe no clone. Node 24.18 / npm 11.16 já instalados.
- [x] Rodar `npm run build` **antes** de qualquer alteração, para registrar o baseline verde. (OK em 13/08/2026, vite 6.4.3, 60 módulos.)

**Sobre o `dist/`:** `vite.config.ts` usa `base: '/evasao/dist/'` e a pasta `evasao/dist/` está commitada — é ela que o GitHub Pages serve. Toda fase que mexer em `evasao/` precisa terminar com rebuild **e commit do `dist/` regenerado**. Nunca editar `dist/` à mão.

---

## Decisões tomadas (confirmadas em 13/08/2026)

Todas as decisões abaixo estão **fechadas**. As fases podem ser executadas sem consulta adicional.

| # | Decisão | Afeta | Resolução |
|---|---|---|---|
| D1 | E-mail de contato do observatório | Fase 1 | `observatoriocgu@gmail.com` — **placeholder**; exige verificação no FormSubmit antes do formulário funcionar |
| D2 | ID do Google Analytics | Fase 1 | **remover** o `G-NZ84J0PJBF` das 4 HTMLs e não colocar substituto |
| D3 | Logo/favicon | Fase 1 | manter os arquivos de imagem atuais; apenas renomear/ajustar as referências |
| D4 | `CARGO` separado de `AREA` | Fase 2 | **sim** — nova coluna `CARGO` (`AFFC` \| `TFFC`); `AREA` fica só com a especialidade |
| D5 | Valor do custo por servidor | Fase 3 | `CUSTO_POR_SERVIDOR = null` → card de custo **oculto** enquanto não houver valor com fonte |
| D6 | Destino da pasta `ranking/` | Fase 5 | **remover** a pasta inteira (opção A) |

**Pendências operacionais que essas decisões geram** (não bloqueiam nenhuma fase):

- D1 — criar/verificar a caixa `observatoriocgu@gmail.com` no FormSubmit; até lá o formulário de colaboração não entrega mensagens.
- D5 — levantar uma estimativa de custo com fonte citável para reativar o card em algum momento futuro.

---

## [x] Fase 1 — Rebranding superficial ✅ concluída em 13/08/2026

**Objetivo:** zero menção a SEF-MG/DOE/Minas Gerais na interface. Nenhum arquivo de dados tocado.

**Terminologia adotada** (vale para as próximas fases):

- subtítulo padrão das páginas: "Auditores e Técnicos Federais de Finanças e Controle — CGU"
- termo genérico para pessoa: **servidor / servidores** (cobre AFFC e TFFC)
- órgão: **CGU** · diário: **Diário Oficial da União (DOU)**

### Textos e identidade

- [x] `evasao/App.tsx` — todas as strings visíveis de `1310-1504`:
  - `:1322` — `<h1>OBSERVATÓRIO DAS EVASÕES</h1>` mantido (título é neutro; cor `#E21111` hardcoded permanece)
  - `:1325` — subtítulo → "Auditores e Técnicos Federais de Finanças e Controle — CGU"
  - `:1332` — "sem perder um Auditor Fiscal" → "sem perder um servidor"
  - `:1346, :1354, :1362, :1366` — cards "Auditores…" → "Servidores…" / "Cada servidor…"
  - `:1453-1454` — "desistindo de tomar posse na CGU" / "A CGU perdeu…"
  - `:1465-1468` — seção "Servidores Aguardando Nomeação"
  - `:1490` — "Edital 1/2022" → "concurso CGU 2021 (FGV), homologado em 14/06/2022"
  - `:1497` — nota metodológica agora cita o DOU
  - `:1504` — rodapé → "Diário Oficial da União (DOU)"
- [x] `evasao/components/AnnouncementModal.tsx:44,48` — texto rebrandeado. O modal segue **desativado** (`ANNOUNCEMENT_ENABLED = false`), então não é decisão urgente; remover só se ninguém for reativá-lo.
- [x] `evasao/components/CollaborationForm.tsx` — e-mail → `observatoriocgu@gmail.com` (**D1**), `_subject` → `[Observatório CGU]`, texto "evasão na SEF" → "evasão na CGU".
- [x] `evasao/components/DetailedTableApp.tsx` (:583 cabeçalho, :829 rodapé), `DetailedTable.tsx` (:210, :438), `relatorio_impressao.tsx` (:174-184 títulos das listas, :199 subtítulo).
  - `HistoryPage.tsx`, `EvasionTable.tsx` e `AprovadosOutrosConcursosTable.tsx` **não tinham texto visível de MG** — as ocorrências contadas eram só identificadores (`AuditorDetail`, `AuditorRow`, chaves `MASP`/`HGV-0`). Renomeação fica para a Fase 3.
- [x] `evasao/index.html` + `dados_detalhados.html` / `historico_alteracoes.html` / `relatorio_impressao.html` — `<title>` com sufixo "CGU" e `<meta description>` nova nas 4 (as 3 últimas não tinham description).
- [x] Google Analytics `G-NZ84J0PJBF` (**D2**) — removido das 4 HTMLs do build, sem substituto.
  - ⚠️ Sobrou em `evasao/table.html:24,30` — arquivo **fora do build**, marcado para exclusão na Fase 6.
- [x] Logos/favicons (**D3**) — arte mantida, nenhuma referência precisou mudar.

### Correção dos links quebrados

- [x] `<link rel="stylesheet" href="/index.css">` — removido de `index.html`, `dados_detalhados.html` e `historico_alteracoes.html` (estavam nas 3, não só na `index.html`). O aviso `"/index.css doesn't exist at build time"` sumiu do build.
- [x] `App.tsx:1444` e `:1481` — links absolutos → `./historico_alteracoes.html` e `./dados_detalhados.html`.
- [x] Bônus, mesmo defeito: `DetailedTableApp.tsx:574` (`/evasao/dist/index.html`) e `HistoryPage.tsx:398` (`/evasao/dist/`) → `./index.html`.
  - Os `fetch` de CSV (`App.tsx:331`, `DetailedTableApp.tsx:188`, `HistoryPage.tsx:281`…) **continuam absolutos de propósito** — têm lista de fallback e mexer neles é lógica de dados (Fase 4).

### Fora de `evasao/`

- [x] `README.md` — passa a descrever o Observatório CGU. (Conteúdo completo fica na Fase 6.)
- [x] `.gitignore` na raiz — criado (node_modules, logs, `.env`, caches Python, artefatos de editor/SO, `repomix-output.xml`). **Não** ignora `evasao/dist/`, que é versionado de propósito.
- [ ] ~~`ranking/index.html:1264`, `composicao.html:589`, `composicao.template.html:589`~~ — pulado: **D6** decidiu remover `ranking/` inteira na Fase 5.

**Não fazer nesta fase:** nada em `evasao/data/`, `types.ts`, `constants.ts` ou lógica de negócio.

**Adiado de propósito** (não é menção a MG, é dependência de constante):

- As strings "Janeiro/2024" / "Desde Janeiro de 2024" (`App.tsx:1350, 1454, 1490`) espelham `DATA_INICIO_OBSERVACAO`. Mudá-las agora deixaria a UI mentindo sobre a constante — vão junto com a troca para `2022-06-14` (ver Fase 2/3).

**Concluída quando:** ~~`npm run build` OK, `dist/` commitado, nenhum "SEF", "MG" ou "Minas Gerais" visível na UI, `/index.css` fora do HTML.~~ ✅ build OK (`vite 6.4.3`, 60 módulos, sem avisos), `dist/` regenerado, varredura de `SEF|Minas Gerais|Receita Estadual|DOE-MG|G-NZ84J0PJBF|index.css` limpa em todo `evasao/` fora de `table.html` (morto) e dos JSONs de histórico (Fase 4). **Falta commitar o `dist/` regenerado.**

---

## [ ] Fase 2 — Novo esquema de dados

**Objetivo:** definir o contrato de dados CGU e um `dados.csv` de EXEMPLO para validar a UI. A UI ainda **não** é adaptada (isso é Fase 3) — esta fase pode deixar o dashboard com números zerados/errados, desde que o build passe.

### Esquema proposto para `dados.csv` (separador `;`)

| Coluna atual (MG) | Coluna nova (CGU) | Observação |
|---|---|---|
| `MASP` | `SIAPE` | matrícula federal |
| `INSCRICAO` | `INSCRICAO` | mantém |
| `POSICAO_CONCURSO` | `POSICAO_CONCURSO` | mantém |
| — | **`CARGO`** | **novo** — `AFFC` \| `TFFC` (**D4**) |
| `AREA` | `AREA` | `Auditoria e Fiscalização`, `TI`, `Contabilidade Pública e Finanças`, `Correição e Combate à Corrupção`; TFFC sem área |
| `NOME`, `PCD`, `SITUACAO`, `ORGAO_DESTINO` | iguais | mantém |
| `DATA_*` (7 colunas) | iguais | mantém a semântica; publicação passa a ser no **DOU** |
| `OBSERVACAO` | `OBSERVACAO` | mantém |
| `UNIDADE` | `UNIDADE` | passa a ser unidade CGU (CGU-Regional/UF ou unidade da sede) |
| `VAGA` (`FA nnnn`) | **remover** | específico de MG |
| `CDCOMI`, `DESCCOMI` | **remover** | específico de MG |
| `DATA_INICIO` | `DATA_INICIO` | mantém (entrada em exercício) |

> Verificado no código: `VAGA`, `CDCOMI` e `DESCCOMI` **não são lidos por nenhum componente** — podem sair sem quebrar nada. `UNIDADE` é lido em 5 pontos do `App.tsx` (`682, 746, 783, 800, 853`) e alimenta o gráfico "por Unidade".

### Tarefas

- [ ] `evasao/types.ts` — hoje tem só 4 linhas (`DadosDestinoEvasao`). Tipar o registro do CSV de verdade (`RegistroServidor`), em vez do `any[]` usado hoje no `App.tsx`.
- [ ] `evasao/constants.ts`:
  - `DATA_INICIO_OBSERVACAO`: `2024-01-01` → **`2022-06-14`** (homologação do concurso CGU 2021)
  - `COST_PER_AUDITOR = 30000` → renomear para `CUSTO_POR_SERVIDOR` e deixar **a definir** (**D5**)
  - adicionar constantes de domínio: `CARGOS`, `AREAS`, `SITUACOES`
- [ ] Criar `evasao/data/dados.csv` novo com o cabeçalho acima + **~10 linhas fictícias marcadas como EXEMPLO** (coluna `OBSERVACAO` = `EXEMPLO — dado fictício`), cobrindo: `EM EXERCÍCIO`, `EXONERADO`, `DESISTENTE`, `APOSENTADO`, `CADASTRO DE RESERVA`, ambos os cargos e as 4 áreas.
- [ ] Preservar o `dados.csv` original em `evasao/data/_legado_sefmg/` ou removê-lo — decidir e registrar.
- [ ] `aprovacoes_outros_concursos.csv` e `outros_concursos.csv` — cabeçalho é genérico (concurso/cargo/vagas), **não precisa mudar**; só esvaziar/substituir por EXEMPLO.

**Concluída quando:** `npm run build` OK, o site carrega o CSV de exemplo sem erro no console (mesmo que os contadores fiquem incoerentes).

---

## [ ] Fase 3 — Adaptar `App.tsx` e componentes ao novo esquema

**Objetivo:** dashboard coerente com os dados de exemplo da Fase 2.

- [ ] **Situações** (`App.tsx:1145-1148`) — revisar os literais `EXONERADO`, `DESISTENTE`, `APOSENTADO`, `AFASTAMENTO PRELIMINAR À APOSENTADORIA`. Verificar se "afastamento preliminar à aposentadoria" existe no regime federal ou se some. `POSSE JUDICIAL` e `INAPTO ADMISSIONAL` também aparecem no CSV atual.
- [ ] **Filtro de área** (`App.tsx:1414-1425`) — hoje monta os botões a partir de `FISCALIZAÇÃO / TI / TRIBUTAÇÃO / VETERANO`. Trocar pelas 4 áreas AFFC.
- [ ] **Cargo AFFC vs TFFC** — decidir se vira um segundo filtro, uma aba, ou uma coluna a mais nas tabelas (**D4**).
- [ ] **"VETERANO"** — no modelo MG era um valor da coluna `AREA` que distinguia servidores antigos dos aprovados no concurso. Definir o equivalente CGU (provavelmente `CARGO`+ausência de `POSICAO_CONCURSO`) e ajustar os agregadores.
- [ ] **Card de custo** (`CounterCard`) — usar `CUSTO_POR_SERVIDOR`; ocultar o card enquanto o valor for `null` (**D5**).
- [ ] **Gráfico por Unidade** (`agregarPorUnidade`, `App.tsx:783-853`) — validar com as unidades CGU do CSV de exemplo.
- [ ] `DetailedTableApp.tsx` (836 linhas) e `DetailedTable.tsx` — colunas exibidas, ordenação e filtros passam a refletir `SIAPE`/`CARGO`.
- [ ] `relatorio_impressao.tsx` — mesmas colunas.
- [ ] `chave` de identificação: `App.tsx:67` usa `INSCRICAO → MASP → HGV-0 → NOME`. Trocar `MASP` por `SIAPE` e eliminar o `'HGV-0'` (resíduo sem origem no CSV). O mesmo padrão se repete em `HistoryPage.tsx:88,150,200,213,232,241` e `:433`.
- [ ] **Strings de data herdadas da Fase 1** — "Desde Janeiro de 2024" (`App.tsx:1350`), "desde Janeiro/2024" (`:1454`) e "a partir de Janeiro de 2024" (`:1490`) precisam acompanhar a troca de `DATA_INICIO_OBSERVACAO` para `2022-06-14`. Ideal: derivar da constante em vez de repetir o texto.
- [ ] **Renomear identificadores** que sobraram do modelo MG (não afetam a UI, por isso ficaram fora da Fase 1): `AuditorDetail`/`AuditorRow` (`EvasionTable.tsx`, `AprovadosOutrosConcursosTable.tsx`), `allAuditors` (`DetailedTableApp.tsx`), `mapaAuditoresEmExercicio`/`contarAuditoresEmExercicioAguardandoNomeacao` (`App.tsx`).

**Concluída quando:** `npm run build` OK e os 4 cards, o gráfico e as 3 tabelas mostram números consistentes com as ~10 linhas de exemplo.

---

## [ ] Fase 4 — Pipeline de dados

**Objetivo:** repor a esteira de atualização, agora contra fontes federais.

- [ ] `evasao/data/processador.ipynb` — hoje consome os snapshots `Auditores_YYYYMM.csv` do portal de MG (43 colunas, `masp,nome,descsitser,...`). Reescrever para o **Portal da Transparência federal** (formato de "Servidores Civis" — layout e nomes de coluna totalmente diferentes).
- [ ] `evasao/data/historico transparencia/` — 27 CSVs mensais de MG (`202312`–`202602`). Remover ou arquivar; recomeçar a série com dados da CGU.
- [ ] `evasao/data/mudancas/` — 26 diffs `.txt` derivados dos anteriores. Idem.
- [ ] `evasao/scripts/reorder_dados.py` — ajustar à nova ordem de colunas.
- [ ] `evasao/scripts/generate-alteracoes.js` (249 linhas) — lê o histórico **git** do `dados.csv` para montar o log de alterações. Verificar as referências a colunas (`MASP`) e o comportamento no primeiro commit do CSV novo.
- [ ] Regenerar `evasao/public/alteracoes.json` e `alteracoes-registros.json` — os atuais contêm 182 commits com autor `observatoriosefmg` e mensagens do projeto antigo.
- [ ] Carregar a lista de aprovados do **Resultado Final FGV de 13/06/2022** (fonte no CLAUDE.md) para popular o `dados.csv` real.

**Concluída quando:** `npm run build` OK e o `dados.csv` real (não-EXEMPLO) renderiza corretamente.

---

## [ ] Fase 5 — Destino da pasta `ranking/`

**Contexto:** 3 páginas HTML estáticas (`index.html` 3708 linhas, `composicao.html` 746, `ranking-verbas-indenizatorias.html` 378) + `dados-grafico.json` (872 KB) + 27 bandeiras estaduais. Compara remuneração de **fiscos estaduais** — sem paralelo no contexto federal da CGU. Não compartilha código com `evasao/` (só os favicons, por caminho relativo `../evasao/`).

Opções (**D6**):

- [ ] **A — Remover** (recomendado): apagar `ranking/` inteira. Nada em `evasao/` depende dela. Menor superfície de manutenção.
- [ ] **B — Adaptar**: trocar o eixo "estados" por "órgãos federais de controle" (CGU, TCU, AGU…). Exige refazer `dados-grafico.json` do zero e trocar as 27 bandeiras — esforço alto, benefício incerto.
- [ ] **C — Congelar**: manter no repo mas remover do build/links, com aviso de "conteúdo herdado do projeto original".

**Concluída quando:** decisão executada, nenhum link morto apontando para `ranking/`, e `npm run build` OK.

---

## [ ] Fase 6 — Metadados, Actions e limpeza final

- [ ] `README.md` — escrever de verdade: o que é o observatório, fonte dos dados, como rodar, como contribuir.
- [ ] `evasao/README.md` — hoje é o boilerplate do Google AI Studio (banner, link para `ai.studio`, instrução de `GEMINI_API_KEY`). Substituir.
- [ ] `evasao/metadata.json` — `name` e `description`.
- [ ] `evasao/package.json:2` — `"name": "evasão-auditores-fiscais-mg"` → `observatorio-cgu`.
- [ ] `evasao/vite.config.ts:29-31` — remove o `define` de `process.env.API_KEY` / `GEMINI_API_KEY`: **não há nenhum uso de Gemini no código**, é resto do scaffold.
- [ ] `.github/workflows/update-alteracoes.yml` — nome do workflow e mensagem de commit em português já servem; revisar caminhos se a Fase 4 mudar a estrutura.
- [ ] Remover `evasao/table.html` e `evasao/table.tsx` — **não estão no build** (`vite.config.ts` declara só 4 entradas), é código morto. `table.html:24,30` ainda carrega o GA `G-NZ84J0PJBF` e `:41` o `/index.css` inexistente — a remoção do arquivo resolve os dois.
- [ ] Reavaliar `base: '/evasao/dist/'` — publicar de `dist/` commitado é frágil. Alternativa: workflow do Actions que builda e publica no Pages, tirando `dist/` do versionamento.
- [ ] Varredura final: `grep -ri "sef\|minas\|masp\|doe-mg" --exclude-dir=.git --exclude-dir=node_modules .` deve voltar vazio (fora de arquivos de legado explicitamente arquivados).

**Concluída quando:** `npm run build` OK e a varredura final está limpa.
