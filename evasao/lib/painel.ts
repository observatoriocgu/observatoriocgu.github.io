/**
 * Regras de negócio do painel.
 *
 * Tudo aqui é função pura sobre `RegistroAuditor[]` — nenhuma faz rede, nenhuma
 * toca no DOM. As três páginas (dashboard, tabela detalhada, relatório) leem
 * daqui, para que "quem saiu" e "por qual motivo" tenham uma definição só.
 *
 * O equivalente em Python é `evasao/scripts/painel.py`, que produz os CSVs.
 * Este arquivo não recalcula nada que o Python já decidiu: ele agrupa.
 */

import {
  AREA_DESCONHECIDA,
  AREA_VETERANO,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVO_APOSENTADORIA,
  MOTIVO_EXONERACAO,
  MOTIVO_SEM_ATO,
  MOTIVO_VACANCIA,
  SITUACAO_EM_EXERCICIO,
} from '../constants';
import {
  DetalheSaida,
  LinhaSerieMensal,
  PontoSerieMensal,
  RegistroAuditor,
} from '../types';
import { LinhaCsv, baseDoSite } from './dados';

/** Converte as linhas cruas do CSV no tipo do painel. Sem validação: o CSV é derivado. */
export const comoRegistros = (linhas: LinhaCsv[]): RegistroAuditor[] =>
  linhas as unknown as RegistroAuditor[];

export const comoSerie = (linhas: LinhaCsv[]): PontoSerieMensal[] =>
  (linhas as unknown as LinhaSerieMensal[]).map((linha) => ({
    mes: linha.MES,
    efetivo: Number(linha.EFETIVO) || 0,
    // `''` na primeira competência não é zero: é "não há mês anterior".
    entradas: linha.ENTRADAS === '' ? null : Number(linha.ENTRADAS),
    saidas: linha.SAIDAS === '' ? null : Number(linha.SAIDAS),
    cedidos: Number(linha.CEDIDOS) || 0,
  }));

/** Saiu da CGU quem tem competência de saída (D13). Não se olha a `SITUACAO`. */
export const saiuDaCgu = (registro: RegistroAuditor): boolean => registro.MES_SAIDA !== '';

export const saidas = (registros: RegistroAuditor[]): RegistroAuditor[] =>
  registros.filter(saiuDaCgu);

export const emExercicio = (registros: RegistroAuditor[]): RegistroAuditor[] =>
  registros.filter((registro) => registro.SITUACAO === SITUACAO_EM_EXERCICIO);

/** Motivo já pronto para exibir: vazio vira o rótulo de "o DOU não disse por quê". */
export const motivoDe = (registro: RegistroAuditor): string =>
  registro.MOTIVO_SAIDA || MOTIVO_SEM_ATO;

/**
 * Área já pronta para exibir.
 *
 * Vazia não é um caso só: no veterano é "não se aplica", porque a especialidade
 * só existe no edital do concurso de 2021 e ele não o fez; em quem é da coorte
 * de 2021 é lacuna — o nome não casou com documento nenhum do concurso.
 */
export const areaDe = (registro: RegistroAuditor): string => {
  if (registro.AREA) return registro.AREA;
  return registro.CONCURSO === ID_CONCURSO_VETERANO ? AREA_VETERANO : AREA_DESCONHECIDA;
};

/**
 * Link para o ato que explica a saída.
 *
 * Prefere o HTML arquivado em `data/saidas_dou/` ao `in.gov.br`: o arquivo local
 * é o que o observatório leu, e continua respondendo se a página original sair
 * do ar. `''` quando não há ato — e aí não se exibe link nenhum.
 */
export const urlDoAto = (registro: RegistroAuditor): string => {
  if (registro.ATO_SAIDA_ARQUIVO) return `${baseDoSite()}data/saidas_dou/${registro.ATO_SAIDA_ARQUIVO}`;
  return registro.ATO_SAIDA_URL;
};

