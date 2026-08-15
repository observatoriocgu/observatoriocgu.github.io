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
  MOTIVO_DEMISSAO,
  MOTIVO_EXONERACAO,
  MOTIVO_FALECIMENTO,
  MOTIVO_OUTRO,
  MOTIVO_SEM_ATO,
  MOTIVO_VACANCIA,
  SITUACAO_EM_EXERCICIO,
  SITUACAO_MUDOU_ORGAO,
} from '../constants';
import {
  DetalheSaida,
  LinhaSerieMensal,
  LogDeAlteracoes,
  PontoSerieMensal,
  RegistroAuditor,
  SaidaRecenteDou,
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

/**
 * O motivo como o `dados.csv` o gravou.
 *
 * Vazio vira o rótulo de "o DOU não disse por quê". Devolve a demissão pelo
 * nome: só a tabela detalhada tem licença para chamar esta função (D18) — todo
 * o resto usa `motivoDe`.
 */
export const motivoDetalhado = (registro: RegistroAuditor): string =>
  registro.MOTIVO_SAIDA || MOTIVO_SEM_ATO;

/**
 * O motivo já pronto para exibir, com a demissão sob rótulo neutro (D18).
 *
 * Este é o caminho PADRÃO, e é de propósito: quem escrever uma tela nova daqui
 * a seis meses vai chamar `motivoDe` sem saber que a regra existe, e vai acertar
 * mesmo assim. A pessoa continua contada em tudo — card, gráfico, curva,
 * destinos, histórico, relatório —, com o mesmo balde e o mesmo total; o que
 * não vai à tela é a palavra.
 */
export const motivoDe = (registro: RegistroAuditor): string => {
  const motivo = motivoDetalhado(registro);
  return motivo === MOTIVO_DEMISSAO ? MOTIVO_OUTRO : motivo;
};

/**
 * Área já pronta para exibir.
 *
 * Vazia não é um caso só: no veterano é "não se aplica", porque a especialidade
 * só existe no edital do concurso de 2021 e ele não o fez; em quem é do concurso
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

/** `SITUACAO` correspondente a cada tipo de ato — o espelho de `dou.SITUACAO_POR_TIPO`. */
const SITUACAO_POR_TIPO: Readonly<Record<string, string>> = {
  vacancia: 'VACÂNCIA',
  aposentadoria: 'APOSENTADO',
  exoneracao: 'EXONERADO',
  falecimento: 'FALECIDO',
};

/**
 * Traz para dentro do painel as saídas que só o DOU conhece (D22).
 *
 * O ato já foi publicado; o Portal da Transparência é que ainda não entregou a
 * competência que mostraria a ausência (~2 meses de atraso). A pessoa JÁ ESTÁ no
 * `dados.csv` — ativa —, então aqui não se cria linha nova: sobrepõe-se a saída
 * ao registro que já existe. É por isso que ela chega à tela com concurso, área e
 * unidade, e responde aos filtros como qualquer outra.
 *
 * POR QUE ISTO ACONTECE NO NAVEGADOR, e não no `construir_painel.py`. Porque o
 * `construir_painel.py` depende dos snapshots do Portal, que não estão no Git e
 * portanto não existem no CI. Quem roda todo dia é a varredura do DOU, que
 * atualiza o `atos_dou.json`. Se a mescla morasse só no Python, uma saída
 * descoberta hoje esperaria a próxima execução local para aparecer — que é
 * exatamente a defasagem que esta mescla existe para eliminar.
 *
 * TRÊS GUARDAS CONTRA CONTAR ERRADO, que era o motivo de estas saídas ficarem
 * fora das contagens até 15/08/2026:
 *
 *   - sobrepõe-se por `ID_SERVIDOR_PORTAL`, casado no Python por nome MAIS
 *     matrícula (D12 — nome não é chave). Ato sem id casado não entra;
 *   - só se aplica a quem NÃO tem `MES_SAIDA`. Quem o SIAPE já mostrou saindo
 *     fica com a versão do SIAPE, e uma pessoa com dois atos não vira duas
 *     saídas;
 *   - quem não está no `dados.csv` não entra de jeito nenhum — é o caso do ato
 *     sobre servidor de outro cargo ou já fora do quadro.
 */
export const mesclarSaidasDoDou = (
  registros: RegistroAuditor[],
  saidasRecentes: SaidaRecenteDou[]
): RegistroAuditor[] => {
  const porId = new Map(saidasRecentes.filter((s) => s.idServidor).map((s) => [s.idServidor, s]));
  if (porId.size === 0) return registros;

  return registros.map((registro) => {
    const saida = porId.get(registro.ID_SERVIDOR_PORTAL);
    if (!saida) return registro;

    // O SIAPE já mostrou esta pessoa sumindo, mas ninguém tinha achado o ato
    // dela — ela aparecia como "saída sem ato identificado". O ato COMPLETA o
    // motivo e não mexe na competência: quem sabe quando ela saiu é o cadastro,
    // e o selo continua sendo SIAPE + DOU.
    if (registro.MES_SAIDA) {
      if (registro.MOTIVO_SAIDA || !saida.jaNoSiape) return registro;
      return {
        ...registro,
        SITUACAO: SITUACAO_POR_TIPO[saida.tipo] ?? registro.SITUACAO,
        MOTIVO_SAIDA: saida.rotulo,
        FONTE_MOTIVO: 'DOU',
        DATA_PUBLICACAO_SAIDA: saida.dataPublicacao,
        ATO_SAIDA_TITULO: saida.titulo,
        ATO_SAIDA_URL: saida.urlDou,
        ATO_SAIDA_ARQUIVO: saida.arquivo ?? '',
      };
    }

    return {
      ...registro,
      // A competência da PUBLICAÇÃO. Não é a data do fato — o ato costuma dizer
      // "a contar de" alguns dias antes —, mas é a única que se tem antes de o
      // SIAPE confirmar, e erra por dias, não por meses.
      MES_SAIDA: saida.dataPublicacao.slice(0, 4) + saida.dataPublicacao.slice(5, 7),
      SAIDA_NO_SIAPE: 'NÃO',
      SITUACAO: SITUACAO_POR_TIPO[saida.tipo] ?? registro.SITUACAO,
      MOTIVO_SAIDA: saida.rotulo,
      FONTE_MOTIVO: 'DOU',
      DATA_PUBLICACAO_SAIDA: saida.dataPublicacao,
      ATO_SAIDA_TITULO: saida.titulo,
      ATO_SAIDA_URL: saida.urlDou,
      ATO_SAIDA_ARQUIVO: saida.arquivo ?? '',
    };
  });
};

/**
 * Põe no histórico de alterações as saídas que só o DOU conhece (D22).
 *
 * O `alteracoes-registros.json` nasce do diff mês a mês do SIAPE, no
 * `construir_painel.py`, e por isso vai só até a última competência do Portal.
 * Quem saiu depois disso não aparecia em lugar nenhum desta página — nem como
 * saída, nem como pendência. Aqui elas entram no bloco do mês correspondente,
 * criando o mês se ele ainda não existir.
 *
 * Recebe os registros JÁ MESCLADOS por `mesclarSaidasDoDou`: é de lá que vêm
 * `SAIDA_NO_SIAPE`, a situação e a unidade.
 */
export const acrescentarSaidasDoDou = (
  log: LogDeAlteracoes,
  registros: RegistroAuditor[]
): LogDeAlteracoes => {
  const soDoDou = registros.filter((r) => r.SAIDA_NO_SIAPE === 'NÃO' && r.MES_SAIDA);
  if (soDoDou.length === 0) return log;

  const porMes = new Map(log.history.map((mes) => [mes.mes, { ...mes, changes: [...mes.changes] }]));

  for (const registro of soDoDou) {
    const mes = porMes.get(registro.MES_SAIDA) ?? {
      mes: registro.MES_SAIDA,
      data: `${registro.MES_SAIDA.slice(0, 4)}-${registro.MES_SAIDA.slice(4)}-01`,
      changeCount: 0,
      changes: [],
    };
    // Uma pessoa só aparece uma vez no mês: se o SIAPE já a tivesse registrado
    // saindo, ela não teria sido mesclada — mas a guarda é barata e o efeito de
    // errar seria a mesma saída contada duas vezes na tela.
    if (!mes.changes.some((mudanca) => mudanca.id === registro.ID_SERVIDOR_PORTAL)) {
      mes.changes.push({
        id: registro.ID_SERVIDOR_PORTAL,
        nome: registro.NOME,
        tipo: 'saida',
        fromSituacao: SITUACAO_EM_EXERCICIO,
        toSituacao: registro.SITUACAO,
        orgaoDestino: registro.ORGAO_DESTINO,
        unidade: registro.UNIDADE,
        concurso: registro.CONCURSO,
      });
    }
    porMes.set(mes.mes, mes);
  }

  // O JSON vem do mês mais novo para o mais antigo, e a página conta com isso.
  const history = [...porMes.values()]
    .map((mes) => ({ ...mes, changeCount: mes.changes.length }))
    .sort((a, b) => b.mes.localeCompare(a.mes));

  return {
    ...log,
    // O log deixou de ser só do SIAPE: dizer que a fonte é uma só passaria a ser
    // falso justamente nas linhas mais recentes da página.
    fonte: `${log.fonte}, e Diário Oficial da União para as saídas que o cadastro ainda não registrou`,
    ultimoMes: history[0]?.mes ?? log.ultimoMes,
    totalChangeCount: history.reduce((soma, mes) => soma + mes.changeCount, 0),
    history,
  };
};

/**
 * As fontes que atestam que a pessoa saiu (D20).
 *
 * `SIAPE` sai de graça para toda linha do `dados.csv` com `MES_SAIDA`: a
 * competência da saída é justamente o mês em que a pessoa deixou de aparecer no
 * cadastro depois de aparecer no anterior — é a definição da D13, não uma
 * inferência à parte. `DOU` entra quando há ato publicado.
 */
export const fontesDaSaida = (registro: RegistroAuditor): string[] => {
  const fontes: string[] = [];
  // `SAIDA_NO_SIAPE = 'NÃO'` só existe nas linhas que `mesclarSaidasDoDou`
  // sobrepôs: ali o ato saiu e o cadastro ainda não mostrou a ausência.
  if (registro.MES_SAIDA && registro.SAIDA_NO_SIAPE !== 'NÃO') fontes.push('SIAPE');
  if (registro.FONTE_MOTIVO) fontes.push(registro.FONTE_MOTIVO);
  return [...new Set(fontes)];
};

/** Uma saída no formato que a interface consome, com os selos de fonte. */
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
  fontesSaida: fontesDaSaida(registro),
  destino: registro.ORGAO_DESTINO,
  fonteDestino: registro.FONTE_DESTINO,
  dataPublicacao: registro.DATA_PUBLICACAO_SAIDA,
  atoTitulo: registro.ATO_SAIDA_TITULO,
  atoUrl: urlDoAto(registro),
  provisoria: registro.SAIDA_PROVISORIA === 'SIM',
  soNoDou: registro.SAIDA_NO_SIAPE === 'NÃO',
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
  concursos: readonly string[];
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
      recorte.concursos.includes(registro.CONCURSO) &&
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

/**
 * Rótulo do balde que junta o que o card de saídas não destaca.
 *
 * NÃO confundir com `MOTIVO_OUTRO`, das constantes: aquele é o rótulo neutro de
 * um motivo só (a demissão, D18) e vale em toda a interface; este é um resumo
 * de quatro motivos e só existe dentro deste card. Os dois somam coisas
 * diferentes de propósito, e por isso não dividem o mesmo texto — "Outros: 21"
 * no card e "Outro motivo: 1" na tabela de destinos não se contradizem.
 */
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

export const DESTINO_DESCONHECIDO = 'Destino não identificado';
export const DESTINO_INATIVIDADE = 'Aposentadoria ou falecimento';
export const SAIDA_POSSE = 'Posse em outro cargo';

/**
 * Rótulo de exibição de `SITUACAO_MUDOU_ORGAO` nesta tabela.
 *
 * O valor gravado em `MOTIVO_SAIDA` é a constante em caixa alta, e é ela que a
 * legenda do gráfico e a caixinha de tipo de saída mostram. Aqui, ao lado de
 * "Posse em outro cargo" e "Aposentadoria ou falecimento", a caixa alta soaria
 * como grito — o rótulo muda, o valor por trás não.
 */
export const SAIDA_MUDOU_ORGAO = 'Mudou de órgão na carreira';

/**
 * Como cada motivo do `dados.csv` cai nos baldes do primeiro nível.
 *
 * Aposentadoria e falecimento andam juntos porque a pergunta da tabela é "para
 * onde foi", e nesses dois casos não há para onde: não é destino desconhecido,
 * é destino inexistente. O resto é um balde por motivo.
 *
 * `MOTIVO_OUTRO` chega aqui já mascarado por `motivoDe` (D18): a pessoa entra
 * na tabela e no total, com balde próprio, e o que não aparece é o nome do
 * motivo. Nada a fazer nesta função — ela nunca vê a demissão.
 */
const BALDE_POR_MOTIVO: Readonly<Record<string, string>> = {
  [MOTIVO_VACANCIA]: SAIDA_POSSE,
  [MOTIVO_EXONERACAO]: MOTIVO_EXONERACAO,
  [MOTIVO_APOSENTADORIA]: DESTINO_INATIVIDADE,
  [MOTIVO_FALECIMENTO]: DESTINO_INATIVIDADE,
  [SITUACAO_MUDOU_ORGAO]: SAIDA_MUDOU_ORGAO,
};

/** A ordem do primeiro nível. Posse vem primeiro: é o grosso da evasão. */
const ORDEM_DOS_BALDES: readonly string[] = [
  SAIDA_POSSE,
  MOTIVO_EXONERACAO,
  DESTINO_INATIVIDADE,
  SAIDA_MUDOU_ORGAO,
  MOTIVO_SEM_ATO,
  MOTIVO_OUTRO,
];

/** Um órgão de chegada, dentro de um tipo de saída. */
export interface DestinoAgregado {
  rotulo: string;
  total: number;
  itens: RegistroAuditor[];
}

/** Um tipo de saída, com a quebra por órgão quando ela existe. */
export interface SaidaAgregada extends DestinoAgregado {
  /** Vazio quando nenhuma saída do balde tem órgão registrado. */
  destinos: DestinoAgregado[];
}

/**
 * Saídas em dois níveis: o tipo da saída e, dentro dele, o órgão de chegada.
 *
 * O nível de cima é o TIPO, e não o órgão, porque "Tribunal de Contas da União"
 * e "Aposentadoria ou falecimento" nunca foram a mesma espécie de coisa — uma
 * lista só misturava destino com ausência de destino e com lacuna de apuração.
 *
 * O nível de baixo só se abre em quem tem para onde ir: um balde sem nenhum
 * órgão registrado vai direto para a lista de pessoas, em vez de fabricar um
 * subnível de um item só. Quem tem destino em branco cai em "Destino não
 * identificado", que é lacuna da busca, não afirmação sobre a pessoa (D14).
 */
export const agregarPorTipoDeSaida = (registros: RegistroAuditor[]): SaidaAgregada[] => {
  const balde = (registro: RegistroAuditor): string => BALDE_POR_MOTIVO[motivoDe(registro)] ?? motivoDe(registro);

  return contarPor(saidas(registros), balde, ORDEM_DOS_BALDES).map((grupo) => {
    if (!grupo.itens.some((registro) => registro.ORGAO_DESTINO)) return { ...grupo, destinos: [] };

    const destinos = contarPor(grupo.itens, (registro) => registro.ORGAO_DESTINO || DESTINO_DESCONHECIDO);
    return {
      ...grupo,
      // A lacuna vai para o fim: o que se apurou vem antes do que falta apurar.
      destinos: destinos.sort(
        (a, b) =>
          Number(a.rotulo === DESTINO_DESCONHECIDO) - Number(b.rotulo === DESTINO_DESCONHECIDO) ||
          b.total - a.total ||
          a.rotulo.localeCompare(b.rotulo, 'pt-BR')
      ),
    };
  });
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
 * Permanência de um concurso mês a mês do calendário.
 *
 * Em cada competência `t`: quantas pessoas do concurso já tinham entrado até `t`
 * (ENTRADAS), quantas dessas já tinham saído até `t` (SAÍDAS), e o quociente
 * `(ENTRADAS - SAÍDAS) / ENTRADAS` — a fração do concurso que ainda estava lá.
 *
 * Duas escolhas que mudam o número e por isso ficam escritas:
 *
 * 1. Entradas e saídas são contadas por PESSOA, sobre `dados.csv`, e não pelos
 *    campos `ENTRADAS`/`SAIDAS` de `serie_mensal.csv`. Aqueles são EVENTOS: as
 *    seis pessoas que somem do SIAPE por alguns meses e voltam (D13) aparecem
 *    lá duas vezes, e o denominador ficaria maior que o tamanho do concurso.
 * 2. O numerador só desconta saídas de quem é DO CONCURSO. Descontar as saídas de
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
  const doConcurso = registros.filter((registro) => registro.CONCURSO === idConcurso && registro.MES_ENTRADA);

  return meses.map((mes) => {
    const entrantes = doConcurso.filter((registro) => registro.MES_ENTRADA <= mes);
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

/** Taxa de evasão de um concurso: quantos saíram sobre quantos passaram por ele. */
export const evasaoDoConcurso = (registros: RegistroAuditor[], idConcurso: string) => {
  const doConcurso = registros.filter((registro) => registro.CONCURSO === idConcurso);
  const saiu = doConcurso.filter(saiuDaCgu).length;
  return {
    total: doConcurso.length,
    saiu,
    percentual: doConcurso.length === 0 ? 0 : (100 * saiu) / doConcurso.length,
  };
};

// === Os primeiros colocados de cada especialidade ===
//
// A pergunta é antiga e sempre foi respondida de ouvido: a CGU perde mais quem
// passou na frente? Aqui ela vira tabela — os dez primeiros de cada
// especialidade do concurso de 2021, e se cada um continua na CGU.
//
// A lista de aprovados NÃO é o dados.csv: quem nunca tomou posse não está lá, e
// é justamente essa a informação que faria a tabela mentir. Ela vem do
// `data/concurso_2021.csv`, que é o Edital CGU nº 5 (D17), e o dados.csv entra
// só para dizer o que aconteceu depois com cada nome.

/**
 * A lista do edital que serve de classificação geral.
 *
 * `POSICAO_CONCURSO` no CSV é a posição DENTRO de uma lista de vaga — por
 * modalidade e por UF —, e não uma classificação geral: em Auditoria há oito
 * pessoas com "posição 1", uma por UF. Uma classificação geral por
 * especialidade NÃO EXISTE no edital, e por isso ela é reconstruída aqui: a
 * ordem é a nota, que é a mesma prova para todo mundo da especialidade.
 *
 * Vaga regional não é especialidade à parte: quem concorreu a vaga de estado
 * fez a prova de Auditoria e Fiscalização e disputa a mesma lista, sem recorte
 * de UF em lugar nenhum do painel. As quatro especialidades saem do edital, e
 * só Auditoria tem vagas regionais.
 *
 * A lista de ampla concorrência da vaga de Brasília entra só como desempate,
 * porque é a única que ordena quase todo o topo das quatro especialidades, e
 * ela resolve os empates de nota do jeito que o edital os resolveu. Quem não
 * está nela — as vagas regionais — não tem como ser ordenado contra ela e fica
 * atrás em caso de empate. Isso é critério do observatório, não do edital, e é
 * por isso que `empatadosNoCorte` existe: quem empatou com o último e ficou de
 * fora aparece embaixo da tabela em vez de sumir.
 */
const MODALIDADE_CLASSIFICACAO_GERAL = 'Ampla Concorrência';
const UF_CLASSIFICACAO_GERAL = 'DF';

/** Posição de quem não está na lista de desempate: vai para o fim, sem virar `NaN`. */
const SEM_POSICAO = Number.MAX_SAFE_INTEGER;

/**
 * O que o observatório sabe sobre um aprovado.
 *
 * São três estados, não dois. `sem_registro` é quem passou no concurso e nunca
 * apareceu no quadro da CGU — não é "continua na CGU" nem "saiu da CGU", e
 * empurrá-lo para um dos dois publicaria como Auditor da casa alguém que nunca
 * tomou posse.
 */
export type SituacaoDoAprovado = 'ativo' | 'saiu' | 'sem_registro';

export interface AprovadoDoTopo {
  /** 1 a N, a classificação na especialidade. `0` em quem ficou de fora por empate. */
  posicao: number;
  nome: string;
  /** Nota final na especialidade, como o edital a publicou. */
  nota: string;
  situacao: SituacaoDoAprovado;
  /** Competência da saída; `''` em quem não saiu. */
  mesSaida: string;
  /** Já mascarado pela D18: nunca traz a demissão pelo nome. `''` em quem não saiu. */
  motivo: string;
}

export interface TopoDaEspecialidade {
  area: string;
  aprovados: AprovadoDoTopo[];
  /**
   * Quem tem a mesma nota do último colocado da tabela e ficou de fora só pelo
   * desempate. Quase sempre vazio — e, quando não está, a tabela tem de dizer,
   * porque aí o corte foi do observatório e não da prova.
   */
  empatadosNoCorte: AprovadoDoTopo[];
}

/**
 * Os `quantidade` primeiros colocados de cada especialidade, e o que houve com
 * cada um.
 *
 * `registros` tem de ser a lista já mesclada com as saídas do DOU (D22) — é o
 * que faz uma saída publicada ontem aparecer aqui hoje, e não daqui a dois
 * meses. Casa-se por `INSCRICAO`, que é a chave do concurso e é o que o
 * pipeline já gravou no dados.csv; o nome não casa nada (D12).
 */
export const evasaoDosPrimeirosColocados = (
  registros: RegistroAuditor[],
  aprovados: LinhaCsv[],
  areas: readonly string[],
  quantidade: number
): TopoDaEspecialidade[] => {
  const porInscricao = new Map<string, RegistroAuditor>();
  for (const registro of registros) {
    if (registro.INSCRICAO) porInscricao.set(registro.INSCRICAO, registro);
  }

  const posicaoDeDesempate = new Map<string, number>();
  for (const linha of aprovados) {
    if (!linha.INSCRICAO) continue;
    if (linha.MODALIDADE !== MODALIDADE_CLASSIFICACAO_GERAL) continue;
    if (linha.UF_VAGA !== UF_CLASSIFICACAO_GERAL) continue;
    const posicao = Number(linha.POSICAO_CONCURSO);
    if (posicao > 0) posicaoDeDesempate.set(linha.INSCRICAO, posicao);
  }

  // Um aprovado por inscrição: quem concorreu por cota aparece duas vezes no
  // edital, na lista da cota e na de ampla concorrência. Sem isto, um nome
  // ocuparia duas posições da tabela. Linha sem nota é sub judice, que o edital
  // publica sem classificação — não dá para ordenar, e fica de fora.
  const unicos = new Map<string, LinhaCsv>();
  for (const linha of aprovados) {
    if (!linha.INSCRICAO || !linha.NOTA) continue;
    if (!unicos.has(linha.INSCRICAO)) unicos.set(linha.INSCRICAO, linha);
  }
  const todos = Array.from(unicos.values());

  /** O que se sabe de um aprovado, a partir da linha do edital. */
  const comoAprovado = (linha: LinhaCsv, posicao: number): AprovadoDoTopo => {
    const registro = porInscricao.get(linha.INSCRICAO);
    const base = { posicao, nome: linha.NOME, nota: linha.NOTA };
    if (!registro) return { ...base, situacao: 'sem_registro', mesSaida: '', motivo: '' };
    if (!saiuDaCgu(registro)) return { ...base, situacao: 'ativo', mesSaida: '', motivo: '' };
    return { ...base, situacao: 'saiu', mesSaida: registro.MES_SAIDA, motivo: motivoDe(registro) };
  };

  return areas.map((area) => {
    const classificados = todos
      .filter((linha) => linha.AREA === area)
      .sort(
        (a, b) =>
          Number(b.NOTA) - Number(a.NOTA) ||
          (posicaoDeDesempate.get(a.INSCRICAO) ?? SEM_POSICAO) -
            (posicaoDeDesempate.get(b.INSCRICAO) ?? SEM_POSICAO) ||
          a.NOME.localeCompare(b.NOME, 'pt-BR')
      );

    const aprovados = classificados.slice(0, quantidade).map((linha, indice) => comoAprovado(linha, indice + 1));
    const notaDeCorte = aprovados.length === quantidade ? Number(aprovados[aprovados.length - 1].nota) : NaN;
    const empatadosNoCorte = classificados
      .slice(quantidade)
      .filter((linha) => Number(linha.NOTA) === notaDeCorte)
      .map((linha) => comoAprovado(linha, 0));

    return { area, aprovados, empatadosNoCorte };
  });
};

/** Concursos conhecidos, na ordem em que a interface os mostra. */
export const CONCURSOS: readonly string[] = [ID_CONCURSO_2021, ID_CONCURSO_VETERANO];
