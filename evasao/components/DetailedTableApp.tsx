import React, { useEffect, useMemo, useState } from 'react';

import {
  AREAS_SEM_ESPECIALIDADE,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVOS_SAIDA_DETALHADOS,
  SITUACAO_EM_EXERCICIO,
  rotuloDoConcurso,
} from '../constants';
import { RegistroAuditor } from '../types';
import {
  carregarCsv,
  formatarCompetenciaLonga,
  formatarDataIsoParaBr,
} from '../lib/dados';
import {
  areaDe,
  comoRegistros,
  fontesDaSaida,
  motivoDetalhado,
  saiuDaCgu,
  urlDoAto,
} from '../lib/painel';
import {
  SeloFonte,
  SelosDaLinha,
  rotuloDoLinkDeDestino,
  tituloDoLinkDeDestino,
} from './Selos';

const TODOS = '';

/** Quantas linhas renderizar de uma vez. 2.009 células vezes 14 colunas trava o navegador. */
const PAGINA = 300;

const normalizar = (valor: string) =>
  String(valor ?? '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('pt-BR').trim();

/**
 * Cor de fundo da linha por situação.
 *
 * O vocabulário é o da D11 — não há mais `DESISTENTE`, `INAPTO ADMISSIONAL` nem
 * `AFASTAMENTO PRELIMINAR À APOSENTADORIA`: o observatório só enxerga quem já
 * estava lotado na CGU, e essas três situações eram do modelo de MG.
 */
const CORES_POR_SITUACAO: Record<string, string> = {
  [SITUACAO_EM_EXERCICIO]: 'bg-green-100',
  'EXONERADO': 'bg-red-100',
  'VACÂNCIA': 'bg-orange-100',
  'APOSENTADO': 'bg-purple-100',
  'FALECIDO': 'bg-slate-200',
  'DEMITIDO': 'bg-fuchsia-100',
  'MUDOU DE ÓRGÃO NA CARREIRA': 'bg-blue-100',
  'SAÍDA SEM ATO IDENTIFICADO': 'bg-yellow-100',
};

const Celula: React.FC<{
  children?: React.ReactNode;
  alinhamento?: string;
  className?: string;
  titulo?: string;
}> = ({ children, alinhamento = 'text-center', className = '', titulo }) => (
  <td
    title={titulo}
    className={`border border-black px-1 py-0.5 text-[10px] text-gray-700 ${alinhamento} ${className}`}
  >
    {children}
  </td>
);

interface Coluna {
  chave: string;
  titulo: string;
  /**
   * O conteúdo da coluna como TEXTO. É o que ordena, é o que vai para o CSV e,
   * quando não há `celula`, é o que aparece na tela. Devolve vazio — e não "-" —
   * quando não há dado: o traço é decoração da tela, e ordenar por ele poria as
   * lacunas no meio da lista, em vez de no fim.
   */
  valor: (registro: RegistroAuditor) => string;
  /** Ordena como número, e não como texto ("10" antes de "9"). */
  numerica?: boolean;
  /** O que a tela mostra, quando é mais que o texto de `valor`. */
  celula?: (registro: RegistroAuditor) => React.ReactNode;
  /** O que o CSV leva, quando é mais útil que o texto de `valor`. */
  exportar?: (registro: RegistroAuditor) => string;
  /** O `title` da célula, para o que não cabe escrito. */
  titulo_da_celula?: (registro: RegistroAuditor) => string | undefined;
  alinhamento?: string;
  classe?: string;
}

/**
 * As colunas, em UMA definição.
 *
 * Cabeçalho, célula, ordenação e exportação saem todos daqui. Havia antes uma
 * lista de títulos no `<thead>` e outra de células no `<tbody>`, e foi assim que
 * a Especialidade passou a mentir: a célula lia `registro.AREA` cru enquanto o
 * filtro do topo usava `areaDe`, então filtrar por "Veterano" devolvia um punhado
 * de linhas cuja coluna Especialidade dizia "-". Com uma definição só, a coluna e
 * o filtro não têm como divergir de novo.
 *
 * A ORDEM é a da leitura, e as quatro últimas colunas são duas afirmações
 * separadas: a pessoa SAIU (quando, quem atesta, qual ato) e só então FOI para
 * algum lugar (para onde, quem atesta, qual documento). Enquanto a procedência
 * da saída ficava entre o órgão de destino e o ato, o selo `SIAPE` da saída
 * parecia responder pelo destino — e o destino, que pode vir do ranking, parecia
 * ter ato publicado. O motivo não tem coluna própria porque a situação já o diz:
 * `VACÂNCIA` ao lado de "Vacância (posse em outro cargo)" gastava uma coluna
 * para repetir a mesma palavra.
 */
const COLUNAS: readonly Coluna[] = [
  {
    chave: 'nome',
    titulo: 'Nome',
    valor: (r) => r.NOME,
    alinhamento: 'text-left',
    classe: 'font-medium text-gray-900',
  },
  { chave: 'concurso', titulo: 'Concurso', valor: (r) => rotuloDoConcurso(r.CONCURSO) },
  // `areaDe`, e não `r.AREA`: é o mesmo que o filtro de Especialidade usa, e é
  // ele que sabe que quem não tem área no edital é veterano, não é lacuna.
  { chave: 'area', titulo: 'Especialidade', valor: areaDe },
  { chave: 'posicao', titulo: 'Class.', valor: (r) => r.POSICAO_CONCURSO, numerica: true },
  { chave: 'modalidade', titulo: 'Modalidade', valor: (r) => r.MODALIDADE },
  { chave: 'unidade', titulo: 'Unidade', valor: (r) => r.UNIDADE },
  { chave: 'uf', titulo: 'UF', valor: (r) => r.UF },
  {
    chave: 'situacao',
    titulo: 'Situação',
    valor: (r) => r.SITUACAO,
    classe: 'whitespace-nowrap',
    // A situação é o motivo dito em uma palavra — `VACÂNCIA` é "Vacância (posse
    // em outro cargo)". O que a palavra deixa de fora vai no `title`, inclusive a
    // demissão: esta é a única página com licença para nomeá-la (D18), e a coluna
    // já mostrava `DEMITIDO`.
    titulo_da_celula: (r) => (saiuDaCgu(r) ? motivoDetalhado(r) : undefined),
    celula: (r) => (
      <>
        {r.SITUACAO || '-'}
        {r.SAIDA_PROVISORIA === 'SIM' && (
          <span
            title="Ausência observada uma única vez. Só vira saída quando o mês seguinte confirmar."
            className="ml-1 rounded border border-orange-500 bg-orange-100 px-1 text-[9px] text-orange-800"
          >
            provisória
          </span>
        )}
      </>
    ),
  },
  {
    chave: 'saida',
    titulo: 'Data de saída',
    // Ordena pela competência crua (`AAAAMM`), que é comparável como texto; a
    // tela é que a escreve por extenso.
    valor: (r) => r.MES_SAIDA,
    classe: 'whitespace-nowrap',
    celula: (r) => (r.MES_SAIDA ? formatarCompetenciaLonga(r.MES_SAIDA) : '-'),
    exportar: (r) => (r.MES_SAIDA ? formatarCompetenciaLonga(r.MES_SAIDA) : ''),
  },
  {
    chave: 'selo_saida',
    titulo: 'Selo da saída',
    // Quem atesta que a pessoa SAIU — e nada mais. Quem está na CGU não tem saída
    // para sustentar, e por isso fica vazio: um `SIAPE` aqui diria que existe uma
    // saída atestada pelo cadastro onde não existe saída nenhuma.
    valor: (r) => (saiuDaCgu(r) ? fontesDaSaida(r).join(' + ') : ''),
    celula: (r) => (saiuDaCgu(r) ? <SelosDaLinha fontes={fontesDaSaida(r)} compacto tema="claro" /> : '-'),
  },
  {
    chave: 'ato_saida',
    titulo: 'Ato da saída',
    // Ordena pela data ISO, que é comparável como texto — a tela mostra a data no
    // formato brasileiro, que não é.
    valor: (r) => r.DATA_PUBLICACAO_SAIDA,
    celula: (r) => {
      const ato = urlDoAto(r);
      return ato ? (
        <a
          href={ato}
          target="_blank"
          rel="noopener noreferrer"
          title={r.ATO_SAIDA_TITULO}
          className="text-blue-700 underline hover:text-blue-900"
        >
          {formatarDataIsoParaBr(r.DATA_PUBLICACAO_SAIDA) || 'ver ato'}
        </a>
      ) : (
        '-'
      );
    },
    // No CSV vai o ENDEREÇO, não a data: a data se lê na coluna "Data de saída",
    // e o link é a única coisa da tabela que não dá para reconstruir de fora.
    //
    // ABSOLUTO, e não o que a tela usa. `urlDoAto` prefere a cópia arquivada em
    // `data/saidas_dou/`, e a devolve como caminho RELATIVO — o que na página
    // resolve sozinho e, numa planilha aberta fora do navegador, não leva a lugar
    // nenhum. `new URL(..., location.href)` completa o relativo e deixa o
    // absoluto (o `in.gov.br` de quem não tem cópia local) como está.
    exportar: (r) => {
      const ato = urlDoAto(r);
      return ato ? new URL(ato, location.href).href : '';
    },
  },
  {
    chave: 'destino',
    titulo: 'Órgão de destino',
    // O destino tem procedência PRÓPRIA, e ela não é a da saída: os selos da
    // esquerda atestam que a pessoa saiu, não para onde foi. Enquanto o destino só
    // vinha do DOU dava para deduzir; desde a D24 ele pode vir do Ranking dos
    // Concursos, que é indício e não ato — e é por isso que o selo dele tem coluna
    // própria, em vez de ficar colado ao nome do órgão.
    valor: (r) => r.ORGAO_DESTINO,
    classe: 'whitespace-nowrap',
  },
  {
    chave: 'selo_destino',
    titulo: 'Selo do destino',
    valor: (r) => (r.ORGAO_DESTINO && r.FONTE_DESTINO ? r.FONTE_DESTINO : ''),
    celula: (r) =>
      r.ORGAO_DESTINO && r.FONTE_DESTINO ? <SeloFonte fonte={r.FONTE_DESTINO} compacto tema="claro" /> : '-',
  },
  {
    chave: 'ato_destino',
    titulo: 'Ato do destino',
    // Nem todo destino tem ATO: o do ranking é a ficha de aprovações da pessoa,
    // uma consulta que qualquer um repete no navegador. O rótulo sai de
    // `Selos.tsx`, para que a tabela não chame de "ato" o que não é.
    valor: (r) => (r.ORGAO_DESTINO && r.URL_DESTINO ? r.DATA_DESTINO : ''),
    celula: (r) =>
      r.ORGAO_DESTINO && r.URL_DESTINO ? (
        <a
          href={r.URL_DESTINO}
          target="_blank"
          rel="noopener noreferrer"
          title={tituloDoLinkDeDestino(r.FONTE_DESTINO, r.NOME, r.ORGAO_DESTINO)}
          className="text-blue-700 underline hover:text-blue-900"
        >
          {rotuloDoLinkDeDestino(r.FONTE_DESTINO, r.DATA_DESTINO)}
        </a>
      ) : (
        '-'
      ),
    // Aqui o endereço já é absoluto: é do órgão de chegada ou do ranking, e não
    // deste site.
    exportar: (r) => (r.ORGAO_DESTINO ? r.URL_DESTINO : ''),
  },
];

/**
 * O byte-order mark que abre o CSV exportado.
 *
 * Vai por código, e não como o caractere em si: ele não tem desenho nenhum, e um
 * caractere invisível no meio de uma string é o tipo de coisa que o próximo
 * editor apaga sem perceber — e aí o acento quebra só para quem abrir no Excel.
 */
const MARCA_DE_ORDEM = String.fromCharCode(0xfeff);

type Direcao = 'asc' | 'desc';

/**
 * Comparador de uma coluna.
 *
 * Vazio vai SEMPRE para o fim, nos dois sentidos. Ele não é "o menor valor": é
 * ausência de valor, e inverter a ordem só para chegar à primeira linha
 * preenchida seria gastar dois cliques com o que a coluna nem tem.
 */
const compararPor = (coluna: Coluna, direcao: Direcao) => (a: RegistroAuditor, b: RegistroAuditor) => {
  const valorA = coluna.valor(a);
  const valorB = coluna.valor(b);
  if (!valorA && !valorB) return 0;
  if (!valorA) return 1;
  if (!valorB) return -1;
  const sinal = direcao === 'asc' ? 1 : -1;
  if (coluna.numerica) return sinal * (Number(valorA) - Number(valorB));
  return sinal * valorA.localeCompare(valorB, 'pt-BR');
};

const DetailedTableApp: React.FC = () => {
  const [registros, setRegistros] = useState<RegistroAuditor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [busca, setBusca] = useState('');
  const [concurso, setConcurso] = useState<string>(TODOS);
  const [area, setArea] = useState<string>(TODOS);
  const [unidade, setUnidade] = useState<string>(TODOS);
  const [motivo, setMotivo] = useState<string>(TODOS);
  const [situacao, setSituacao] = useState<string>(TODOS);
  const [limite, setLimite] = useState(PAGINA);
  /** `null` é a ordem padrão da página — quem saiu por último no topo. */
  const [ordem, setOrdem] = useState<{ chave: string; direcao: Direcao } | null>(null);

  useEffect(() => {
    let montado = true;
    (async () => {
      try {
        // Um arquivo só, e já pronto (D29): o `painel.csv` é o `dados.csv` com as
        // saídas que só o DOU conhece sobrepostas (D22) e os destinos do ranking
        // preenchidos (D24). Sem aquela sobreposição, quem saiu em agosto
        // apareceria aqui trabalhando — mas quem a faz é o Python, na publicação,
        // e não esta página.
        const linhas = await carregarCsv('painel.csv');
        if (montado) setRegistros(comoRegistros(linhas));
      } catch (falha) {
        if (montado) setErro(falha instanceof Error ? falha.message : 'Erro ao carregar painel.csv.');
      } finally {
        if (montado) setCarregando(false);
      }
    })();
    return () => {
      montado = false;
    };
  }, []);

  // As opções vêm do dado, não de uma lista fixa: assim uma unidade nova aparece
  // no filtro sozinha, e uma que sumiu não fica de opção morta.
  const areas = useMemo(() => {
    const encontradas = new Set(registros.map(areaDe));
    const especialidades = Array.from(encontradas)
      .filter((valor) => !AREAS_SEM_ESPECIALIDADE.includes(valor))
      .sort((a, b) => a.localeCompare(b, 'pt-BR'));
    // "Veterano" e "Sem área identificada" no fim: não são especialidade, e
    // misturá-las na ordem alfabética as faria parecer uma.
    return [...especialidades, ...AREAS_SEM_ESPECIALIDADE.filter((valor) => encontradas.has(valor))];
  }, [registros]);

  const unidades = useMemo(
    () => Array.from(new Set(registros.map((registro) => registro.UNIDADE).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [registros]
  );

  const situacoes = useMemo(
    () => Array.from(new Set(registros.map((registro) => registro.SITUACAO).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [registros]
  );

  // `motivoDetalhado`, e não `motivoDe`: esta é a única página que nomeia o
  // motivo da D18, e o filtro tem de casar com o valor cru da coluna.
  const motivos = useMemo(() => {
    const encontrados = new Set(registros.filter(saiuDaCgu).map(motivoDetalhado));
    return MOTIVOS_SAIDA_DETALHADOS.filter((valor) => encontrados.has(valor));
  }, [registros]);

  const filtrados = useMemo(() => {
    const termo = normalizar(busca);
    return registros
      .filter((registro) => {
        if (concurso && registro.CONCURSO !== concurso) return false;
        if (area && areaDe(registro) !== area) return false;
        if (unidade && registro.UNIDADE !== unidade) return false;
        if (situacao && registro.SITUACAO !== situacao) return false;
        if (motivo && (!saiuDaCgu(registro) || motivoDetalhado(registro) !== motivo)) return false;
        if (termo && !normalizar(registro.NOME).includes(termo)) return false;
        return true;
      })
      .sort((a, b) => {
        // Quem saiu primeiro, do mais recente para o mais antigo — é o que a
        // página serve para consultar. Quem está na CGU vem depois, por
        // classificação do concurso e, na falta dela, por nome.
        if (a.MES_SAIDA !== b.MES_SAIDA) {
          if (!a.MES_SAIDA) return 1;
          if (!b.MES_SAIDA) return -1;
          return b.MES_SAIDA.localeCompare(a.MES_SAIDA);
        }
        const posicaoA = Number(a.POSICAO_CONCURSO) || Number.MAX_SAFE_INTEGER;
        const posicaoB = Number(b.POSICAO_CONCURSO) || Number.MAX_SAFE_INTEGER;
        return posicaoA - posicaoB || a.NOME.localeCompare(b.NOME, 'pt-BR');
      });
  }, [registros, busca, concurso, area, unidade, situacao, motivo]);

  /**
   * O recorte na ordem escolhida.
   *
   * Ordena o RECORTE INTEIRO, e não as linhas à vista: a tabela renderiza 300 por
   * vez, e ordenar depois de cortar só reorganizaria a primeira página — quem
   * clicasse em "Class." veria o primeiro colocado das 300, não do recorte.
   *
   * O `sort` do JavaScript é estável, então o desempate herda a ordem padrão:
   * ordenar por Unidade agrupa por unidade e, dentro de cada uma, mantém quem
   * saiu por último no topo.
   */
  const ordenados = useMemo(() => {
    if (!ordem) return filtrados;
    const coluna = COLUNAS.find((c) => c.chave === ordem.chave);
    if (!coluna) return filtrados;
    return [...filtrados].sort(compararPor(coluna, ordem.direcao));
  }, [filtrados, ordem]);

  useEffect(() => setLimite(PAGINA), [busca, concurso, area, unidade, situacao, motivo]);

  const visiveis = ordenados.slice(0, limite);
  // Saída atestada pelas DUAS fontes: o cadastro mostra a ausência e existe ato
  // publicado dizendo por quê. É o número que responde "quanto disto está
  // documentado em dobro" — que era o que o antigo "conferido" tentava dizer, e
  // dizia mal, porque media conferência humana, que quase nunca acontece.
  const comDuasFontes = filtrados.filter(
    (registro) => saiuDaCgu(registro) && registro.FONTE_MOTIVO
  ).length;

  /** Primeiro clique ordena crescente; o segundo inverte; o terceiro devolve a ordem padrão. */
  const alternarOrdem = (chave: string) =>
    setOrdem((atual) => {
      if (atual?.chave !== chave) return { chave, direcao: 'asc' };
      return atual.direcao === 'asc' ? { chave, direcao: 'desc' } : null;
    });

  /**
   * Baixa o recorte inteiro em CSV.
   *
   * Sai `ordenados`, e não `visiveis`: o arquivo tem de ser o recorte que os
   * filtros descrevem, e não o pedaço que o botão "Mostrar mais" já carregou.
   *
   * Separador `;` e BOM no começo por causa do Excel em português: com vírgula
   * ele joga a linha toda numa célula, e sem o BOM lê o arquivo como Latin-1 e
   * escreve "VACÂNCIA" errado. O Google Sheets detecta os dois sozinho.
   */
  const baixarCsv = () => {
    const escapar = (valor: string) => `"${String(valor ?? '').replaceAll('"', '""')}"`;
    const linhas = [
      COLUNAS.map((coluna) => escapar(coluna.titulo)).join(';'),
      ...ordenados.map((registro) =>
        COLUNAS.map((coluna) => escapar((coluna.exportar ?? coluna.valor)(registro))).join(';')
      ),
    ];
    const blob = new Blob([MARCA_DE_ORDEM + linhas.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    const endereco = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = endereco;
    link.download = `auditores-cgu-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(endereco);
  };

  const seletor = (
    rotulo: string,
    valor: string,
    aoMudar: (novo: string) => void,
    opcoes: readonly string[],
    rotuloDeTodos: string,
    formatar: (opcao: string) => string = (opcao) => opcao
  ) => (
    <label className="flex flex-col text-[11px] font-medium text-gray-700">
      {rotulo}
      <select
        value={valor}
        onChange={(evento) => aoMudar(evento.target.value)}
        className="mt-0.5 rounded border border-gray-300 bg-white px-2 py-1 text-xs focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
      >
        <option value={TODOS}>{rotuloDeTodos}</option>
        {opcoes.map((opcao) => (
          <option key={opcao} value={opcao}>
            {formatar(opcao)}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="min-h-screen bg-gray-50 p-2 text-gray-900">
      <div className="w-full max-w-none">
        <div className="mb-2">
          <a
            href="./index.html"
            className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors duration-200 hover:bg-gray-100 hover:text-gray-900"
          >
            ← Voltar ao dashboard
          </a>
        </div>

        <header className="mb-3 text-center">
          <span className="text-sm font-medium text-red-600">
            Auditores Federais de Finanças e Controle &mdash; CGU
          </span>
        </header>

        <div className="mb-3 flex flex-wrap items-end justify-center gap-3">
          <label className="flex flex-col text-[11px] font-medium text-gray-700">
            Buscar por nome
            <input
              type="search"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
              placeholder="Digite o nome..."
              className="mt-0.5 w-64 rounded border border-gray-300 bg-white px-2 py-1 text-xs focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
            />
          </label>

          {seletor('Concurso', concurso, setConcurso, [ID_CONCURSO_2021, ID_CONCURSO_VETERANO], 'Todos', rotuloDoConcurso)}
          {seletor('Especialidade', area, setArea, areas, 'Todas')}
          {seletor('Unidade', unidade, setUnidade, unidades, 'Todas')}
          {seletor('Situação', situacao, setSituacao, situacoes, 'Todas')}
          {seletor('Motivo da saída', motivo, setMotivo, motivos, 'Todos')}

          {/* O número no rótulo é o do recorte inteiro, e não o das linhas à
              vista: é o que o arquivo vai conter, e dizê-lo aqui evita a dúvida
              de quem ainda não clicou em "Mostrar mais". */}
          <button
            type="button"
            onClick={baixarCsv}
            disabled={ordenados.length === 0}
            className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Baixar este recorte em CSV ({ordenados.length.toLocaleString('pt-BR')})
          </button>
        </div>

        {!carregando && !erro && (
          <div className="mb-2 text-center text-xs text-gray-600">
            {filtrados.length.toLocaleString('pt-BR')} Auditor(es) neste recorte ·{' '}
            {filtrados.filter(saiuDaCgu).length.toLocaleString('pt-BR')} já saíram ·{' '}
            {comDuasFontes.toLocaleString('pt-BR')} com saída atestada pelo SIAPE e pelo DOU
            {visiveis.length < ordenados.length && ` · mostrando ${visiveis.length.toLocaleString('pt-BR')}`}
          </div>
        )}

        <div className="border border-black bg-white shadow-lg">
          <div className="max-h-[80vh] overflow-x-auto overflow-y-auto">
            <table className="w-full border-collapse border border-black text-[10px]">
              <thead className="sticky top-0 z-50 bg-white text-[10px] uppercase text-gray-700 shadow-sm">
                <tr>
                  {/* Os títulos saem de `COLUNAS` — ver a nota lá sobre a ordem
                      das quatro últimas. */}
                  {COLUNAS.map((coluna) => {
                    const ativa = ordem?.chave === coluna.chave;
                    return (
                      <th
                        key={coluna.chave}
                        scope="col"
                        aria-sort={ativa ? (ordem.direcao === 'asc' ? 'ascending' : 'descending') : 'none'}
                        className="border border-black bg-white p-0 text-center font-semibold"
                      >
                        <button
                          type="button"
                          onClick={() => alternarOrdem(coluna.chave)}
                          title={
                            ativa && ordem.direcao === 'desc'
                              ? 'Voltar à ordem padrão (saída mais recente primeiro)'
                              : `Ordenar por ${coluna.titulo}`
                          }
                          className="flex w-full items-center justify-center gap-1 px-1 py-1 uppercase hover:bg-gray-100 focus:outline-none focus:ring-1 focus:ring-inset focus:ring-red-400"
                        >
                          {coluna.titulo}
                          <span aria-hidden="true" className={ativa ? 'text-red-600' : 'text-gray-300'}>
                            {ativa ? (ordem.direcao === 'asc' ? '▲' : '▼') : '↕'}
                          </span>
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-black">
                {carregando && (
                  <tr>
                    <td colSpan={COLUNAS.length} className="border border-black px-4 py-6 text-center text-orange-600">
                      Carregando dados...
                    </td>
                  </tr>
                )}
                {erro && (
                  <tr>
                    <td colSpan={COLUNAS.length} className="border border-black px-4 py-6 text-center text-red-700">
                      {erro}
                    </td>
                  </tr>
                )}
                {!carregando && !erro && visiveis.length === 0 && (
                  <tr>
                    <td colSpan={COLUNAS.length} className="border border-black px-4 py-6 text-center text-gray-500">
                      Nenhum Auditor encontrado com estes filtros.
                    </td>
                  </tr>
                )}
                {visiveis.map((registro) => (
                  <tr
                    key={registro.ID_SERVIDOR_PORTAL}
                    className={`${CORES_POR_SITUACAO[registro.SITUACAO] ?? 'bg-white'} transition-all duration-150 hover:brightness-95`}
                  >
                    {COLUNAS.map((coluna) => (
                      <Celula
                        key={coluna.chave}
                        alinhamento={coluna.alinhamento}
                        className={coluna.classe}
                        titulo={coluna.titulo_da_celula?.(registro)}
                      >
                        {coluna.celula ? coluna.celula(registro) : coluna.valor(registro) || '-'}
                      </Celula>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {visiveis.length < ordenados.length && (
          <div className="mt-3 text-center">
            <button
              type="button"
              onClick={() => setLimite((atual) => atual + PAGINA)}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-100"
            >
              Mostrar mais {Math.min(PAGINA, ordenados.length - visiveis.length)} de{' '}
              {(ordenados.length - visiveis.length).toLocaleString('pt-BR')} restantes
            </button>
          </div>
        )}

        <p className="mt-4 text-center text-xs text-gray-500">
          Clicar no título de uma coluna ordena o recorte inteiro, e não só as linhas já carregadas; clicar de novo
          inverte, e a terceira vez devolve a ordem padrão. A especialidade vem do Edital CGU nº 5, de 13/06/2022,
          publicado no DOU; veteranos não têm edital de onde tirá-la. A situação resume o motivo da saída, como o ato
          do DOU o diz — passe o cursor sobre ela para ler o motivo por extenso.
        </p>
        <p className="mx-auto mt-2 max-w-4xl text-center text-xs text-gray-500">
          <span className="font-medium">Que a pessoa saiu</span> e{' '}
          <span className="font-medium">para onde ela foi</span> são duas afirmações, e cada uma tem o seu selo e o seu
          documento. O selo da saída é <span className="font-medium">SIAPE</span> quando o cadastro mostra a pessoa
          presente num mês e ausente no seguinte, e <span className="font-medium">DOU</span> quando existe ato
          publicado; os dois juntos são duas fontes independentes dizendo o mesmo, e um sozinho diz exatamente o que se
          sabe até agora. O selo do destino é <span className="font-medium">DOU</span> quando existe ato de nomeação no
          órgão de chegada, e <span className="font-medium">Ranking</span> quando o destino foi deduzido da única
          aprovação em concurso que a pessoa tinha — aí o link abre a ficha de aprovações, e não um ato: é indício com
          fonte, não fato publicado.
        </p>

        <footer className="mt-8 text-center text-sm text-gray-500">
          <p>
            &copy; {new Date().getFullYear()} Observatório das Evasões. Dados do Portal da Transparência e do Diário
            Oficial da União (DOU).
          </p>
        </footer>
      </div>
    </div>
  );
};

export default DetailedTableApp;
