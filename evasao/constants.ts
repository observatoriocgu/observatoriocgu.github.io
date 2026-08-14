import { Concurso, DadosDestinoEvasao, SituacaoAuditor } from './types';

// Custo estimado por Auditor que deixa o cargo após a posse.
// D5 do PLANO.md: fica `null` — e o card de custo fica oculto — enquanto não
// houver uma estimativa com fonte citável. Não chutar valor.
export const CUSTO_POR_AUDITOR: number | null = null;

// Este arquivo não carrega mais dados estáticos em tempo de build para evitar
// problemas quando o arquivo `dados.json` não é um JSON válido durante o empacotamento.
// A leitura dos dados passa a ser feita em runtime pelo `App.tsx` a partir de `dados.csv`.

// Data em que o observatório começa a contar eventos: homologação do concurso
// CGU 2021 (FGV). Vale para todas as coortes, veteranos inclusive — não é a data
// de início de um concurso específico.
// O horário é 10:00Z de propósito: com 00:00Z, `toLocaleDateString('pt-BR')`
// exibiria o dia anterior no fuso do Brasil (UTC-3).
export const DATA_INICIO_OBSERVACAO = new Date('2022-06-14T10:00:00Z');

// Identificador do pseudo-concurso que agrupa quem entrou antes do primeiro
// concurso monitorado (D9 do PLANO.md).
export const ID_CONCURSO_VETERANO = 'VETERANO';

/**
 * Catálogo dos concursos monitorados (D9).
 *
 * Fica em código, e não num CSV, porque é configuração que muda uma vez por
 * concurso: assim é tipada e não adiciona mais um `fetch` que possa falhar.
 * Um concurso novo = uma entrada aqui + um valor novo na coluna `CONCURSO`
 * do dados.csv. Nenhuma coluna nova, nenhum arquivo novo.
 */
export const CONCURSOS: readonly Concurso[] = [
  {
    id: 'CGU-2021',
    rotulo: 'CGU 2021',
    banca: 'FGV',
    ano: 2021,
    dataHomologacao: new Date('2022-06-14T10:00:00Z'),
    areas: [
      'Auditoria e Fiscalização',
      'TI',
      'Contabilidade Pública e Finanças',
      'Correição e Combate à Corrupção',
    ],
  },
  {
    id: 'CGU-2026',
    rotulo: 'CGU 2026',
    banca: null,
    ano: 2026,
    dataHomologacao: null,
    // EXEMPLO: o edital de 2026 ainda não foi publicado, então banca, data e
    // áreas são desconhecidas. Preencher quando sair — não inventar.
    areas: ['ÁREA A DEFINIR (EXEMPLO)'],
    provisorio: true,
  },
  {
    id: ID_CONCURSO_VETERANO,
    rotulo: 'Veteranos',
    banca: null,
    ano: null,
    dataHomologacao: null,
    // Veteranos entraram por concursos anteriores, não monitorados individualmente.
    // As áreas do CGU-2021 servem de vocabulário provisório; `AREA` vazia é válida
    // e significa "desconhecida".
    areas: [
      'Auditoria e Fiscalização',
      'TI',
      'Contabilidade Pública e Finanças',
      'Correição e Combate à Corrupção',
    ],
  },
];

/** Busca rápida por id — ex.: `CONCURSO_POR_ID.get('CGU-2021')`. */
export const CONCURSO_POR_ID: ReadonlyMap<string, Concurso> = new Map(
  CONCURSOS.map((concurso) => [concurso.id, concurso])
);

/** Concursos de verdade, sem o pseudo-concurso `VETERANO`. */
export const CONCURSOS_REAIS: readonly Concurso[] = CONCURSOS.filter(
  (concurso) => concurso.id !== ID_CONCURSO_VETERANO
);

/**
 * Áreas oferecidas por um concurso. Sem argumento, devolve a união das áreas de
 * todos os concursos — que é o vocabulário a usar quando o filtro está em "Todos".
 */
export const areasDoConcurso = (idConcurso?: string): readonly string[] => {
  if (idConcurso) return CONCURSO_POR_ID.get(idConcurso)?.areas ?? [];
  return Array.from(new Set(CONCURSOS.flatMap((concurso) => concurso.areas))).sort();
};

/**
 * Situações esperadas na coluna `SITUACAO`.
 *
 * A Fase 3 ainda precisa decidir o que fazer com os casos herdados de MG que
 * aparecem no CSV legado: `AFASTAMENTO PRELIMINAR À APOSENTADORIA`,
 * `POSSE JUDICIAL` e `INAPTO ADMISSIONAL`.
 */
export const SITUACOES: readonly SituacaoAuditor[] = [
  'EM EXERCÍCIO',
  'EXONERADO',
  'DESISTENTE',
  'APOSENTADO',
  'CADASTRO DE RESERVA',
];

/** Situações que significam que o Auditor não está mais na ativa da CGU. */
export const SITUACOES_DE_SAIDA: readonly SituacaoAuditor[] = [
  'EXONERADO',
  'DESISTENTE',
  'APOSENTADO',
];

// Tipagem auxiliar exportada para quem quiser reusar a forma de DadosDestinoEvasao.
export type { DadosDestinoEvasao };
