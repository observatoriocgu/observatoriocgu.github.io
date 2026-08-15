import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

import { MOTIVOS_SAIDA, rotuloDoConcurso } from './constants';
import { RegistroAuditor, SaidasDou } from './types';
import {
  carregarCsv,
  carregarJsonPublico,
  formatarCompetenciaLonga,
  formatarDataIsoParaBr,
} from './lib/dados';
import { comoRegistros, fontesDaSaida, mesclarSaidasDoDou, motivoDe, saidas } from './lib/painel';

const TODAS = 'TODAS';

/**
 * Relatório para imprimir.
 *
 * Até a Fase 2 as listas eram "exonerados", "desistentes" e "nomeados em outros
 * concursos". Nenhuma das três sobrevive à D11: `DESISTENTE` não existe no
 * universo do SIAPE — quem desiste nunca chega a aparecer no cadastro — e
 * concurso de destino é Fase 7. As listas passam a ser por MOTIVO DE SAÍDA, que
 * é o que o ato do DOU informa.
 */
const RelatorioImpressao: React.FC = () => {
  const [registros, setRegistros] = useState<RegistroAuditor[]>([]);
  const [motivoSelecionado, setMotivoSelecionado] = useState<string>(TODAS);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    // O relatório impresso lê as mesmas duas fontes que o painel (D22): sem o
    // JSON do DOU ele voltaria a terminar na última competência do SIAPE, e a
    // folha impressa contradiria a tela.
    Promise.all([
      carregarCsv('dados.csv'),
      carregarJsonPublico<SaidasDou>('atos_dou.json').catch(() => null),
    ])
      .then(([linhas, dou]) =>
        setRegistros(mesclarSaidasDoDou(comoRegistros(linhas), dou?.saidasRecentes ?? []))
      )
      .catch((falha) => setErro(falha instanceof Error ? falha.message : 'Erro ao carregar os dados.'))
      .finally(() => setCarregando(false));
  }, []);

  const todasAsSaidas = useMemo(
    () =>
      saidas(registros).sort(
        (a, b) => b.MES_SAIDA.localeCompare(a.MES_SAIDA) || a.NOME.localeCompare(b.NOME, 'pt-BR')
      ),
    [registros]
  );

  /** Só os motivos que de fato ocorrem — a lista fixa não vira aba vazia. */
  const motivosPresentes = useMemo(() => {
    const encontrados = new Set(todasAsSaidas.map(motivoDe));
    return MOTIVOS_SAIDA.filter((motivo) => encontrados.has(motivo));
  }, [todasAsSaidas]);

  const linhas = useMemo(
    () =>
      motivoSelecionado === TODAS
        ? todasAsSaidas
        : todasAsSaidas.filter((registro) => motivoDe(registro) === motivoSelecionado),
    [todasAsSaidas, motivoSelecionado]
  );

  const titulo =
    motivoSelecionado === TODAS
      ? 'Auditores que deixaram a CGU'
      : `Auditores que deixaram a CGU — ${motivoSelecionado.toLocaleLowerCase('pt-BR')}`;

  return (
    <main className="min-h-screen bg-slate-100 p-4 text-slate-900 md:p-8">
      <div className="print-area mx-auto max-w-7xl rounded-xl bg-white p-5 shadow-lg md:p-8">
        <header className="mb-6 border-b-2 border-slate-800 pb-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">Observatório das Evasões</p>
          <h1 className="mt-1 text-3xl font-bold">{titulo}</h1>
          <p className="mt-1 text-sm text-slate-600">Auditores Federais de Finanças e Controle &mdash; CGU</p>
        </header>

        <div className="print-hidden mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Selecionar motivo da saída">
            {[TODAS, ...motivosPresentes].map((motivo) => (
              <button
                key={motivo}
                type="button"
                onClick={() => setMotivoSelecionado(motivo)}
                aria-pressed={motivoSelecionado === motivo}
                className={`rounded-lg border px-4 py-2 font-medium ${
                  motivoSelecionado === motivo
                    ? 'border-slate-900 bg-slate-900 text-white'
                    : 'border-slate-300 bg-white text-slate-800 hover:bg-slate-100'
                }`}
              >
                {motivo === TODAS ? 'Todas as saídas' : motivo}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-lg bg-red-700 px-5 py-2 font-semibold text-white hover:bg-red-800"
          >
            Imprimir lista selecionada
          </button>
        </div>

        {carregando ? (
          <p className="py-10 text-center text-slate-500">Carregando dados...</p>
        ) : erro ? (
          <p className="py-10 text-center text-red-700">{erro}</p>
        ) : (
          <>
            <p className="total-registros mb-3 text-sm text-slate-600">
              Total de registros: {linhas.length.toLocaleString('pt-BR')}
            </p>
            <div className="print-table-wrapper overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-800 text-white">
                    <th className="w-12 border border-slate-500 px-2 py-2 text-center">Nº</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Nome</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Concurso</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Unidade</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Saída</th>
                    {motivoSelecionado === TODAS && (
                      <th className="border border-slate-500 px-3 py-2 text-left">Motivo</th>
                    )}
                    <th className="border border-slate-500 px-3 py-2 text-left">Órgão de destino</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Ato no DOU</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Procedência</th>
                  </tr>
                </thead>
                <tbody>
                  {linhas.map((registro, indice) => (
                    <tr key={registro.ID_SERVIDOR_PORTAL} className="even:bg-slate-100">
                      <td className="border border-slate-300 px-2 py-2 text-center">{indice + 1}</td>
                      <td className="border border-slate-300 px-3 py-2 font-medium">{registro.NOME || '—'}</td>
                      <td className="border border-slate-300 px-3 py-2">{rotuloDoConcurso(registro.CONCURSO)}</td>
                      <td className="border border-slate-300 px-3 py-2">{registro.UNIDADE || '—'}</td>
                      <td className="whitespace-nowrap border border-slate-300 px-3 py-2">
                        {formatarCompetenciaLonga(registro.MES_SAIDA)}
                      </td>
                      {motivoSelecionado === TODAS && (
                        <td className="border border-slate-300 px-3 py-2">{motivoDe(registro)}</td>
                      )}
                      <td className="border border-slate-300 px-3 py-2">
                        {registro.ORGAO_DESTINO || 'Não identificado'}
                      </td>
                      <td className="border border-slate-300 px-3 py-2">
                        {registro.ATO_SAIDA_TITULO
                          ? `${registro.ATO_SAIDA_TITULO} (DOU de ${formatarDataIsoParaBr(registro.DATA_PUBLICACAO_SAIDA)})`
                          : 'Sem ato identificado'}
                      </td>
                      {/* Os selos de fonte em texto, porque a folha impressa é
                          preto e branco e a cor do selo não sobrevive a ela. */}
                      <td className="whitespace-nowrap border border-slate-300 px-3 py-2">
                        {fontesDaSaida(registro).join(' · ') || 'sem fonte'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-xs text-slate-500">
              Fonte primária: diferença mês a mês do Cadastro de Servidores Civis (SIAPE), no Portal da Transparência.
              Motivo e destino vêm do ato correspondente no Diário Oficial da União. A coluna
              &ldquo;Procedência&rdquo; diz de onde veio a informação de cada linha e se uma pessoa já a conferiu.
            </p>
          </>
        )}
      </div>
    </main>
  );
};

const container = document.getElementById('root');
if (container) createRoot(container).render(<RelatorioImpressao />);
