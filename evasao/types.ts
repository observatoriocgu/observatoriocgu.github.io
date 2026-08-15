/**
 * Tipos do observatório.
 *
 * Até a Fase 2 este arquivo existia mas nenhum componente o usava — tudo era
 * `any`. Da Fase 3 em diante `RegistroAuditor` é o contrato do `dados.csv` e a
 * interface o usa de fato.
 */

/**
 * Uma linha do `evasao/data/dados.csv`: uma pessoa que passou pela CGU como
 * AFFC entre jun/2022 e a última competência publicada.
 *
 * Todo campo é string porque vem do parser de CSV; campo ausente é `''`, nunca
 * `null`. Datas em `DD/MM/AAAA` quando vêm do SIAPE (`DATA_POSSE`) e em
 * `AAAA-MM-DD` quando vêm do DOU (`DATA_SAIDA`, `DATA_PUBLICACAO_SAIDA`,
 * `DATA_DESTINO`) — o crawler grava o que o ato traz, sem reformatar.
 *
 * Regras de preenchimento (D11-D14):
 * - `CONCURSO = 'VETERANO'` → `INSCRICAO`, `POSICAO_CONCURSO`, `NOTA`,
 *   `MODALIDADE` e `UF_VAGA` sempre vazios: o edital só cobre o CGU-2021.
 * - `AREA` vazia significa desconhecida, não "sem área". Vale para todo
 *   veterano e para quem do CGU-2021 não casou por nome com o edital.
 * - Quem está na CGU (`MES_SAIDA` vazio) tem todo o bloco de saída vazio.
 * - Todo campo enriquecido carrega o `FONTE_*` correspondente, e a linha
 *   carrega `VERIFICADO` (D14).
 */
export interface RegistroAuditor {
  /** Chave de identidade — e a única (D12). Nome nunca é chave: homônimos existem. */
  ID_SERVIDOR_PORTAL: string;
  NOME: string;
  /** SIAPE mascarado pelo Portal em 7 posições, ex.: `166****`. */
  MATRICULA: string;

  /** Coorte de entrada: `CGU-2021` ou `VETERANO`. Derivada da 1ª aparição na série. */
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

  /** Ver `SITUACOES` em `constants.ts`. */
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
  DATA_SAIDA: string;
  DATA_PUBLICACAO_SAIDA: string;
  ATO_SAIDA_TITULO: string;
  ATO_SAIDA_URL: string;
  /** Nome do HTML arquivado em `data/saidas_dou/`. */
  ATO_SAIDA_ARQUIVO: string;

  /** Para onde a pessoa foi. `''` = desconhecido — nunca chutar (D14). */
  ORGAO_DESTINO: string;
  CARGO_DESTINO: string;
  DATA_DESTINO: string;
  /** `SIAPE` | `DOU` | `BUSCA` | `MANUAL`. Selo de procedência do destino (D14). */
  FONTE_DESTINO: string;
  URL_DESTINO: string;

  /** `SIM` | `NÃO` — preenchido por gente, nunca pela máquina (D14). */
  VERIFICADO: string;
  VERIFICADO_EM: string;
  OBSERVACAO: string;
}

export type ColunaRegistroAuditor = keyof RegistroAuditor;

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

/** Uma barra da tabela de destinos. */
export interface DadosDestinoEvasao {
  destino: string;
  count: number;
}

/**
 * Uma saída, do jeito que a interface exibe: pessoa, quando, por quê e com que
 * procedência. Os dois selos da D14 (`fonte` e `verificado`) são obrigatórios —
 * nenhum destino vai à tela sem eles.
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
  destino: string;
  /** Selo D14: de onde veio o destino. */
  fonteDestino: string;
  /** Selo D14: se gente conferiu a linha. */
  verificado: boolean;
  /** Data de publicação do ato, `AAAA-MM-DD`. */
  dataPublicacao: string;
  atoTitulo: string;
  /** Link para o ato: o arquivado, se houver, senão o do in.gov.br. */
  atoUrl: string;
  /** `SIM` quando a saída ainda pode ser um buraco na série, não uma saída (D13). */
  provisoria: boolean;
}

/**
 * Saídas de AFFC da CGU publicadas no DOU, geradas por
 * `evasao/scripts/gerar_card_dou.py` a partir do índice único de atos
 * (`data/atos_dou.csv`), que as duas varreduras do DOU alimentam — a por frase
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

export interface SaidasDou {
  /** `AAAA-MM-DD` até onde a varredura do DOU já cobriu. */
  varreduraAte: string;
  /** `AAAAMM` — a competência mais nova que o SIAPE entregou. */
  ultimaCompetenciaSiape: string;
  /**
   * Atos que o DOU publicou depois dessa competência. Não é pendência nem erro:
   * é a defasagem de ~2 meses do Portal da Transparência, que faz o card estar
   * sempre à frente da lista de últimas saídas. Essas saídas ainda não contam
   * na evasão — quem conta é o SIAPE (D11, D13).
   */
  atosDepoisDaUltimaCompetencia: number;
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
