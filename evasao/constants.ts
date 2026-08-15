import { Concurso, DadosDestinoEvasao } from './types';

// Custo estimado por Auditor que deixa o cargo após a posse.
// D5 do PLANO.md: fica `null` — e o card de custo fica oculto — enquanto não
// houver uma estimativa com fonte citável. Não chutar valor.
export const CUSTO_POR_AUDITOR: number | null = null;

// Data em que o observatório começa a contar: homologação do concurso CGU 2021
// (FGV), que é também a competência do primeiro snapshot do SIAPE (202206).
// O horário é 10:00Z de propósito: com 00:00Z, `toLocaleDateString('pt-BR')`
// exibiria o dia anterior no fuso do Brasil (UTC-3).
export const DATA_INICIO_OBSERVACAO = new Date('2022-06-14T10:00:00Z');

/** Primeira competência da série. Tudo que existe aqui já existia antes do observatório. */
export const MES_INICIO_OBSERVACAO = '202206';

/**
 * Onde o gráfico de saídas mês a mês começa.
 *
 * O concurso CGU-2021 tomou posse em jul/2022, então ago/2022 é a primeira
 * competência em que alguém dela poderia aparecer ausente. Antes disso o
 * gráfico só teria os veteranos, e a comparação entre os dois concursos — que é
 * o ponto — nasceria torta. Custa exatamente uma saída, a de jul/2022.
 */
export const MES_INICIO_GRAFICO_SAIDAS = '202208';

// Identificador do pseudo-concurso que agrupa quem já estava na CGU no primeiro
// snapshot (D9). Não é um concurso: é "entrou antes de a gente olhar".
export const ID_CONCURSO_VETERANO = 'VETERANO';
export const ID_CONCURSO_2021 = 'CGU-2021';

/**
 * Catálogo dos concursos monitorados (D9).
 *
 * Fica em código, e não num CSV, porque é configuração que muda uma vez por
 * concurso: assim é tipada e não adiciona mais um `fetch` que possa falhar.
 *
 * As áreas do `CGU-2021` são as 4 do Edital CGU nº 5 de 13/06/2022 (D17),
 * conferidas linha a linha contra `data/concurso_2021.csv`: dos 488 aprovados
 * AFFC, 250 em Auditoria e Fiscalização, 94 em Correição e Combate à Corrupção,
 * 83 em Contabilidade Pública e Finanças e 61 em TI.
 */
export const CONCURSOS: readonly Concurso[] = [
  {
    id: ID_CONCURSO_2021,
    rotulo: 'CGU 2021',
    banca: 'FGV',
    ano: 2021,
    dataHomologacao: new Date('2022-06-14T10:00:00Z'),
    areas: [
      'Auditoria e Fiscalização',
      'Correição e Combate à Corrupção',
      'Contabilidade Pública e Finanças',
      'TI',
    ],
  },
  {
    id: ID_CONCURSO_VETERANO,
    rotulo: 'Veteranos',
    banca: null,
    ano: null,
    dataHomologacao: null,
    // Veteranos entraram por concursos anteriores, que o observatório não
    // monitora. Não existe edital de onde tirar a área deles: a lista fica
    // vazia de propósito, e `AREA` vazia no dados.csv quer dizer "desconhecida".
    areas: [],
  },
];

/** Busca rápida por id — ex.: `CONCURSO_POR_ID.get('CGU-2021')`. */
export const CONCURSO_POR_ID: ReadonlyMap<string, Concurso> = new Map(
  CONCURSOS.map((concurso) => [concurso.id, concurso])
);

/** Rótulo de exibição de um concurso; devolve o próprio id se for desconhecido. */
export const rotuloDoConcurso = (id: string): string => CONCURSO_POR_ID.get(id)?.rotulo ?? id;

/** Concursos de verdade, sem o pseudo-concurso `VETERANO`. */
export const CONCURSOS_REAIS: readonly Concurso[] = CONCURSOS.filter(
  (concurso) => concurso.id !== ID_CONCURSO_VETERANO
);

/**
 * Áreas oferecidas por um concurso. Sem argumento, devolve a união das áreas de
 * todos os concursos — que é o vocabulário a usar quando o filtro está em "Todas".
 */
