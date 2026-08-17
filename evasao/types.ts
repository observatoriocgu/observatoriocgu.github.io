/**
 * Tipos do observatório.
 *
 * Até a Fase 2 este arquivo existia mas nenhum componente o usava — tudo era
 * `any`. Da Fase 3 em diante `RegistroAuditor` é o contrato do `dados.csv` e a
 * interface o usa de fato.
 */

/**
 * Uma linha do `evasao/data/painel.csv`: uma pessoa que passou pela CGU como
 * AFFC entre jun/2022 e a última competência publicada.
 *
 * O `painel.csv` é o `dados.csv` já mesclado com as saídas que só o DOU conhece
 * (D22) e com os destinos do ranking (D24) — quem o gera é
 * `scripts/gerar_publicacao.py`, na hora de publicar o site (D29). Todas as
 * colunas do `dados.csv` estão aqui, mais `SAIDA_NO_SIAPE`.
 *
 * Todo campo é string porque vem do parser de CSV; campo ausente é `''`, nunca
 * `null`. Datas em `DD/MM/AAAA` quando vêm do SIAPE (`DATA_POSSE`) e em
 * `AAAA-MM-DD` quando vêm do DOU (`DATA_PUBLICACAO_SAIDA`, `DATA_DESTINO`) —
 * o crawler grava o que o ato traz, sem reformatar.
 *
 * Regras de preenchimento (D11-D14):
 * - `CONCURSO = 'VETERANO'` → `INSCRICAO`, `POSICAO_CONCURSO`, `NOTA`,
 *   `MODALIDADE` e `UF_VAGA` sempre vazios: o edital só cobre o CGU-2021.
 * - `AREA` vazia significa desconhecida, não "sem área". Vale para todo
 *   veterano e para quem do CGU-2021 não casou por nome com o edital.
 * - Quem está na CGU (`MES_SAIDA` vazio) tem todo o bloco de saída vazio.
 * - Todo campo enriquecido carrega o `FONTE_*` correspondente (D14). NÃO existe
 *   mais coluna `VERIFICADO` (D20): a tela mostra de onde veio o dado, e não
 *   uma avaliação do observatório sobre o próprio dado.
 */
export interface RegistroAuditor {
  /** Chave de identidade — e a única (D12). Nome nunca é chave: homônimos existem. */
  ID_SERVIDOR_PORTAL: string;
  NOME: string;
  /** SIAPE mascarado pelo Portal em 7 posições, ex.: `166****`. */
  MATRICULA: string;

  /** Concurso de entrada: `CGU-2021` ou `VETERANO`. Derivado da 1ª aparição na série. */
  CONCURSO: string;
  /** Especialidade do edital (D17). Vazia = desconhecida. */
  AREA: string;
  /** Competência `AAAAMM` da primeira aparição no SIAPE. */
  MES_ENTRADA: string;
  /** Ingresso no órgão, como o SIAPE informa. `DD/MM/AAAA`. */
  DATA_POSSE: string;

  /** Bloco do edital CGU nº 5/2022 (D17). Vazio para veteranos. */
  INSCRICAO: string;
  POSICAO_CONCURSO: string;
  NOTA: string;
  /** `Ampla Concorrência` | `Negros` | `PcD`. */
  MODALIDADE: string;
  /** UF da vaga disputada no concurso — não é onde a pessoa está hoje. */
  UF_VAGA: string;

  /**
   * `EM EXERCÍCIO`, `EXONERADO`, `VACÂNCIA`, `APOSENTADO`, `FALECIDO`,
   * `DEMITIDO`, `CEDIDO`, `MUDOU DE ÓRGÃO NA CARREIRA` ou
   * `SAÍDA SEM ATO IDENTIFICADO`. Quem grava é `painel.py` (o primeiro e os
   * dois últimos) e `dou.py` (o resto).
   */
  SITUACAO: string;
  /** `Sede/DF`, `CGU-Regional/UF` ou o rótulo da sub-unidade. Contada pelo código, não pelo nome. */
  UNIDADE: string;
  /** UF da unidade de lotação. `''` quando a sub-unidade não permite deduzir. */
  UF: string;
  /** `SIM` | `NÃO`. Cedido a outro órgão, mas ainda lotado na CGU. */
  CEDIDO: string;
  ORGAO_EXERCICIO: string;
  CLASSE_CARGO: string;
  PADRAO_CARGO: string;

  /** Competência `AAAAMM` do primeiro mês de ausência. `''` para quem está na CGU. */
  MES_SAIDA: string;
  /** `SIM` quando a ausência só foi observada uma vez e o mês seguinte ainda não confirmou (D13). */
  SAIDA_PROVISORIA: string;
  /** Ver `MOTIVOS_SAIDA` em `constants.ts`. `''` = nenhum ato identificado. */
  MOTIVO_SAIDA: string;
  /** `SIAPE` | `DOU` | `MANUAL`. Selo de procedência do motivo (D14). */
  FONTE_MOTIVO: string;
  DATA_PUBLICACAO_SAIDA: string;
  ATO_SAIDA_TITULO: string;
  ATO_SAIDA_URL: string;
  /** Nome do HTML arquivado em `data/dou/atos_saida/`. */
  ATO_SAIDA_ARQUIVO: string;

