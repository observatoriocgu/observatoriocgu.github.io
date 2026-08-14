export interface DadosDestinoEvasao {
  destino: string;
  count: number;
}

/**
 * Situações normalizadas de um Auditor. O campo `SITUACAO` do CSV é lido como
 * string crua — use este tipo só depois de normalizar (trim + caixa alta).
 */
export type SituacaoAuditor =
  | 'EM EXERCÍCIO'
  | 'EXONERADO'
  | 'DESISTENTE'
  | 'APOSENTADO'
  | 'CADASTRO DE RESERVA';

/**
 * Um concurso monitorado, ou o pseudo-concurso `VETERANO` (D9 do PLANO.md).
 *
 * As áreas variam de concurso para concurso — por isso a lista vive aqui, e não
 * num enum global de áreas.
 */
export interface Concurso {
  /** Identificador usado na coluna `CONCURSO` do dados.csv. Ex.: `CGU-2021`. */
  id: string;
  /** Rótulo de exibição na interface. Ex.: `CGU 2021`. */
  rotulo: string;
  /** Banca organizadora. `null` para `VETERANO` ou enquanto não se souber. */
  banca: string | null;
  /** Ano do edital. `null` para `VETERANO`. */
  ano: number | null;
  /** Homologação do resultado final. `null` para `VETERANO` ou se ainda não houve. */
  dataHomologacao: Date | null;
  /** Áreas/especialidades daquele concurso. Pode ser vazia se ainda não se souber. */
  areas: readonly string[];
  /** `true` enquanto os dados do concurso forem placeholder (edital não publicado). */
  provisorio?: boolean;
}

/**
 * Uma linha do `evasao/data/dados.csv`.
 *
 * Todos os campos são string porque vêm do parser de CSV — campo ausente é `''`,
 * nunca `null`/`undefined`. Datas seguem o formato `DD/MM/AAAA`.
 *
 * Regras de preenchimento (D9):
 * - `CONCURSO = 'VETERANO'` → `INSCRICAO` e `POSICAO_CONCURSO` sempre vazios.
 * - Quem nunca tomou posse (`DESISTENTE`, `CADASTRO DE RESERVA`) → `SIAPE`,
 *   `UNIDADE` e `DATA_INICIO` vazios.
 * - `AREA` é só a especialidade, e vale também para veteranos. Vazia = desconhecida.
 */
export interface RegistroAuditor {
  /** Matrícula federal. Vazio para quem nunca tomou posse. */
  SIAPE: string;
  /** Coorte de entrada: `CGU-2021`, `CGU-2026`, … ou `VETERANO`. */
  CONCURSO: string;
  /** Número de inscrição no concurso. Único apenas dentro de um mesmo `CONCURSO`. */
  INSCRICAO: string;
  POSICAO_CONCURSO: string;
  AREA: string;
  NOME: string;
  /** `SIM` | `NÃO` | `INDEFERIDO`. */
  PCD: string;
  /** Ver `SituacaoAuditor`. */
  SITUACAO: string;
  /** Órgão para o qual o Auditor saiu, quando houver. */
  ORGAO_DESTINO: string;
  DATA_NOMEACAO: string;
  DATA_EXONERACAO: string;
  DATA_PUBLICACAO_EXONERACAO: string;
  DATA_NOMEACAO_SEM_EFEITO: string;
  DATA_INATIVIDADE: string;
  DATA_PUBLICACAO_INATIVIDADE: string;
  OBSERVACAO: string;
  /** Unidade da CGU: `Sede/DF` ou `CGU-Regional/UF`. */
  UNIDADE: string;
  /** Entrada em exercício. */
  DATA_INICIO: string;
}

export type ColunaRegistroAuditor = keyof RegistroAuditor;