export const areasDoConcurso = (idConcurso?: string): readonly string[] => {
  if (idConcurso) return CONCURSO_POR_ID.get(idConcurso)?.areas ?? [];
  return Array.from(new Set(CONCURSOS.flatMap((concurso) => concurso.areas)));
};

/**
 * Os dois rótulos de quem não tem especialidade — e eles não querem dizer a
 * mesma coisa.
 *
 * `AREA_VETERANO` é "não se aplica": quem já estava na CGU em jun/2022 não fez o
 * concurso de 2021, e a especialidade só existe no edital dele. Não há dado a
 * buscar, e não haverá.
 *
 * `AREA_DESCONHECIDA` é lacuna de verdade: é gente do concurso de 2021 cujo nome
 * não casou com nenhum documento do concurso. Aí ainda há o que procurar.
 *
 * Juntar os dois num rótulo só faria 104 saídas de veterano parecerem buraco de
 * dado, e daria a 4 Auditores do concurso um rótulo que não é o deles.
 */
export const AREA_VETERANO = 'Veterano';
export const AREA_DESCONHECIDA = 'Sem área identificada';

/** As duas que não são especialidade. Nascem desmarcadas no filtro. */
export const AREAS_SEM_ESPECIALIDADE: readonly string[] = [AREA_VETERANO, AREA_DESCONHECIDA];

/**
 * Vocabulário da coluna `SITUACAO`.
 *
 * `EM EXERCÍCIO` e as duas últimas vêm do próprio SIAPE (`painel.py`); as cinco
 * do meio vêm da classificação do ato no DOU (`dou.py`). Nada aqui é herdado de
 * MG: `DESISTENTE`, `CADASTRO DE RESERVA`, `INAPTO ADMISSIONAL` e
 * `AFASTAMENTO PRELIMINAR À APOSENTADORIA` não existem no universo da D11 —
 * o observatório só vê quem já estava lotado na CGU.
 */
export const SITUACAO_EM_EXERCICIO = 'EM EXERCÍCIO';
export const SITUACAO_SEM_ATO = 'SAÍDA SEM ATO IDENTIFICADO';
export const SITUACAO_MUDOU_ORGAO = 'MUDOU DE ÓRGÃO NA CARREIRA';

export const SITUACOES: readonly string[] = [
  SITUACAO_EM_EXERCICIO,
  'EXONERADO',
  'VACÂNCIA',
  'APOSENTADO',
  'FALECIDO',
  'DEMITIDO',
  SITUACAO_MUDOU_ORGAO,
  SITUACAO_SEM_ATO,
];

/** Situações que significam que a pessoa não está mais na CGU. */
export const SITUACOES_DE_SAIDA: readonly string[] = SITUACOES.filter(
  (situacao) => situacao !== SITUACAO_EM_EXERCICIO
);

/**
 * Motivos de saída, na ordem em que aparecem nos gráficos.
 *
 * O rótulo é exatamente o que `dou.py` grava em `MOTIVO_SAIDA` — mudar aqui
 * sem mudar lá quebra o agrupamento em silêncio. `MOTIVO_SEM_ATO` é o rótulo
 * de exibição para `MOTIVO_SAIDA` vazio: o SIAPE viu a pessoa sumir, o DOU não
 * disse por quê. É informação legítima, não erro.
 */
export const MOTIVO_SEM_ATO = 'Sem ato identificado';

export const MOTIVO_EXONERACAO = 'Exoneração';
export const MOTIVO_VACANCIA = 'Vacância (posse em outro cargo)';
export const MOTIVO_APOSENTADORIA = 'Aposentadoria';
export const MOTIVO_FALECIMENTO = 'Falecimento';

/**
 * O motivo que o dado grava e a tela não nomeia (D18).
 *
 * `MOTIVO_DEMISSAO` é o valor real, escrito no `dados.csv` por `dou.py`.
 * `MOTIVO_OUTRO` é o que o leitor vê no lugar dele em toda página que não seja
 * a tabela detalhada — a pessoa continua contada em tudo, o balde continua no
 * lugar, e o que não se publica é a palavra.
 *
 * Quem faz a troca é `motivoDe`, em `lib/painel.ts`, e só ela. Não repetir esta
 * regra em componente nenhum: o rótulo neutro tem de ser o CAMINHO PADRÃO, e
 * revelar o motivo tem de exigir um pedido explícito (`motivoDetalhado`). O
 * contrário — mascarar caso a caso — vaza no primeiro componente novo que
 * alguém escrever sem saber que a regra existe.
 */