  /** Para onde a pessoa foi. `''` = desconhecido — nunca chutar (D14). */
  ORGAO_DESTINO: string;
  DATA_DESTINO: string;
  /** `SIAPE` | `DOU` | `BUSCA` | `MANUAL`. Selo de procedência do destino (D14). */
  FONTE_DESTINO: string;
  URL_DESTINO: string;
  /**
   * Nome do HTML arquivado em `data/dou/atos_destino/` — o ato de nomeação
   * publicado pelo órgão de chegada (D30). Vazio quando o destino não veio do
   * DOU, ou quando o ato ainda não foi arquivado.
   */
  ATO_DESTINO_ARQUIVO?: string;
  OBSERVACAO: string;

  /**
   * `NÃO` quando a saída veio só do ato do DOU e o cadastro do SIAPE ainda não
   * mostrou a ausência (D22).
   *
   * É a única coluna que existe no `painel.csv` e não no `dados.csv`: quem a
   * escreve é `scripts/publicacao.py`, ao sobrepor o `dou.json` ao CSV do
   * SIAPE (D29). Vazio significa "o SIAPE confirmou" — porque no `dados.csv`
   * toda saída nasce do diff mensal (D13).
   */
  SAIDA_NO_SIAPE?: string;
}

/**
 * Uma linha do `evasao/data/serie_mensal.csv`: o retrato de uma competência.
 *
 * `ENTRADAS` e `SAIDAS` são `''` na primeira competência, e não `0`: as 1.559
 * pessoas de jun/2022 não "entraram" — é onde a observação começa.
 */
export interface LinhaSerieMensal {
  MES: string;
  EFETIVO: string;
  ENTRADAS: string;
  SAIDAS: string;
  CEDIDOS: string;
}

/** A mesma linha depois de convertida para número, que é como os gráficos usam. */
export interface PontoSerieMensal {
  mes: string;
  efetivo: number;
  entradas: number | null;
  saidas: number | null;
  cedidos: number;
}

/**
 * Um concurso monitorado, ou o pseudo-concurso `VETERANO` (D9).
 *
 * As áreas variam de concurso para concurso — por isso a lista vive aqui, e não
 * num enum global de áreas.
 */
export interface Concurso {
  /** Identificador usado na coluna `CONCURSO` do dados.csv. Ex.: `CGU-2021`. */
  id: string;
  /** Rótulo de exibição na interface. Ex.: `CGU 2021`. */
  rotulo: string;
  /** Banca organizadora. `null` para `VETERANO`. */
  banca: string | null;
  /** Ano do edital. `null` para `VETERANO`. */
  ano: number | null;
  /** Homologação do resultado final. `null` para `VETERANO`. */
  dataHomologacao: Date | null;
  /** Áreas/especialidades daquele concurso. Vazia quando não há edital que as diga. */
  areas: readonly string[];
}

/**
 * Uma saída, do jeito que a interface exibe: pessoa, quando, por quê e com que
 * procedência. Nenhuma afirmação sobre pessoa nomeada vai à tela sem os selos de
 * fonte ao lado.
 */
export interface DetalheSaida {
  id: string;
  nome: string;
  concurso: string;
  area: string;
  unidade: string;
  uf: string;
  /** Competência `AAAAMM` da saída. */
  mesSaida: string;
  motivo: string;
  /** Selo D14: de onde veio o motivo. `''` quando não há ato. */
  fonteMotivo: string;
  /**
   * Todas as fontes que atestam que a pessoa saiu (D20). `SIAPE` quando o
   * cadastro mensal mostra a ausência — estava no mês n-1 e não está no mês n;
   * `DOU` quando existe ato publicado. As duas juntas é o caso mais comum, e
   * uma sozinha diz exatamente o que se sabe até agora.
   */
  fontesSaida: string[];
  destino: string;
  /** Selo D14: de onde veio o destino. */
  fonteDestino: string;
  /**
   * Data que atesta o destino, `AAAA-MM-DD`. É a publicação do ato de nomeação
   * no órgão de chegada quando a fonte é o DOU; vazia quando é o ranking, que
   * lista aprovações e não sabe dizer o dia da posse.
   */
  dataDestino: string;
  /**
   * Link da fonte do destino: o ato de nomeação no `in.gov.br`, ou a ficha da
   * pessoa no rankingdosconcursos. Vazio quando não há como mostrar de onde
   * saiu — é o caso do destino lido do próprio SIAPE.
   */
  urlDestino: string;
  /** Data de publicação do ato, `AAAA-MM-DD`. */
  dataPublicacao: string;
  atoTitulo: string;
  /** Link para o ato: o arquivado, se houver, senão o do in.gov.br. */
  atoUrl: string;
  /** `SIM` quando a saída ainda pode ser um buraco na série, não uma saída (D13). */
  provisoria: boolean;
  /**
   * `true` quando a saída só existe no DOU: o ato está publicado e o Portal da
   * Transparência ainda não entregou a competência que mostraria a ausência.
   * Sem pessoa no SIAPE, não há concurso, área nem unidade para exibir.
   */
  soNoDou: boolean;
}