/** Uma saída no formato que a interface consome, com os dois selos da D14. */
export const detalharSaida = (registro: RegistroAuditor): DetalheSaida => ({
  id: registro.ID_SERVIDOR_PORTAL,
  nome: registro.NOME,
  concurso: registro.CONCURSO,
  area: areaDe(registro),
  unidade: registro.UNIDADE,
  uf: registro.UF,
  mesSaida: registro.MES_SAIDA,
  motivo: motivoDe(registro),
  fonteMotivo: registro.FONTE_MOTIVO,
  destino: registro.ORGAO_DESTINO,
  fonteDestino: registro.FONTE_DESTINO,
  verificado: registro.VERIFICADO === 'SIM',
  dataPublicacao: registro.DATA_PUBLICACAO_SAIDA,
  atoTitulo: registro.ATO_SAIDA_TITULO,
  atoUrl: urlDoAto(registro),
  provisoria: registro.SAIDA_PROVISORIA === 'SIM',
});

/** Ordena saídas da mais recente para a mais antiga, desempatando por nome. */
export const porSaidaMaisRecente = (a: DetalheSaida, b: DetalheSaida): number =>
  b.mesSaida.localeCompare(a.mesSaida) || a.nome.localeCompare(b.nome, 'pt-BR');

/**
 * O recorte que os três grupos de caixinhas do painel produzem.
 *
 * Lista vazia em qualquer um dos três quer dizer "nenhum", não "todos" — é o
 * que o leitor pediu ao desmarcar tudo.
 */
export interface RecorteDeSaidas {
  coortes: readonly string[];
  areas: readonly string[];
  motivos: readonly string[];
}

/** As saídas que sobrevivem ao recorte. */
export const filtrarSaidas = (
  registros: RegistroAuditor[],
  recorte: RecorteDeSaidas
): RegistroAuditor[] =>
  saidas(registros).filter(
    (registro) =>
      recorte.coortes.includes(registro.CONCURSO) &&
      recorte.areas.includes(areaDe(registro)) &&
      recorte.motivos.includes(motivoDe(registro))
  );

/**
 * Saídas por competência e por motivo — a matriz que o gráfico principal desenha.
 *
 * Devolve, para cada motivo pedido, uma contagem por mês e os nomes por trás
 * dela. Meses sem saída entram com zero: é o mês sem perda nenhuma, e ele conta
 * a história tanto quanto o mês de pico.
 */
export const serieDeSaidasPorMotivo = (
  saidasFiltradas: RegistroAuditor[],
  meses: string[],
  motivos: readonly string[]
): { motivo: string; valores: number[]; nomes: string[][] }[] => {
  const indicePorMes = new Map(meses.map((mes, indice) => [mes, indice]));

  return motivos.map((motivo) => {
    const valores = new Array(meses.length).fill(0);
    const nomes: string[][] = meses.map(() => []);

    for (const registro of saidasFiltradas) {
      if (motivoDe(registro) !== motivo) continue;
      const indice = indicePorMes.get(registro.MES_SAIDA);
      if (indice === undefined) continue; // saída anterior ao início do gráfico
      valores[indice] += 1;
      nomes[indice].push(registro.NOME);
    }

    for (const lista of nomes) lista.sort((a, b) => a.localeCompare(b, 'pt-BR'));
    return { motivo, valores, nomes };
  });
};

