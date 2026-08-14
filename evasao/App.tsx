import React, { useEffect, useMemo, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faArrowTrendDown,
  faCalendarAlt,
  faUserMinus,
  faUsers,
} from '@fortawesome/free-solid-svg-icons';

import AnnouncementModal from './components/AnnouncementModal';
import CollaborationForm from './components/CollaborationForm';
import CounterCard from './components/CounterCard';
import EvasionChart, { SerieGrafico } from './components/EvasionChart';
import EvasionTable from './components/EvasionTable';
import { SelosDaLinha } from './components/Selos';

import {
  AREA_DESCONHECIDA,
  COR_POR_CONCURSO,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  rotuloDoConcurso,
} from './constants';
import { PontoSerieMensal, RegistroAuditor, SaidasDou } from './types';
import {
  baseDoSite,
  carregarCsv,
  carregarJsonPublico,
  diasDesde,
  formatarCompetencia,
  formatarCompetenciaLonga,
  formatarDataIsoParaBr,
} from './lib/dados';
import {
  agregarPorDestino,
  agregarPorMotivo,
  agregarPorUf,
  agregarPorUnidade,
  areaDe,
  comoRegistros,
  comoSerie,
  curvaDePermanencia,
  detalharSaida,
  evasaoDaCoorte,
  saidas,
} from './lib/painel';

const TODAS = 'TODAS';

const TIPOS_SAIDA_DOU: Array<{ tipo: SaidasDou['eventos'][number]['tipo']; rotuloCurto: string }> = [
  { tipo: 'vacancia', rotuloCurto: 'Vacância' },
  { tipo: 'aposentadoria', rotuloCurto: 'Aposentadoria' },
  { tipo: 'exoneracao', rotuloCurto: 'Exoneração' },
];

const numero = (valor: number) => valor.toLocaleString('pt-BR');
const percentual = (valor: number) => `${valor.toFixed(1).replace('.', ',')}%`;

