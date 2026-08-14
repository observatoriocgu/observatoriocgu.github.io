import React, { useEffect, useMemo, useState } from 'react';

import { rotuloDoConcurso } from '../constants';
import { AlteracaoRegistro, LogDeAlteracoes, MesDeAlteracoes, RegistroAuditor } from '../types';
import { carregarCsv, carregarJsonPublico, formatarCompetenciaLonga, formatarDataIsoParaBr } from '../lib/dados';
import { comoRegistros, motivoDe, urlDoAto } from '../lib/painel';
import { SelosDaLinha } from './Selos';

type Filtro = 'todas' | 'saida' | 'entrada';

/**
 * O histórico de alterações.
 *
 * Até a Fase 2 este log era reconstruído do histórico do Git do `dados.csv` —
 * arqueologia de commits, com a data do commit no lugar da data do fato. Agora
 * ele vem do diff mês a mês do SIAPE: cada bloco é uma competência, e a data é
 * a do dado, não a de quem o publicou. Por isso não existe mais `hash`, `autor`
 * nem `mensagem` aqui.
 */
const HistoryPage: React.FC = () => {
  const [log, setLog] = useState<LogDeAlteracoes | null>(null);
  const [registrosPorId, setRegistrosPorId] = useState<Map<string, RegistroAuditor>>(new Map());
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [filtro, setFiltro] = useState<Filtro>('todas');
  const [busca, setBusca] = useState('');
  const [mesesVisiveis, setMesesVisiveis] = useState(12);

  useEffect(() => {
    let montado = true;

    (async () => {
      try {
        // O CSV é opcional: sem ele o histórico ainda se lê, só perde o motivo e
        // o link do ato. O JSON, não — sem ele não há o que mostrar.
        const [logCarregado, linhas] = await Promise.all([
          carregarJsonPublico<LogDeAlteracoes>('alteracoes-registros.json'),
          carregarCsv('dados.csv').catch(() => []),
        ]);
        if (!montado) return;
        setLog(logCarregado);
        // Junta pelo Id_SERVIDOR_PORTAL, e só por ele (D12): a cadeia
        // INSCRICAO → MASP → HGV-0 → NOME que existia aqui está revogada, e
        // casar por nome atribuiria ato de uma pessoa a seu homônimo.
        setRegistrosPorId(
          new Map(comoRegistros(linhas).map((registro) => [registro.ID_SERVIDOR_PORTAL, registro]))
        );
      } catch (falha) {
        if (montado) setErro(falha instanceof Error ? falha.message : 'Erro ao carregar o histórico.');
      } finally {
        if (montado) setCarregando(false);
      }
    })();

    return () => {
      montado = false;
    };
  }, []);

  const normalizar = (valor: string) =>
    String(valor ?? '').normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('pt-BR').trim();

  const meses: MesDeAlteracoes[] = useMemo(() => {
    if (!log) return [];
    const termo = normalizar(busca);
    return log.history
      .map((mes) => ({
        ...mes,
        changes: mes.changes.filter(
          (mudanca) =>
            (filtro === 'todas' || mudanca.tipo === filtro) &&
            (!termo || normalizar(mudanca.nome).includes(termo))
        ),
      }))
      .filter((mes) => mes.changes.length > 0);
  }, [log, filtro, busca]);

  useEffect(() => setMesesVisiveis(12), [filtro, busca]);

  const totalFiltrado = meses.reduce((soma, mes) => soma + mes.changes.length, 0);

  const descrever = (mudanca: AlteracaoRegistro): React.ReactNode => {
    const pessoa = <strong className="text-amber-400">{mudanca.nome}</strong>;
    const registro = registrosPorId.get(mudanca.id);

    if (mudanca.tipo === 'entrada') {
      return (
        <>
          {pessoa} entrou em exercício na CGU ({mudanca.unidade || 'unidade não informada'}), coorte{' '}
          {rotuloDoConcurso(mudanca.concurso)}.
        </>
      );
    }

    const motivo = registro ? motivoDe(registro) : mudanca.toSituacao;
    const destino = registro?.ORGAO_DESTINO || mudanca.orgaoDestino;

    return (
      <>
        {pessoa} deixou a CGU ({mudanca.unidade || 'unidade não informada'}) — {motivo.toLocaleLowerCase('pt-BR')}
        {destino ? (
          <>
            , para <strong className="text-amber-400">{destino}</strong>
          </>
        ) : null}
        .
      </>
    );
  };

  const botao = (valor: Filtro, rotulo: string) => (
    <button
      key={valor}
      type="button"
      onClick={() => setFiltro(valor)}
      aria-pressed={filtro === valor}
      className={`rounded px-3 py-1 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-red-400 ${
        filtro === valor
          ? 'bg-red-500 text-white shadow-lg'
          : 'border border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700'
      }`}
    >
      {rotulo}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-950 p-4 text-gray-200 sm:p-6 lg:p-8">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-extrabold text-red-400 md:text-5xl">Histórico de alterações</h1>
          <p className="mt-2 text-lg font-medium text-amber-400">
            Auditores Federais de Finanças e Controle &mdash; CGU
          </p>
        </header>

        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-gray-300">
              {carregando
                ? 'Carregando o histórico...'
                : erro
                  ? 'Não foi possível carregar o histórico.'
                  : log
                    ? `${log.totalChangeCount.toLocaleString('pt-BR')} movimentações entre ${formatarCompetenciaLonga(log.primeiroMes)} e ${formatarCompetenciaLonga(log.ultimoMes)}.`
                    : ''}
            </p>
            {log && !carregando && !erro && <p className="mt-1 text-sm text-gray-500">Fonte: {log.fonte}.</p>}
          </div>
          <a
            href="./index.html"
            className="inline-flex items-center justify-center rounded-lg border border-gray-700 bg-gray-800 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
          >
            Voltar ao dashboard
          </a>
        </div>

        {!carregando && !erro && (
          <div className="mb-6 flex flex-wrap items-end gap-3">
            <div className="flex flex-wrap gap-2">
              {botao('todas', 'Todas')}
              {botao('saida', 'Saídas')}
              {botao('entrada', 'Entradas')}
            </div>
            <input
              type="search"
              value={busca}
              onChange={(evento) => setBusca(evento.target.value)}
              placeholder="Buscar por nome..."
              className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-400 sm:w-72"
            />
            <span className="pb-2 text-sm text-gray-500">
              {totalFiltrado.toLocaleString('pt-BR')} no recorte
            </span>
          </div>
        )}

        {erro && (
          <div className="rounded-2xl border border-red-700 bg-red-950/40 p-6 text-center text-red-300">
            <strong>Erro:</strong> {erro}
          </div>
        )}

        {!carregando && !erro && meses.length === 0 && (
          <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
            Nenhuma movimentação neste recorte.
          </div>
        )}

        <div className="space-y-4">
          {meses.slice(0, mesesVisiveis).map((mes) => (
            <section key={mes.mes} className="overflow-hidden rounded-2xl border border-gray-800 bg-gray-900">
              <header className="flex items-baseline justify-between border-b border-gray-800 bg-gray-950 px-5 py-3">
                <h2 className="text-lg font-semibold text-amber-400">{formatarCompetenciaLonga(mes.mes)}</h2>
                <span className="text-sm text-gray-500">
                  {mes.changes.length} de {mes.changeCount} movimentação(ões)
                </span>
              </header>
              <ul className="divide-y divide-gray-800">
                {mes.changes.map((mudanca) => {
                  const registro = registrosPorId.get(mudanca.id);
                  const ato = registro ? urlDoAto(registro) : '';
                  return (
                    <li key={`${mes.mes}-${mudanca.id}`} className="flex flex-wrap items-baseline gap-2 px-5 py-3 text-sm">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                          mudanca.tipo === 'saida'
                            ? 'bg-red-500/15 text-red-300'
                            : 'bg-emerald-500/15 text-emerald-300'
                        }`}
                      >
                        {mudanca.tipo === 'saida' ? 'saída' : 'entrada'}
                      </span>
                      <span className="text-gray-300">{descrever(mudanca)}</span>
                      {mudanca.tipo === 'saida' && registro && (
                        <SelosDaLinha
                          fonte={registro.ORGAO_DESTINO ? registro.FONTE_DESTINO : registro.FONTE_MOTIVO}
                          verificado={registro.VERIFICADO === 'SIM'}
                          compacto
                        />
                      )}
                      {ato && (
                        <a
                          href={ato}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={registro?.ATO_SAIDA_TITULO}
                          className="text-xs text-amber-400 hover:text-amber-300"
                        >
                          ato de {formatarDataIsoParaBr(registro?.DATA_PUBLICACAO_SAIDA ?? '') || 'data não informada'}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>

        {meses.length > mesesVisiveis && (
          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={() => setMesesVisiveis((atual) => atual + 12)}
              className="rounded-lg border border-gray-700 bg-gray-800 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
            >
              Carregar mais 12 competências
            </button>
          </div>
        )}

        <p className="mt-8 text-center text-sm text-gray-500">
          Cada bloco é uma competência do SIAPE. A data é a do dado, não a de quando o observatório o publicou.
        </p>
      </div>
    </div>
  );
};

export default HistoryPage;