/** Contagem por chave, preservando a ordem de `ordemPreferida` e jogando o resto ao fim. */
const contarPor = (
  registros: RegistroAuditor[],
  chave: (registro: RegistroAuditor) => string,
  ordemPreferida?: readonly string[]
): { rotulo: string; total: number; itens: RegistroAuditor[] }[] => {
  const grupos = new Map<string, RegistroAuditor[]>();
  for (const registro of registros) {
    const rotulo = chave(registro);
    const grupo = grupos.get(rotulo);
    if (grupo) grupo.push(registro);
    else grupos.set(rotulo, [registro]);
  }

  const posicao = (rotulo: string) => {
    const indice = ordemPreferida?.indexOf(rotulo) ?? -1;
    return indice === -1 ? Number.MAX_SAFE_INTEGER : indice;
  };

  return Array.from(grupos.entries())
    .map(([rotulo, itens]) => ({ rotulo, total: itens.length, itens }))
    .sort((a, b) => posicao(a.rotulo) - posicao(b.rotulo) || b.total - a.total || a.rotulo.localeCompare(b.rotulo, 'pt-BR'));
};

/** Rótulo do balde que junta o que o card de saídas não destaca. */
export const MOTIVO_OUTROS = 'Outros';

const MOTIVOS_DESTACADOS: readonly string[] = [
  MOTIVO_EXONERACAO,
  MOTIVO_VACANCIA,
  MOTIVO_APOSENTADORIA,
];

/**
 * Saídas a partir de `mesMinimo`, resumidas em quatro baldes.
 *
 * No card acima dos filtros os sete motivos viram uma parede de números. Os
 * quatro menores — falecimento, demissão, mudança de órgão na carreira e saída
 * sem ato — somados ainda cabem abaixo da aposentadoria, então juntá-los em
 * "Outros" não esconde nenhuma ordem de grandeza. A quebra completa continua na
 * caixinha "Tipo de saída", no gráfico mês a mês e na tabela detalhada.
 *
 * `mesMinimo` é o mesmo corte do gráfico (`MES_INICIO_GRAFICO_SAIDAS`, ago/2022):
 * antes dele só existiam veteranos na série, e o card diria "desde jun/2022"
 * sobre um período em que metade do universo ainda não tinha tomado posse.
 */
export const agregarPorMotivoResumido = (registros: RegistroAuditor[], mesMinimo: string) => {
  const noPeriodo = saidas(registros).filter((registro) => registro.MES_SAIDA >= mesMinimo);
  const balde = (registro: RegistroAuditor): string => {
    const motivo = motivoDe(registro);
    return MOTIVOS_DESTACADOS.includes(motivo) ? motivo : MOTIVO_OUTROS;
  };
  return contarPor(noPeriodo, balde, [...MOTIVOS_DESTACADOS, MOTIVO_OUTROS]);
};

/**
 * Saídas agrupadas por órgão de destino.
 *
 * Quem não tem destino registrado cai em "Destino não identificado" — que não é
 * o mesmo que "não foi a lugar nenhum": aposentadoria e falecimento não têm
 * destino por definição, e ficam separados. Nada aqui inventa órgão (D14).
 */
export const DESTINO_DESCONHECIDO = 'Destino não identificado';
export const DESTINO_INATIVIDADE = 'Aposentadoria ou falecimento';

export const agregarPorDestino = (registros: RegistroAuditor[]) => {
  const chave = (registro: RegistroAuditor): string => {
    if (registro.ORGAO_DESTINO) return registro.ORGAO_DESTINO;
    const motivo = motivoDe(registro);
    if (motivo === 'Aposentadoria' || motivo === 'Falecimento') return DESTINO_INATIVIDADE;
    return DESTINO_DESCONHECIDO;
  };

  const grupos = contarPor(saidas(registros), chave);
  const ordem = (rotulo: string) => {
    if (rotulo === DESTINO_DESCONHECIDO) return 3;
    if (rotulo === DESTINO_INATIVIDADE) return 2;
    return 1;
  };
  return [...grupos].sort((a, b) => ordem(a.rotulo) - ordem(b.rotulo) || b.total - a.total);
};