const App: React.FC = () => {
  const [registros, setRegistros] = useState<RegistroAuditor[]>([]);
  const [serie, setSerie] = useState<PontoSerieMensal[]>([]);
  const [saidasDou, setSaidasDou] = useState<SaidasDou | null>(null);

  const [erroDados, setErroDados] = useState<string | null>(null);
  const [erroSaidasDou, setErroSaidasDou] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const [coorteSelecionada, setCoorteSelecionada] = useState<string>(TODAS);
  const [areaSelecionada, setAreaSelecionada] = useState<string>(TODAS);
  const [corteGeografico, setCorteGeografico] = useState<'unidade' | 'uf'>('unidade');

  // Dado do painel: uma pessoa por linha e uma competência por linha. Os dois
  // arquivos são derivados dos snapshots do SIAPE (D11/D16); a interface só lê.
  useEffect(() => {
    let montado = true;

    (async () => {
      try {
        const [linhasDados, linhasSerie] = await Promise.all([
          carregarCsv('dados.csv'),
          carregarCsv('serie_mensal.csv'),
        ]);
        if (!montado) return;
        setRegistros(comoRegistros(linhasDados));
        setSerie(comoSerie(linhasSerie));
        setErroDados(null);
      } catch (erro) {
        if (montado) setErroDados(erro instanceof Error ? erro.message : 'Erro ao carregar os dados.');
      } finally {
        if (montado) setCarregando(false);
      }
    })();

    return () => {
      montado = false;
    };
  }, []);

  // Saídas de AFFC no DOU — alimenta o card "dias sem perder um Auditor" (D10).
  // Vem de um crawler próprio, por frase, e não do dados.csv: é o único número
  // da tela que precisa estar certo no dia, não no mês.
  useEffect(() => {
    let montado = true;

    (async () => {
      try {
        const dados = await carregarJsonPublico<SaidasDou>('dias_sem_perder_affc.json');
        if (!montado) return;
        if (!dados?.dataMaisRecente) throw new Error('JSON sem data mais recente.');
        setSaidasDou(dados);
        setErroSaidasDou(null);
      } catch {
        if (montado) setErroSaidasDou('Não foi possível carregar as saídas do DOU.');
      }
    })();

    return () => {
      montado = false;
    };
  }, []);

  // === Recortes ===

  const areasDisponiveis = useMemo(() => {
    const encontradas = new Set(registros.map(areaDe));
    // "Sem área identificada" vai sempre por último: é ausência de dado, não uma área.
    const comArea = Array.from(encontradas).filter((area) => area !== AREA_DESCONHECIDA).sort((a, b) => a.localeCompare(b, 'pt-BR'));
    return encontradas.has(AREA_DESCONHECIDA) ? [...comArea, AREA_DESCONHECIDA] : comArea;
  }, [registros]);

  const filtrados = useMemo(
    () =>
      registros.filter(
        (registro) =>
          (coorteSelecionada === TODAS || registro.CONCURSO === coorteSelecionada) &&
          (areaSelecionada === TODAS || areaDe(registro) === areaSelecionada)
      ),
    [registros, coorteSelecionada, areaSelecionada]
  );

  // === Cards ===

  const totalSaidas = useMemo(() => saidas(registros).length, [registros]);
  const motivosDoTotal = useMemo(() => agregarPorMotivo(registros), [registros]);
  const coorte2021 = useMemo(() => evasaoDaCoorte(registros, ID_CONCURSO_2021), [registros]);
  const coorteVeterana = useMemo(() => evasaoDaCoorte(registros, ID_CONCURSO_VETERANO), [registros]);

  const primeiroMes = serie[0];
  const ultimoMes = serie[serie.length - 1];

  const diasSemPerderAuditor = saidasDou ? diasDesde(saidasDou.dataMaisRecente) : null;
  const eventosDouPorTipo = useMemo(
    () => new Map((saidasDou?.eventos ?? []).map((evento) => [evento.tipo, evento])),
    [saidasDou]
  );
  const eventoMaisRecente = saidasDou
    ? (saidasDou.eventos ?? []).find((evento) => evento.dataPublicacao === saidasDou.dataMaisRecente)
    : undefined;

  // === Gráfico 1: efetivo mensal, entradas e saídas ===

  const graficoEfetivo = useMemo((): { rotulos: string[]; completos: string[]; series: SerieGrafico[] } => {
    const rotulos = serie.map((ponto) => formatarCompetencia(ponto.mes));
    const completos = serie.map((ponto) => formatarCompetenciaLonga(ponto.mes));
    return {
      rotulos,
      completos,
      series: [
        {
          rotulo: 'Auditores na CGU',
          cor: '#d4af37',
          tipo: 'linha',
          valores: serie.map((ponto) => ponto.efetivo),
        },
        {
          rotulo: 'Entradas',
          cor: '#22c55e',
          eixo: 'direita',
          valores: serie.map((ponto) => ponto.entradas),
        },
        {
          rotulo: 'Saídas',
          cor: '#dc2626',
          eixo: 'direita',
          valores: serie.map((ponto) => ponto.saidas),
        },
      ],
    };
  }, [serie]);

  // === Gráficos 2 e 3: saídas por motivo e por unidade/UF, quebradas por coorte ===

  /** Monta uma série por coorte sobre um agrupamento qualquer, com nomes no tooltip. */
  const seriesPorCoorte = (
    grupos: { rotulo: string; itens: RegistroAuditor[] }[]
  ): SerieGrafico[] =>
    [ID_CONCURSO_2021, ID_CONCURSO_VETERANO]
      .filter((id) => coorteSelecionada === TODAS || coorteSelecionada === id)
      .map((id) => ({
        rotulo: rotuloDoConcurso(id),
        cor: COR_POR_CONCURSO[id],
        valores: grupos.map((grupo) => grupo.itens.filter((registro) => registro.CONCURSO === id).length),
        detalhes: grupos.map((grupo) =>
          grupo.itens
            .filter((registro) => registro.CONCURSO === id)
            .map((registro) => `${registro.NOME} — ${formatarCompetenciaLonga(registro.MES_SAIDA)}`)
        ),
      }));

  const graficoMotivos = useMemo(() => {
    const grupos = agregarPorMotivo(filtrados);
    return {
      rotulos: grupos.map((grupo) => grupo.rotulo),
      series: seriesPorCoorte(grupos),
      vazio: grupos.length === 0,
    };
    // `seriesPorCoorte` depende de `coorteSelecionada`, já na lista.
  }, [filtrados, coorteSelecionada]);

  const graficoGeografico = useMemo(() => {
    const grupos = corteGeografico === 'unidade' ? agregarPorUnidade(filtrados) : agregarPorUf(filtrados);
    return {
      rotulos: grupos.map((grupo) => grupo.rotulo),
      series: seriesPorCoorte(grupos),
      vazio: grupos.length === 0,
    };
  }, [filtrados, corteGeografico, coorteSelecionada]);

  // === Gráfico 4: curva de permanência ===

  const graficoPermanencia = useMemo(() => {
    if (!ultimoMes) return { rotulos: [], series: [] as SerieGrafico[], vazio: true };

    // O filtro de coorte não se aplica: o gráfico existe justamente para pôr as
    // duas lado a lado. O de área se aplica, porque área é atributo da pessoa.
    const porArea = areaSelecionada === TODAS
      ? registros
      : registros.filter((registro) => areaDe(registro) === areaSelecionada);

    const curvas = [ID_CONCURSO_2021, ID_CONCURSO_VETERANO].map((id) => ({
      id,
      pontos: curvaDePermanencia(porArea, id, ultimoMes.mes),
    }));

    const comprimento = Math.max(0, ...curvas.map((curva) => curva.pontos.length));
    if (comprimento === 0) return { rotulos: [], series: [] as SerieGrafico[], vazio: true };

    return {
      rotulos: Array.from({ length: comprimento }, (_, indice) => String(indice)),
      series: curvas
        .filter((curva) => curva.pontos.length > 0)
        .map((curva) => ({
          rotulo: rotuloDoConcurso(curva.id),
          cor: COR_POR_CONCURSO[curva.id],
          tipo: 'linha' as const,
          sufixo: '%',
          valores: Array.from({ length: comprimento }, (_, indice) => curva.pontos[indice]?.percentual ?? null),
          detalhes: Array.from({ length: comprimento }, (_, indice) => {
            const ponto = curva.pontos[indice];
            return ponto ? [`${numero(ponto.restantes)} de ${numero(ponto.base)} ainda na CGU`] : [];
          }),
        })),
      vazio: false,
    };
  }, [registros, areaSelecionada, ultimoMes]);

  // === Tabela de destinos e últimas saídas ===

  const gruposDeDestino = useMemo(
    () =>
      agregarPorDestino(filtrados).map((grupo) => ({
        rotulo: grupo.rotulo,
        total: grupo.total,
        itens: grupo.itens
          .map(detalharSaida)
          .sort((a, b) => b.mesSaida.localeCompare(a.mesSaida) || a.nome.localeCompare(b.nome, 'pt-BR')),
      })),
    [filtrados]
  );

  const ultimasSaidas = useMemo(
    () =>
      saidas(registros)
        .map(detalharSaida)
        .sort((a, b) => b.mesSaida.localeCompare(a.mesSaida) || a.nome.localeCompare(b.nome, 'pt-BR'))
        .slice(0, 6),
    [registros]
  );

  const base = baseDoSite();

  const icone = (definicao: typeof faCalendarAlt) => (
    <FontAwesomeIcon icon={definicao} className="h-10 w-10 text-red-400 md:h-12 md:w-12" />
  );

  const botaoFiltro = (ativo: boolean) =>
    `px-3 py-1 rounded text-sm font-medium focus:outline-none focus:ring-2 focus:ring-red-400 ${
      ativo ? 'bg-red-500 text-white shadow-lg' : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700'
    }`;

  return (
    <div className="min-h-screen bg-gray-950 p-4 text-gray-200 sm:p-6 lg:p-8">
      <AnnouncementModal />
      <div className="mx-auto max-w-5xl">
        <header className="mb-10">
          <div className="mb-4 text-center">
            <span className="inline-flex flex-col items-center gap-2 md:flex-row md:gap-3">
              <img
                src={`${base}assets/images/observatorio-cgu-logo-mini.png`}
                alt="Logo do Observatório"
                className="h-20 w-20 flex-shrink-0 md:h-24 md:w-24"
              />
              <h1
                className="min-w-0 whitespace-normal break-words text-center text-4xl font-extrabold drop-shadow-lg md:inline-block md:text-left md:text-5xl"
                style={{ color: '#E21111' }}
              >
                OBSERVATÓRIO DAS EVASÕES
              </h1>
            </span>
          </div>
          <p className="text-center text-lg font-medium text-amber-400">
            Auditores Federais de Finanças e Controle &mdash; CGU
          </p>
        </header>

        {erroDados && (
          <div className="mb-6 rounded-xl border border-red-700 bg-red-950/40 p-4 text-center text-red-300">
            <strong>Erro:</strong> {erroDados}
          </div>
        )}

        <main>
          <section className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            <CounterCard
              value={diasSemPerderAuditor ?? '—'}
              label={`Dia${(diasSemPerderAuditor ?? 0) === 1 ? '' : 's'} sem perder um Auditor`}
              icon={icone(faCalendarAlt)}
              footer={
                <div className="space-y-2">
                  {erroSaidasDou ? (
                    <div className="text-gray-500">{erroSaidasDou}</div>
                  ) : (
                    <>
                      <div>Por data de publicação no Diário Oficial da União.</div>
                      {eventoMaisRecente && (
                        <div>
                          Última saída: <b>{eventoMaisRecente.rotulo}</b> em{' '}
                          <b>{formatarDataIsoParaBr(eventoMaisRecente.dataPublicacao)}</b>
                        </div>
                      )}
                      <div className="flex flex-wrap justify-center gap-2 pt-1">
                        {TIPOS_SAIDA_DOU.map(({ tipo, rotuloCurto }) => {
                          const evento = eventosDouPorTipo.get(tipo);
                          if (!evento) {
                            return (
                              <span
                                key={tipo}
                                className="rounded border border-gray-800 px-2 py-1 text-gray-600"
                                title="Nenhum ato deste tipo encontrado nos últimos 12 meses"
                              >
                                {rotuloCurto}: —
                              </span>
                            );
                          }
                          const href = evento.arquivo
                            ? `${base}data/dias_sem_perder_AFFC/${evento.arquivo}`
                            : evento.urlDou;
                          return (
                            <a
                              key={tipo}
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={evento.titulo}
                              className="rounded border border-amber-500/40 px-2 py-1 text-amber-400 transition-colors hover:border-amber-400 hover:bg-amber-500/10"
                            >
                              {rotuloCurto}: {formatarDataIsoParaBr(evento.dataPublicacao)}
                            </a>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              }
              estaCarregando={!saidasDou && !erroSaidasDou}
            />

            <CounterCard
              value={numero(totalSaidas)}
              label="Auditores que saíram da CGU"
              icon={icone(faUserMinus)}
              footer={
                <div className="space-y-2">
                  <div>Desde {primeiroMes ? formatarCompetenciaLonga(primeiroMes.mes) : 'o início da série'}.</div>
                  <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 border-t border-gray-700 pt-2">
                    {motivosDoTotal.map((grupo) => (
                      <span key={grupo.rotulo} className="text-xs text-gray-400">
                        {grupo.rotulo}: <span className="font-medium text-amber-400">{grupo.total}</span>
                      </span>
                    ))}
                  </div>
                </div>
              }
              estaCarregando={carregando}
            />

            <CounterCard
              value={percentual(coorte2021.percentual)}
              label="Evasão de quem entrou depois de jun/2022"
              icon={icone(faArrowTrendDown)}
              footer={
                <div className="space-y-1">
                  <div>
                    <span className="font-medium text-amber-400">{numero(coorte2021.saiu)}</span> de{' '}
                    {numero(coorte2021.total)} da coorte {rotuloDoConcurso(ID_CONCURSO_2021)}.
                  </div>
                  <div className="border-t border-gray-700 pt-1">
                    Entre os veteranos, {percentual(coorteVeterana.percentual)} ({numero(coorteVeterana.saiu)} de{' '}
                    {numero(coorteVeterana.total)}).
                  </div>
                </div>
              }
              estaCarregando={carregando}
            />

            <CounterCard
              value={ultimoMes ? numero(ultimoMes.efetivo) : '—'}
              label="Auditores na CGU hoje"
              icon={icone(faUsers)}
              footer={
                <div className="space-y-1">
                  {primeiroMes && ultimoMes && (
                    <div>
                      Eram <span className="font-medium text-amber-400">{numero(primeiroMes.efetivo)}</span> em{' '}
                      {formatarCompetenciaLonga(primeiroMes.mes)}.
                    </div>
                  )}
                  {ultimoMes && (
                    <div className="border-t border-gray-700 pt-1">
                      {numero(ultimoMes.cedidos)} cedidos a outros órgãos · competência{' '}
                      {formatarCompetenciaLonga(ultimoMes.mes)}
                    </div>
                  )}
                </div>
              }
              estaCarregando={carregando}
            />
          </section>

          <section className="mb-8">
            <h2 className="mb-1 text-lg font-semibold text-red-300">Efetivo, entradas e saídas mês a mês</h2>
            <p className="mb-3 text-sm text-gray-400">
              A linha é quantos Auditores a CGU tinha em cada competência; as barras, quantos entraram e saíram no mês.
              Este gráfico é do quadro inteiro e não responde aos filtros abaixo. A soma das barras vermelhas é maior
              que os {numero(totalSaidas)} do card porque um punhado de pessoas some do cadastro por alguns meses e
              volta: cada sumiço aparece aqui como movimentação do mês, mas só quem nunca voltou conta como saída.
            </p>
            {serie.length > 0 ? (
              <EvasionChart
                rotulos={graficoEfetivo.rotulos}
                rotulosCompletos={graficoEfetivo.completos}
                series={graficoEfetivo.series}
                altura={300}
                eixoEsquerdaComZero={false}
                tituloEixoEsquerda="Efetivo"
                tituloEixoDireita="Movimentações"
                maximoRotulosX={13}
              />
            ) : (
              <div className="rounded border border-gray-800 bg-gray-900/50 p-8 text-center text-gray-500">
                {carregando ? 'Carregando a série mensal...' : 'Série mensal indisponível.'}
              </div>
            )}
          </section>

          <section className="mb-6 flex flex-col items-center gap-4">
            <div className="flex flex-col items-center">
              <div className="mb-2 text-sm text-gray-300">Filtrar por coorte:</div>
              <div className="flex flex-wrap justify-center gap-2">
                {[TODAS, ID_CONCURSO_2021, ID_CONCURSO_VETERANO].map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setCoorteSelecionada(id)}
                    aria-pressed={coorteSelecionada === id}
                    className={botaoFiltro(coorteSelecionada === id)}
                  >
                    {id === TODAS ? 'Todas' : rotuloDoConcurso(id)}
                  </button>
                ))}
              </div>
            </div>

            {areasDisponiveis.length > 0 && (
              <div className="flex flex-col items-center">
                <div className="mb-2 text-sm text-gray-300">Filtrar por especialidade:</div>
                <div className="flex flex-wrap justify-center gap-2">
                  {[TODAS, ...areasDisponiveis].map((area) => (
                    <button
                      key={area}
                      type="button"
                      onClick={() => setAreaSelecionada(area)}
                      aria-pressed={areaSelecionada === area}
                      className={botaoFiltro(areaSelecionada === area)}
                    >
                      {area === TODAS ? 'Todas' : area}
                    </button>
                  ))}
                </div>
                <p className="mt-2 max-w-2xl text-center text-xs text-gray-500">
                  A especialidade vem do Edital CGU nº 5, de 13/06/2022, publicado no DOU. Veteranos não têm edital de
                  onde tirá-la, e por isso caem em &ldquo;{AREA_DESCONHECIDA}&rdquo;.
                </p>
              </div>
            )}
          </section>

          <section className="mb-8">
            <h2 className="mb-1 text-lg font-semibold text-red-300">Saídas por motivo</h2>
            <p className="mb-3 text-sm text-gray-400">
              O motivo vem do ato publicado no DOU, encontrado por busca de nome. &ldquo;Sem ato identificado&rdquo; é a
              pessoa que o SIAPE mostra saindo e cujo ato a busca não achou — é informação, não erro.
            </p>
            {!graficoMotivos.vazio ? (
              <EvasionChart rotulos={graficoMotivos.rotulos} series={graficoMotivos.series} altura={300} empilhar rotacionarRotulos />
            ) : (
              <div className="rounded border border-gray-800 bg-gray-900/50 p-8 text-center text-gray-500">
                {carregando ? 'Carregando...' : 'Nenhuma saída neste recorte.'}
              </div>
            )}
          </section>

          <section className="mb-8">
            <div className="mb-3 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-lg font-semibold text-red-300">
                  {corteGeografico === 'unidade' ? 'Saídas por unidade de lotação' : 'Saídas por UF'}
                </h2>
                <p className="mt-1 text-sm text-gray-400">
                  {corteGeografico === 'unidade'
                    ? 'As 12 unidades que mais perderam Auditores. A unidade é contada pelo código da UORG, não pelo nome.'
                    : 'UF da unidade de lotação. O traço agrupa sub-unidades cujo nome não permite deduzir o estado.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCorteGeografico(corteGeografico === 'unidade' ? 'uf' : 'unidade')}
                className="rounded bg-amber-500 px-4 py-2 font-bold text-black transition-colors hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-300"
              >
                {corteGeografico === 'unidade' ? 'Ver por UF' : 'Ver por unidade'}
              </button>
            </div>
            {!graficoGeografico.vazio ? (
              <EvasionChart
                rotulos={graficoGeografico.rotulos}
                series={graficoGeografico.series}
                altura={380}
                empilhar
                rotacionarRotulos
              />
            ) : (
              <div className="rounded border border-gray-800 bg-gray-900/50 p-8 text-center text-gray-500">
                {carregando ? 'Carregando...' : 'Nenhuma saída neste recorte.'}
              </div>
            )}
          </section>

          <section className="mb-8">
            <h2 className="mb-1 text-lg font-semibold text-red-300">Curva de permanência</h2>
            <p className="mb-3 text-sm text-gray-400">
              Que percentual de cada coorte ainda estava na CGU a cada mês desde a própria entrada. A curva para onde
              restam menos de 50 pessoas observadas — daí para a frente ela seria ruído, não tendência. O filtro de
              coorte não se aplica aqui: o gráfico existe para comparar as duas.
            </p>
            {!graficoPermanencia.vazio ? (
              <EvasionChart
                rotulos={graficoPermanencia.rotulos}
                series={graficoPermanencia.series}
                altura={300}
                eixoEsquerdaComZero={false}
                maximoEixoEsquerda={100}
                tituloEixoEsquerda="% ainda na CGU"
                maximoRotulosX={13}
              />
            ) : (
              <div className="rounded border border-gray-800 bg-gray-900/50 p-8 text-center text-gray-500">
                {carregando ? 'Carregando...' : 'Sem base suficiente para traçar a curva neste recorte.'}
              </div>
            )}
            <p className="mt-2 text-xs text-gray-500">
              Eixo horizontal: meses desde a entrada de cada pessoa, não datas do calendário.
            </p>
          </section>

          <section className="mb-8 rounded-xl border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-3 text-2xl font-bold text-amber-400">Últimas saídas registradas</h2>
            {ultimasSaidas.length === 0 ? (
              <div className="text-sm text-gray-400">{carregando ? 'Carregando...' : 'Nenhuma saída registrada.'}</div>
            ) : (
              <>
                <ul className="space-y-2 text-sm text-gray-200">
                  {ultimasSaidas.map((saida) => (
                    <li key={saida.id} className="flex flex-wrap items-baseline gap-2">
                      <span className="text-xs uppercase tracking-wider text-gray-400">
                        {formatarCompetenciaLonga(saida.mesSaida)}
                      </span>
                      <span className="text-amber-400">•</span>
                      <span>
                        <strong>{saida.nome}</strong> — {saida.motivo.toLocaleLowerCase('pt-BR')}
                        {saida.destino ? (
                          <>
                            , para <strong>{saida.destino}</strong>
                          </>
                        ) : null}
                        .
                      </span>
                      <SelosDaLinha
                        fonte={saida.destino ? saida.fonteDestino : saida.fonteMotivo}
                        verificado={saida.verificado}
                        compacto
                      />
                      {saida.atoUrl && (
                        <a
                          href={saida.atoUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={saida.atoTitulo}
                          className="text-xs text-amber-400 hover:text-amber-300"
                        >
                          ver ato
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="mt-3 text-sm">
                  <a href="./historico_alteracoes.html" className="text-amber-400 hover:text-amber-300">
                    Ver histórico completo
                  </a>
                </div>
              </>
            )}
          </section>

          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 shadow-2xl">
            <h2 className="mb-4 text-2xl font-bold text-red-300">Destinos da evasão</h2>
            <p className="mb-6 text-gray-400">
              Para onde foram os Auditores que deixaram a CGU. O destino só aparece quando há ato do DOU ou registro do
              SIAPE que o diga: cada linha traz de onde veio a informação e se alguém a conferiu. A CGU perdeu{' '}
              <span className="font-bold text-orange-400">{numero(totalSaidas)}</span> Auditores desde{' '}
              {primeiroMes ? formatarCompetenciaLonga(primeiroMes.mes) : 'o início da série'}.
            </p>
            <EvasionTable grupos={gruposDeDestino} />
          </section>
        </main>

        <div className="mb-6 mt-8 flex flex-col items-center justify-center gap-3 text-center sm:flex-row">
          <a
            href="./dados_detalhados.html"
            className="inline-flex items-center rounded-lg border border-transparent bg-red-600 px-6 py-3 text-base font-medium text-white shadow-sm transition-colors duration-200 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          >
            Ver dados detalhados →
          </a>
        </div>

        <div className="mt-8 space-y-2 text-sm text-gray-400">
          <p>
            A fonte primária é a diferença mês a mês do Cadastro de Servidores Civis (SIAPE), publicado no Portal da
            Transparência. Considera-se saída da CGU a ausência a partir da última presença na série — não o diff entre
            dois meses seguidos, que publicaria como saída quem apenas some do cadastro por um mês e volta.
          </p>
          <p>
            O motivo e o destino de cada saída vêm do ato correspondente no Diário Oficial da União, localizado por busca
            de nome. Onde a busca não encontrou ato, a tela diz isso; nada é preenchido por dedução.
          </p>
          <p>
            A quantidade de dias sem perder um Auditor considera a data de publicação no DOU, apurada por um crawler
            próprio — é o único número desta página que se move todo dia, e não todo mês.
          </p>
        </div>

        <CollaborationForm />

        <footer className="mt-6 text-center text-sm text-gray-500">
          <p>
            &copy; {new Date().getFullYear()} Observatório das Evasões. Dados do Portal da Transparência e do Diário
            Oficial da União (DOU).
          </p>
        </footer>
      </div>
    </div>
  );
};

export default App;