/**
 * Saídas de AFFC da CGU publicadas no DOU, geradas por
 * `evasao/scripts/resumir_dou.py` a partir do índice único de atos
 * (`data/dou/atos_saida.csv`), que as duas varreduras do DOU alimentam — a por frase
 * e a por nome. Até 15/08/2026 este JSON vinha de um crawler só dele, e por
 * isso podia discordar do resto do painel.
 *
 * O JSON guarda datas, nunca a contagem de dias — quem conta é o navegador,
 * para o card não congelar no dia em que o crawler rodou.
 */
export interface EventoSaidaDou {
  tipo: 'vacancia' | 'aposentadoria' | 'exoneracao';
  rotulo: string;
  titulo: string;
  /** `AAAA-MM-DD`. */
  dataPublicacao: string;
  urlDou: string;
  arquivo: string | null;
}

/**
 * Uma saída que só o DOU conhece: o ato está publicado e o SIAPE ainda não
 * entregou a competência que mostraria a ausência (~2 meses de atraso do
 * Portal). O nome vem lido do texto do próprio ato.
 *
 * Elas CONTAM EM TUDO (D22, que revogou o recorte da D21): cards, gráficos,
 * curva, destinos, tabela detalhada e histórico. Não são linha nova — são
 * sobrepostas ao registro da pessoa, que já está no `dados.csv` como ativa, e
 * por isso chegam à tela com concurso, área e unidade. Na tela, a diferença
 * aparece sozinha: só carregam o selo `DOU`, nunca o do SIAPE.
 *
 * Quem faz a sobreposição é `scripts/publicacao.py` (D29), e o resultado é o
 * `painel.csv` — nenhuma página do site vê este tipo.
 */
export interface SaidaRecenteDou {
  nome: string;
  tipo: string;
  rotulo: string;
  /** `AAAA-MM-DD` da publicação. */
  dataPublicacao: string;
  titulo: string;
  urlDou: string;
  arquivo: string | null;
  /**
   * `ID_SERVIDOR_PORTAL` de quem o ato trata, quando dá para casar com o
   * `dados.csv`. Vazio quando não dá — nome não é chave (D12).
   */
  idServidor: string;
  /**
   * `true` quando o SIAPE já mostrou a pessoa sair e o que falta é só o motivo.
   * Acontece com a saída provisória, que `enriquecer_saidas.py` não consulta no
   * DOU de propósito (D13). Nesse caso o ato completa o motivo e NÃO cria saída
   * nova — a competência continua sendo a do cadastro.
   */
  jaNoSiape: boolean;
}

/**
 * O `dou.json`.
 *
 * A interface consome daqui só o CARD de "dias sem perder um Auditor"
 * (`eventos`, `dataMaisRecente`, `varreduraAte`, `ultimaCompetenciaSiape`).
 * `saidasRecentes` continua no arquivo, mas quem a lê é `scripts/publicacao.py`,
 * que a aplica ao `dados.csv` antes de o site subir (D29).
 */
export interface ResumoDoDou {
  /** `AAAA-MM-DD` até onde a varredura do DOU já cobriu. */
  varreduraAte: string;
  /** `AAAAMM` — a competência mais nova que o SIAPE entregou. */
  ultimaCompetenciaSiape: string;
  saidasRecentes: SaidaRecenteDou[];
  dataMaisRecente: string;
  tipoMaisRecente: string;
  eventos: EventoSaidaDou[];
}

/** Uma mudança do diff mensal, como `painel.gerar_alteracoes` a grava. */
export interface AlteracaoRegistro {
  id: string;
  nome: string;
  tipo: 'entrada' | 'saida';
  fromSituacao: string;
  toSituacao: string;
  orgaoDestino: string;
  unidade: string;
  concurso: string;
}

/** Um mês do log de alterações. Substituiu o bloco `commit` da versão git-arqueológica. */
export interface MesDeAlteracoes {
  /** Competência `AAAAMM`. */
  mes: string;
  /** `AAAA-MM-01` — o dia é convenção, o fato é mensal. */
  data: string;
  changeCount: number;
  changes: AlteracaoRegistro[];
}

export interface LogDeAlteracoes {
  fonte: string;
  primeiroMes: string;
  ultimoMes: string;
  totalChangeCount: number;
  history: MesDeAlteracoes[];
}