/** Um ponto da curva de permanência, numa competência do calendário. */
export interface PontoPermanencia {
  /** Competência, no formato `AAAAMM`. */
  mes: string;
  /** Quantas pessoas já haviam entrado até `mes`, inclusive. */
  entradas: number;
  /** Quantas dessas já haviam saído até `mes`, inclusive. */
  saidas: number;
  /** `entradas - saidas`: quantas ainda estavam na CGU no fim de `mes`. */
  restantes: number;
  /** `restantes / entradas`, em pontos percentuais. `null` antes da primeira entrada. */
  percentual: number | null;
}

/**
 * Permanência de uma coorte mês a mês do calendário.
 *
 * Em cada competência `t`: quantas pessoas da coorte já tinham entrado até `t`
 * (ENTRADAS), quantas dessas já tinham saído até `t` (SAÍDAS), e o quociente
 * `(ENTRADAS - SAÍDAS) / ENTRADAS` — a fração da coorte que ainda estava lá.
 *
 * Duas escolhas que mudam o número e por isso ficam escritas:
 *
 * 1. Entradas e saídas são contadas por PESSOA, sobre `dados.csv`, e não pelos
 *    campos `ENTRADAS`/`SAIDAS` de `serie_mensal.csv`. Aqueles são EVENTOS: as
 *    seis pessoas que somem do SIAPE por alguns meses e voltam (D13) aparecem
 *    lá duas vezes, e o denominador ficaria maior que o tamanho da coorte.
 * 2. O numerador só desconta saídas de quem é DA COORTE. Descontar as saídas de
 *    todo mundo — veteranos inclusive — de um denominador que só tem entrantes
 *    daria um número que não é permanência de ninguém.
 *
 * Diferente da curva por tempo-desde-a-entrada que existia aqui antes, o
 * denominador CRESCE ao longo do eixo: quem entrou em 2023 entra na conta a
 * partir de 2023. Por isso cada ponto carrega `entradas` — sem isso, uma queda
 * causada por um lote novo de posses passaria por evasão.
 */
export const curvaDePermanencia = (
  registros: RegistroAuditor[],
  idConcurso: string,
  meses: readonly string[]
): PontoPermanencia[] => {
  const coorte = registros.filter((registro) => registro.CONCURSO === idConcurso && registro.MES_ENTRADA);

  return meses.map((mes) => {
    const entrantes = coorte.filter((registro) => registro.MES_ENTRADA <= mes);
    // D13: `MES_SAIDA` é o primeiro mês de AUSÊNCIA, então quem saiu em `mes`
    // já não está na CGU no fim de `mes`.
    const saidas = entrantes.filter((registro) => registro.MES_SAIDA && registro.MES_SAIDA <= mes).length;
    const restantes = entrantes.length - saidas;
    return {
      mes,
      entradas: entrantes.length,
      saidas,
      restantes,
      percentual: entrantes.length === 0 ? null : (100 * restantes) / entrantes.length,
    };
  });
};

/** Saídas por competência, para cruzar com a série mensal. */
export const saidasPorMes = (registros: RegistroAuditor[]): Map<string, RegistroAuditor[]> => {
  const mapa = new Map<string, RegistroAuditor[]>();
  for (const registro of saidas(registros)) {
    const grupo = mapa.get(registro.MES_SAIDA);
    if (grupo) grupo.push(registro);
    else mapa.set(registro.MES_SAIDA, [registro]);
  }
  return mapa;
};

/** Taxa de evasão de uma coorte: quantos saíram sobre quantos passaram por ela. */
export const evasaoDaCoorte = (registros: RegistroAuditor[], idConcurso: string) => {
  const coorte = registros.filter((registro) => registro.CONCURSO === idConcurso);
  const saiu = coorte.filter(saiuDaCgu).length;
  return {
    total: coorte.length,
    saiu,
    percentual: coorte.length === 0 ? 0 : (100 * saiu) / coorte.length,
  };
};

/** Coortes conhecidas, na ordem em que a interface as mostra. */
export const COORTES: readonly string[] = [ID_CONCURSO_2021, ID_CONCURSO_VETERANO];
