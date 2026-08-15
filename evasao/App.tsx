import React, { useEffect, useMemo, useState } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import {
  faArrowTrendDown,
  faCalendarAlt,
  faUserMinus,
} from '@fortawesome/free-solid-svg-icons';

import AnnouncementModal from './components/AnnouncementModal';
import CollaborationForm from './components/CollaborationForm';
import CounterCard from './components/CounterCard';
import EvasionChart, { SerieGrafico } from './components/EvasionChart';
import EvasionTable from './components/EvasionTable';
import CardDeFiltros, { useFiltrosEncadeados } from './components/CardDeFiltros';
import { SelosDaLinha } from './components/Selos';

import {
  COR_POR_CONCURSO,
  COR_POR_MOTIVO,
  ID_CONCURSO_2021,
  MES_INICIO_GRAFICO_SAIDAS,
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
  listarCompetencias,
} from './lib/dados';
import {
  agregarPorDestino,
  agregarPorMotivoResumido,
  comoRegistros,
  comoSerie,
  curvaDePermanencia,
  detalharSaida,
  evasaoDaCoorte,
  filtrarSaidas,
  saidas,
  serieDeSaidasPorMotivo,
} from './lib/painel';

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
  // Vem do índice de atos do DOU, não do dados.csv: é o único número da tela que
  // precisa estar certo no dia, e não no mês. Por isso ele fica à frente da
  // lista de últimas saídas, que espera o SIAPE — `atosDepoisDaUltimaCompetencia`
  // diz de quanto é essa distância, e o card mostra.
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

  // === Recorte ===
  //
  // Os filtros valem para o gráfico de saídas mês a mês, e só para ele. A curva
  // de permanência, as últimas saídas e os destinos respondem por toda a série
  // — cada um explica isso no seu próprio texto.

  const todasAsSaidas = useMemo(() => saidas(registros), [registros]);

  const filtros = useFiltrosEncadeados(registros);
  const { coortes, areas, motivos } = filtros;

  const recorte = useMemo(() => ({ coortes, areas, motivos }), [coortes, areas, motivos]);
  const saidasFiltradas = useMemo(() => filtrarSaidas(registros, recorte), [registros, recorte]);

  // === Cards (acima dos filtros: são sempre o quadro inteiro) ===

  /** O card de saídas conta a partir de ago/2022, o mesmo corte do gráfico. */
  const motivosDoTotal = useMemo(
    () => agregarPorMotivoResumido(registros, MES_INICIO_GRAFICO_SAIDAS),
    [registros]
  );
  const saidasNoPeriodo = useMemo(
    () => motivosDoTotal.reduce((soma, grupo) => soma + grupo.total, 0),
    [motivosDoTotal]
  );
  const coorte2021 = useMemo(() => evasaoDaCoorte(registros, ID_CONCURSO_2021), [registros]);

  const ultimoMes = serie[serie.length - 1];

  const diasSemPerderAuditor = saidasDou ? diasDesde(saidasDou.dataMaisRecente) : null;
  const eventosDouPorTipo = useMemo(
    () => new Map((saidasDou?.eventos ?? []).map((evento) => [evento.tipo, evento])),
    [saidasDou]
  );
  const eventoMaisRecente = saidasDou
    ? (saidasDou.eventos ?? []).find((evento) => evento.dataPublicacao === saidasDou.dataMaisRecente)
    : undefined;

  // === Gráfico principal: saídas mês a mês ===

  const graficoSaidas = useMemo(() => {
    if (!ultimoMes) return { rotulos: [], completos: [], series: [] as SerieGrafico[], vazio: true };

    const meses = listarCompetencias(MES_INICIO_GRAFICO_SAIDAS, ultimoMes.mes);
    const series = serieDeSaidasPorMotivo(saidasFiltradas, meses, motivos)
      // Um motivo marcado mas sem nenhuma saída no recorte só polui a legenda.
      .filter((linha) => linha.valores.some((valor) => valor > 0))
      .map(
        (linha): SerieGrafico => ({
          rotulo: linha.motivo,
          cor: COR_POR_MOTIVO[linha.motivo] ?? '#6b7280',
          valores: linha.valores,
          detalhes: linha.nomes,
        })
      );

    return {
      rotulos: meses.map(formatarCompetencia),
      completos: meses.map(formatarCompetenciaLonga),
      series,
      vazio: series.length === 0,
    };
  }, [saidasFiltradas, motivos, ultimoMes]);

  /** Quantas saídas o gráfico realmente desenha — o corte em ago/2022 deixa de fora as anteriores. */
  const noGrafico = useMemo(
    () => saidasFiltradas.filter((registro) => registro.MES_SAIDA >= MES_INICIO_GRAFICO_SAIDAS).length,
    [saidasFiltradas]
  );
  const foraDoGrafico = saidasFiltradas.length - noGrafico;

  // === Curva de permanência ===

  const graficoPermanencia = useMemo(() => {
    if (!ultimoMes) return { rotulos: [], completos: [], series: [] as SerieGrafico[], vazio: true };

    // NENHUM filtro se aplica aqui. A curva responde a uma pergunta só, sobre a
    // coorte inteira: de todos os Auditores que entraram pelo concurso de 2021,
    // quantos ainda restam. É `registros`, e não `saidasFiltradas`.
    //
    // O filtro de tipo de saída é o que não pode entrar de jeito nenhum:
    // esconder um tipo transformaria quem saiu por ele em alguém que ficou, e a
    // curva mentiria para cima. O de coorte já não valia — o gráfico é, por
    // definição, só de quem entrou depois de jun/2022.
    const meses = listarCompetencias(MES_INICIO_GRAFICO_SAIDAS, ultimoMes.mes);
    const pontos = curvaDePermanencia(registros, ID_CONCURSO_2021, meses);
    if (pontos.every((ponto) => ponto.percentual === null)) {
      return { rotulos: [], completos: [], series: [] as SerieGrafico[], vazio: true };
    }

    return {
      rotulos: meses.map(formatarCompetencia),
      completos: meses.map(formatarCompetenciaLonga),
      series: [
        {
          rotulo: rotuloDoConcurso(ID_CONCURSO_2021),
          cor: COR_POR_CONCURSO[ID_CONCURSO_2021],
          tipo: 'linha' as const,
          sufixo: '%',
          valores: pontos.map((ponto) => ponto.percentual),
          detalhes: pontos.map((ponto) => [
            `${numero(ponto.restantes)} de ${numero(ponto.entradas)} ainda na CGU`,
            `${numero(ponto.saidas)} já ${ponto.saidas === 1 ? 'havia saído' : 'haviam saído'}`,
          ]),
        },
      ],
      vazio: false,
    };
  }, [registros, ultimoMes]);

  // === Tabela de destinos e últimas saídas ===
  //
  // Os dois leem `todasAsSaidas`, não `saidasFiltradas`: são registro do que
  // aconteceu, não recorte. "Últimas saídas" é o mural do que acabou de sair —
  // esconder uma saída porque a especialidade dela está desmarcada faria o
  // painel omitir a notícia mais recente sem dizer que omitiu. E os destinos
  // são a resposta a "para onde foram os Auditores", no plural e no geral;
  // quem quiser recortar por coorte tem o histórico de alterações.

  const gruposDeDestino = useMemo(
    () =>
      agregarPorDestino(todasAsSaidas).map((grupo) => ({
        rotulo: grupo.rotulo,
        total: grupo.total,
        itens: grupo.itens
          .map(detalharSaida)
          .sort((a, b) => b.mesSaida.localeCompare(a.mesSaida) || a.nome.localeCompare(b.nome, 'pt-BR')),
      })),
    [todasAsSaidas]
  );

  const ultimasSaidas = useMemo(
    () =>
      todasAsSaidas
        .map(detalharSaida)
        .sort((a, b) => b.mesSaida.localeCompare(a.mesSaida) || a.nome.localeCompare(b.nome, 'pt-BR'))
        .slice(0, 6),
    [todasAsSaidas]
  );

  const base = baseDoSite();

  const icone = (definicao: typeof faCalendarAlt) => (
    <FontAwesomeIcon icon={definicao} className="h-10 w-10 text-red-400 md:h-12 md:w-12" />
  );

  const semDados = (mensagem: string) => (
    <div className="rounded border border-gray-800 bg-gray-900/50 p-8 text-center text-gray-500">
      {carregando ? 'Carregando...' : mensagem}
    </div>
  );

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
          <section className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-3">
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
                      {/* O DOU sai no dia; o SIAPE, com ~2 meses de atraso. Dizer de
                          quanto é a distância é o que impede que a diferença entre
                          este card e a lista de últimas saídas pareça erro. */}
                      {saidasDou && saidasDou.atosDepoisDaUltimaCompetencia > 0 && (
                        <div className="text-gray-500">
                          {saidasDou.atosDepoisDaUltimaCompetencia} ato
                          {saidasDou.atosDepoisDaUltimaCompetencia === 1 ? '' : 's'} publicado
                          {saidasDou.atosDepoisDaUltimaCompetencia === 1 ? '' : 's'} depois de{' '}
                          {formatarCompetenciaLonga(saidasDou.ultimaCompetenciaSiape)}, que é a última
                          competência do SIAPE. Elas só entram nas contagens quando o Portal da
                          Transparência as confirmar.
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
                            ? `${base}data/saidas_dou/${evento.arquivo}`
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
              value={numero(saidasNoPeriodo)}
              label="Auditores que saíram da CGU"
              icon={icone(faUserMinus)}
              footer={
                <div className="space-y-2">
                  <div>Desde {formatarCompetenciaLonga(MES_INICIO_GRAFICO_SAIDAS)}.</div>
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
                </div>
              }
              estaCarregando={carregando}
            />
          </section>

          <section className="mb-8">
            <h2 className="mb-1 text-lg font-semibold text-red-300">Saídas mês a mês</h2>
            <p className="mb-3 text-sm text-gray-400">
              Quantos Auditores deixaram a CGU em cada competência, no recorte escolhido abaixo. A série começa em
              agosto de 2022, primeira competência em que alguém da coorte de 2022 poderia aparecer ausente.
              {!carregando && (
                <>
                  {' '}
                  <span className="text-gray-300">
                    {numero(noGrafico)} saída{noGrafico === 1 ? '' : 's'} no gráfico
                  </span>
                  {foraDoGrafico > 0 && ` (${numero(foraDoGrafico)} anterior a ago/2022, fora do corte)`}.
                </>
              )}
            </p>
            {!graficoSaidas.vazio ? (
              <EvasionChart
                rotulos={graficoSaidas.rotulos}
                rotulosCompletos={graficoSaidas.completos}
                series={graficoSaidas.series}
                altura={340}
                empilhar
                maximoRotulosX={14}
              />
            ) : (
              semDados('Nenhuma saída neste recorte. Abra "Filtros", logo abaixo, e marque mais alguma caixinha.')
            )}
          </section>

          {/* Os filtros ficam DEPOIS do gráfico: quem chega vê primeiro o quadro
              inteiro, e só então o recorta. Fechados por padrão, porque o recorte
              que abre o painel já é o que interessa à maioria. Eles valem para o
              gráfico acima, e só para ele. */}
          <CardDeFiltros filtros={filtros} />

          <section className="mb-8">
            <h2 className="mb-1 text-lg font-semibold text-red-300">Curva de permanência</h2>
            <p className="mb-3 text-sm text-gray-400">
              <span className="text-gray-300">
                Do total de Auditores que entraram pelo concurso de 2021, quantos ainda restam?
              </span>{' '}
              Em cada competência do eixo, a conta é (entradas até aquele mês &minus; saídas até aquele mês) dividido
              pelas entradas até aquele mês — as duas pontas contadas por pessoa. O denominador cresce ao longo do
              eixo, conforme novas turmas tomam posse.{' '}
              <span className="text-gray-300">Esta curva não acompanha os filtros acima</span>: é sempre a coorte de
              2021 inteira. Recortá-la por tipo de saída transformaria quem saiu em alguém que ficou, e ela mentiria
              para cima.
            </p>
            {!graficoPermanencia.vazio ? (
              <EvasionChart
                rotulos={graficoPermanencia.rotulos}
                rotulosCompletos={graficoPermanencia.completos}
                series={graficoPermanencia.series}
                altura={300}
                eixoEsquerdaComZero={false}
                maximoEixoEsquerda={100}
                tituloEixoEsquerda="% ainda na CGU"
                maximoRotulosX={14}
              />
            ) : (
              semDados('Sem base suficiente para traçar a curva.')
            )}
            <p className="mt-2 text-xs text-gray-500">
              Eixo horizontal: competências do calendário, de ago/2022 até a última do SIAPE.
            </p>
          </section>

          <section className="mb-8 rounded-xl border border-gray-800 bg-gray-900 p-4">
            <h2 className="mb-1 text-2xl font-bold text-amber-400">Últimas saídas registradas</h2>
            <p className="mb-3 text-sm text-gray-400">
              As seis mais recentes de toda a série, coorte de 2021 e veteranos juntos.{' '}
              <span className="text-gray-300">Não acompanha os filtros acima</span>: é o que acabou de acontecer, e
              esconder uma saída porque a especialidade dela está desmarcada omitiria a notícia mais recente sem dizer
              que omitiu.
            </p>
            {/* Esta lista é do SIAPE; o card de dias é do DOU. As duas fontes não
                podem coincidir — o Portal publica com atraso —, e sem esta frase a
                diferença de datas entre elas lê como erro do painel. */}
            {saidasDou && saidasDou.atosDepoisDaUltimaCompetencia > 0 && (
              <p className="mb-3 text-sm text-gray-500">
                Aqui quem conta é o SIAPE, que vai até{' '}
                {formatarCompetenciaLonga(saidasDou.ultimaCompetenciaSiape)}. O DOU já publicou mais{' '}
                <span className="text-gray-300">{saidasDou.atosDepoisDaUltimaCompetencia}</span> ato
                {saidasDou.atosDepoisDaUltimaCompetencia === 1 ? '' : 's'} de saída depois disso — estão no card
                acima, e entram nesta lista quando o Portal da Transparência confirmar de quem são.
              </p>
            )}
            {ultimasSaidas.length === 0 ? (
              <div className="text-sm text-gray-400">
                {carregando ? 'Carregando...' : 'Nenhuma saída registrada.'}
              </div>
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
              SIAPE que o diga: cada linha traz de onde veio a informação e se alguém a conferiu. São{' '}
              <span className="font-bold text-orange-400">{numero(todasAsSaidas.length)}</span> saída
              {todasAsSaidas.length === 1 ? '' : 's'} em toda a série, coorte de 2021 e veteranos juntos.{' '}
              <span className="text-gray-300">Esta tabela não acompanha os filtros acima</span> — para recortar por
              coorte ou por especialidade, use o{' '}
              <a href="./historico_alteracoes.html" className="text-amber-400 hover:text-amber-300">
                histórico de alterações
              </a>
              .
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
