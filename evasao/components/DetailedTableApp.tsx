import React, { useEffect, useMemo, useState } from 'react';

import {
  AREAS_SEM_ESPECIALIDADE,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVOS_SAIDA,
  SITUACAO_EM_EXERCICIO,
  rotuloDoConcurso,
} from '../constants';
import { RegistroAuditor } from '../types';
import { carregarCsv, formatarCompetenciaLonga, formatarDataIsoParaBr } from '../lib/dados';
import { areaDe, comoRegistros, motivoDe, saiuDaCgu, urlDoAto } from '../lib/painel';
import { SelosDaLinha } from './Selos';

const TODOS = '';

/** Quantas linhas renderizar de uma vez. 2.009 células vezes 13 colunas trava o navegador. */
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

const Celula: React.FC<{ children?: React.ReactNode; alinhamento?: string; className?: string }> = ({
  children,
  alinhamento = 'text-center',
  className = '',
}) => (
  <td className={`border border-black px-1 py-0.5 text-[10px] text-gray-700 ${alinhamento} ${className}`}>
    {children}
  </td>
);

const DetailedTableApp: React.FC = () => {
  const [registros, setRegistros] = useState<RegistroAuditor[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [busca, setBusca] = useState('');
  const [coorte, setCoorte] = useState<string>(TODOS);
  const [area, setArea] = useState<string>(TODOS);
  const [unidade, setUnidade] = useState<string>(TODOS);
  const [motivo, setMotivo] = useState<string>(TODOS);
  const [situacao, setSituacao] = useState<string>(TODOS);
  const [soVerificados, setSoVerificados] = useState(false);
  const [limite, setLimite] = useState(PAGINA);

  useEffect(() => {
    let montado = true;
    (async () => {
      try {
        const linhas = await carregarCsv('dados.csv');
        if (montado) setRegistros(comoRegistros(linhas));
      } catch (falha) {
        if (montado) setErro(falha instanceof Error ? falha.message : 'Erro ao carregar dados.csv.');
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

  const motivos = useMemo(() => {
    const encontrados = new Set(registros.filter(saiuDaCgu).map(motivoDe));
    return MOTIVOS_SAIDA.filter((valor) => encontrados.has(valor));
  }, [registros]);

  const filtrados = useMemo(() => {
    const termo = normalizar(busca);
    return registros
      .filter((registro) => {
        if (coorte && registro.CONCURSO !== coorte) return false;
        if (area && areaDe(registro) !== area) return false;
        if (unidade && registro.UNIDADE !== unidade) return false;
        if (situacao && registro.SITUACAO !== situacao) return false;
        if (motivo && (!saiuDaCgu(registro) || motivoDe(registro) !== motivo)) return false;
        if (soVerificados && registro.VERIFICADO !== 'SIM') return false;
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
  }, [registros, busca, coorte, area, unidade, situacao, motivo, soVerificados]);

  useEffect(() => setLimite(PAGINA), [busca, coorte, area, unidade, situacao, motivo, soVerificados]);

  const visiveis = filtrados.slice(0, limite);
  const totalVerificados = filtrados.filter((registro) => registro.VERIFICADO === 'SIM').length;

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

          {seletor('Coorte', coorte, setCoorte, [ID_CONCURSO_2021, ID_CONCURSO_VETERANO], 'Todas', rotuloDoConcurso)}
          {seletor('Especialidade', area, setArea, areas, 'Todas')}
          {seletor('Unidade', unidade, setUnidade, unidades, 'Todas')}
          {seletor('Situação', situacao, setSituacao, situacoes, 'Todas')}
          {seletor('Motivo da saída', motivo, setMotivo, motivos, 'Todos')}

          <label className="flex items-center gap-1.5 pb-1 text-[11px] font-medium text-gray-700">
            <input
              type="checkbox"
              checked={soVerificados}
              onChange={(evento) => setSoVerificados(evento.target.checked)}
              className="h-3.5 w-3.5 accent-red-600"
            />
            Só conferidos por gente
          </label>
        </div>

        {!carregando && !erro && (
          <div className="mb-2 text-center text-xs text-gray-600">
            {filtrados.length.toLocaleString('pt-BR')} Auditor(es) neste recorte ·{' '}
            {filtrados.filter(saiuDaCgu).length.toLocaleString('pt-BR')} já saíram ·{' '}
            {totalVerificados.toLocaleString('pt-BR')} com linha conferida por uma pessoa
            {visiveis.length < filtrados.length && ` · mostrando ${visiveis.length.toLocaleString('pt-BR')}`}
          </div>
        )}

        <div className="border border-black bg-white shadow-lg">
          <div className="max-h-[80vh] overflow-x-auto overflow-y-auto">
            <table className="w-full border-collapse border border-black text-[10px]">
              <thead className="sticky top-0 z-50 bg-white text-[10px] uppercase text-gray-700 shadow-sm">
                <tr>
                  {[
                    'Nome',
                    'Coorte',
                    'Especialidade',
                    'Class.',
                    'Modalidade',
                    'Unidade',
                    'UF',
                    'Situação',
                    'Motivo da saída',
                    'Saída',
                    'Órgão de destino',
                    'Procedência',
                    'Ato no DOU',
                  ].map((titulo) => (
                    <th key={titulo} className="border border-black bg-white px-1 py-1 text-center font-semibold">
                      {titulo}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-black">
                {carregando && (
                  <tr>
                    <td colSpan={13} className="border border-black px-4 py-6 text-center text-orange-600">
                      Carregando dados...
                    </td>
                  </tr>
                )}
                {erro && (
                  <tr>
                    <td colSpan={13} className="border border-black px-4 py-6 text-center text-red-700">
                      {erro}
                    </td>
                  </tr>
                )}
                {!carregando && !erro && visiveis.length === 0 && (
                  <tr>
                    <td colSpan={13} className="border border-black px-4 py-6 text-center text-gray-500">
                      Nenhum Auditor encontrado com estes filtros.
                    </td>
                  </tr>
                )}
                {visiveis.map((registro) => {
                  const saiu = saiuDaCgu(registro);
                  const ato = urlDoAto(registro);
                  return (
                    <tr
                      key={registro.ID_SERVIDOR_PORTAL}
                      className={`${CORES_POR_SITUACAO[registro.SITUACAO] ?? 'bg-white'} transition-all duration-150 hover:brightness-95`}
                    >
                      <Celula alinhamento="text-left" className="font-medium text-gray-900">
                        {registro.NOME || '-'}
                      </Celula>
                      <Celula>{rotuloDoConcurso(registro.CONCURSO)}</Celula>
                      <Celula>{registro.AREA || '-'}</Celula>
                      <Celula>{registro.POSICAO_CONCURSO || '-'}</Celula>
                      <Celula>{registro.MODALIDADE || '-'}</Celula>
                      <Celula>{registro.UNIDADE || '-'}</Celula>
                      <Celula>{registro.UF || '-'}</Celula>
                      <Celula className="whitespace-nowrap">
                        {registro.SITUACAO || '-'}
                        {registro.SAIDA_PROVISORIA === 'SIM' && (
                          <span
                            title="Ausência observada uma única vez. Só vira saída quando o mês seguinte confirmar."
                            className="ml-1 rounded border border-orange-500 bg-orange-100 px-1 text-[9px] text-orange-800"
                          >
                            provisória
                          </span>
                        )}
                      </Celula>
                      <Celula>{saiu ? motivoDe(registro) : '-'}</Celula>
                      <Celula className="whitespace-nowrap">
                        {registro.MES_SAIDA ? formatarCompetenciaLonga(registro.MES_SAIDA) : '-'}
                      </Celula>
                      <Celula>{registro.ORGAO_DESTINO || '-'}</Celula>
                      <Celula>
                        {saiu ? (
                          <SelosDaLinha
                            fonte={registro.ORGAO_DESTINO ? registro.FONTE_DESTINO : registro.FONTE_MOTIVO}
                            verificado={registro.VERIFICADO === 'SIM'}
                            compacto
                            tema="claro"
                          />
                        ) : (
                          <span title="Quem está na CGU vem direto do SIAPE; não há o que conferir contra o DOU.">
                            SIAPE
                          </span>
                        )}
                      </Celula>
                      <Celula>
                        {ato ? (
                          <a
                            href={ato}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={registro.ATO_SAIDA_TITULO}
                            className="text-blue-700 underline hover:text-blue-900"
                          >
                            {formatarDataIsoParaBr(registro.DATA_PUBLICACAO_SAIDA) || 'ver ato'}
                          </a>
                        ) : (
                          '-'
                        )}
                      </Celula>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {visiveis.length < filtrados.length && (
          <div className="mt-3 text-center">
            <button
              type="button"
              onClick={() => setLimite((atual) => atual + PAGINA)}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-100"
            >
              Mostrar mais {Math.min(PAGINA, filtrados.length - visiveis.length)} de{' '}
              {(filtrados.length - visiveis.length).toLocaleString('pt-BR')} restantes
            </button>
          </div>
        )}

        <p className="mt-4 text-center text-xs text-gray-500">
          A especialidade vem do Edital CGU nº 5, de 13/06/2022, publicado no DOU; veteranos não têm edital de onde
          tirá-la. O motivo e o destino vêm do ato do DOU, e a coluna &ldquo;Procedência&rdquo; diz, para cada linha, de
          onde veio a informação e se uma pessoa já a conferiu.
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
