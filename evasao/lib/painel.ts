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
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVO_SEM_ATO,
  MOTIVOS_SAIDA,
  SITUACAO_EM_EXERCICIO,
} from '../constants';
import {
  DetalheSaida,
  LinhaSerieMensal,
  PontoSerieMensal,
  RegistroAuditor,
} from '../types';
import { LinhaCsv, baseDoSite, distanciaEmMeses } from './dados';

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

/** Área já pronta para exibir: vazia vira o rótulo de desconhecida. */
export const areaDe = (registro: RegistroAuditor): string => registro.AREA || AREA_DESCONHECIDA;

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

/** Saídas agrupadas por motivo, na ordem de `MOTIVOS_SAIDA`. */
export const agregarPorMotivo = (registros: RegistroAuditor[]) =>
  contarPor(saidas(registros), motivoDe, MOTIVOS_SAIDA);

/**
 * Saídas agrupadas por unidade de lotação, com a quebra por coorte.
 *
 * A unidade vem do `dados.csv` já normalizada pelo CÓDIGO da UORG — nunca pelo
 * nome, que muda de grafia entre meses e infla a contagem. Até a Fase 3 este
 * agrupamento só olhava `EXONERADO`; agora considera toda saída.
 */
export const agregarPorUnidade = (registros: RegistroAuditor[], limite = 12) => {
  const grupos = contarPor(saidas(registros), (registro) => registro.UNIDADE || 'Não informada');
  const ordenados = [...grupos].sort((a, b) => b.total - a.total);
  return ordenados.slice(0, limite);
};

/**
 * Saídas agrupadas por UF de exercício.
 *
 * `UF` vazia quer dizer que a sub-unidade não permite deduzir o estado. Note que
 * o Portal só passou a preencher `UF_EXERCICIO` no fim de 2023 — este corte é
 * por unidade de LOTAÇÃO, que existe desde 202206.
 */
export const agregarPorUf = (registros: RegistroAuditor[]) => {
  const grupos = contarPor(saidas(registros), (registro) => registro.UF || '—');
  return [...grupos].sort((a, b) => b.total - a.total);
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

/** Um ponto da curva de permanência: `t` meses após a entrada. */
export interface PontoPermanencia {
  /** Meses decorridos desde a entrada. */
  mes: number;
  /** Quantas pessoas já foram observadas por pelo menos `mes` meses. */
  base: number;
  /** Quantas dessas ainda estavam na CGU. */
  restantes: number;
  /** `restantes / base`, em pontos percentuais. */
  percentual: number;
}

/**
 * Curva de permanência de uma coorte: % ainda na CGU a cada mês desde a entrada.
 *
 * A base encolhe conforme `mes` cresce, porque quem entrou em 2025 ainda não
 * completou 40 meses de observação — por isso cada ponto carrega o próprio
 * denominador, e a curva para onde a base fica pequena demais para significar
 * alguma coisa. Sem esse cuidado, o rabo da curva viraria ruído: no limite,
 * 100% de uma pessoa só.
 *
 * "Ainda na CGU no mês `t`" = não tem competência de saída, ou a saída é
 * posterior a `t` (D13: a saída é o primeiro mês de AUSÊNCIA).
 */
export const curvaDePermanencia = (
  registros: RegistroAuditor[],
  idConcurso: string,
  ultimoMes: string,
  baseMinima = 50
): PontoPermanencia[] => {
  const coorte = registros.filter((registro) => registro.CONCURSO === idConcurso && registro.MES_ENTRADA);
  if (coorte.length === 0) return [];

  const observados = coorte.map((registro) => ({
    // Quantos meses a pessoa já pôde ser observada.
    janela: distanciaEmMeses(registro.MES_ENTRADA, ultimoMes),
    // Em que mês da própria trajetória ela sumiu; `Infinity` = nunca sumiu.
    saidaEm: registro.MES_SAIDA ? distanciaEmMeses(registro.MES_ENTRADA, registro.MES_SAIDA) : Number.POSITIVE_INFINITY,
  }));

  const janelaMaxima = Math.max(...observados.map((pessoa) => pessoa.janela));
  const pontos: PontoPermanencia[] = [];

  for (let mes = 0; mes <= janelaMaxima; mes += 1) {
    const naBase = observados.filter((pessoa) => pessoa.janela >= mes);
    if (naBase.length < baseMinima) break;
    const restantes = naBase.filter((pessoa) => pessoa.saidaEm > mes).length;
    pontos.push({
      mes,
      base: naBase.length,
      restantes,
      percentual: (100 * restantes) / naBase.length,
    });
  }

  return pontos;
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