export const MOTIVO_DEMISSAO = 'Demissão';
export const MOTIVO_OUTRO = 'Outro motivo';

/** Motivos como a tela os mostra, na ordem em que aparecem nos gráficos. */
export const MOTIVOS_SAIDA: readonly string[] = [
  MOTIVO_EXONERACAO,
  MOTIVO_VACANCIA,
  MOTIVO_APOSENTADORIA,
  MOTIVO_FALECIMENTO,
  MOTIVO_OUTRO,
  SITUACAO_MUDOU_ORGAO,
  MOTIVO_SEM_ATO,
];

/**
 * A mesma lista com o motivo real no lugar do rótulo neutro.
 *
 * Só `dados_detalhados.html` usa. É a lista que casa com o que está gravado no
 * `dados.csv`, e por isso é a única que serve para montar um filtro sobre o
 * valor cru da coluna.
 */
export const MOTIVOS_SAIDA_DETALHADOS: readonly string[] = MOTIVOS_SAIDA.map((motivo) =>
  motivo === MOTIVO_OUTRO ? MOTIVO_DEMISSAO : motivo
);

/**
 * Os dois motivos que o painel mostra por padrão.
 *
 * São as saídas em que o Auditor escolheu ir embora para outro cargo público —
 * que é o fenômeno que o observatório existe para medir. Aposentadoria,
 * falecimento e demissão também esvaziam a CGU, mas não são evasão no sentido
 * que interessa aqui: continuam a um clique de distância, na caixinha.
 */
export const MOTIVOS_PADRAO: readonly string[] = [MOTIVO_EXONERACAO, MOTIVO_VACANCIA];

/** Cor de cada motivo. Uma só definição, para gráfico e legenda não divergirem. */
export const COR_POR_MOTIVO: Readonly<Record<string, string>> = {
  [MOTIVO_EXONERACAO]: '#dc2626',
  [MOTIVO_VACANCIA]: '#f97316',
  [MOTIVO_APOSENTADORIA]: '#d4af37',
  [MOTIVO_FALECIMENTO]: '#94a3b8',
  [MOTIVO_OUTRO]: '#a21caf',
  [SITUACAO_MUDOU_ORGAO]: '#2563eb',
  [MOTIVO_SEM_ATO]: '#4b5563',
};

/** Cor de cada concurso, usada nos gráficos que separam CGU-2021 de veteranos. */
export const COR_POR_CONCURSO: Readonly<Record<string, string>> = {
  [ID_CONCURSO_2021]: '#dc2626',
  [ID_CONCURSO_VETERANO]: '#d4af37',
};

/**
 * Selos de procedência (D14). A máquina diz de onde tirou o dado; ela não se
 * autoavalia, e não existe nota de confiança automática.
 */
export const ROTULO_POR_FONTE: Readonly<Record<string, string>> = {
  SIAPE: 'SIAPE',
  DOU: 'DOU',
  RANKING: 'Edital',
  BUSCA: 'Busca',
  MANUAL: 'Curadoria',
};

/** Descrição longa de cada fonte, para o `title` do selo. */
export const DESCRICAO_POR_FONTE: Readonly<Record<string, string>> = {
  SIAPE:
    'Cadastro de Servidores Civis do Portal da Transparência: a pessoa consta ' +
    'do quadro num mês e não consta no seguinte',
  DOU: 'Ato publicado no Diário Oficial da União, com cópia arquivada aqui',
  RANKING: 'Edital CGU nº 5, de 13/06/2022, publicado no DOU',
  BUSCA: 'Busca por nome no DOU',
  MANUAL: 'Correção humana registrada em data/curadoria.csv',
};

// Tipagem auxiliar exportada para quem quiser reusar a forma de DadosDestinoEvasao.
export type { DadosDestinoEvasao };
