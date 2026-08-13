import React, { useEffect, useMemo, useState } from 'react';

type Change = {
  masp?: string;
  inscricao?: string;
  nome: string;
  fromSituacao: string;
  toSituacao: string;
  orgaoDestino: string | null;
  before: Record<string, string>;
  after: Record<string, string>;
};

type CommitInfo = {
  hash: string;
  date: string;
  author: string;
  message: string;
};

type HistoryItem = {
  commit: CommitInfo;
  changeCount: number;
  changes: Change[];
};

type HistoryRow = Change & {
  commitDate: string;
  currentOrgaoDestino?: string;
  currentDataExoneracao?: string;
};

type CurrentRecord = Record<string, string | null>;

const analisarDataBrasil = (d: any): Date | null => {
  if (!d || typeof d !== 'string') return null;
  const partes = d.split('/');
  if (partes.length !== 3) return null;
  const dia = Number(partes[0]);
  const mes = Number(partes[1]) - 1;
  const ano = Number(partes[2]);
  if (Number.isNaN(dia) || Number.isNaN(mes) || Number.isNaN(ano)) return null;
  return new Date(ano, mes, dia);
};

const formatDate = (dateString: string | undefined | null): string => {
  if (!dateString) return '—';

  const isoMatch = dateString.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(?:Z|([+-]\d{2}):?(\d{2}))?$/,
  );

  if (isoMatch) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  const date = analisarDataBrasil(dateString);
  if (date) {
    return new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  return dateString;
};

const parseCsv = (texto: string): CurrentRecord[] => {
  const cleanText = texto.replace(/^\uFEFF/, '');
  const linhas = cleanText.split(/\r?\n/).filter(l => l.trim() !== '');
  if (linhas.length === 0) return [];

  const normalizeHeader = (header: string) => header.replace(/^\uFEFF/, '').trim();
  const canonicalHeader = (header: string) => {
    const normalized = normalizeHeader(header).toUpperCase();
    if (normalized === 'HGV-0') return 'MASP';
    return normalized;
  };

  const analisarLinha = (linha: string) => {
    const partes: string[] = [];
    let atual = '';
    let entreAspas = false;
    for (let i = 0; i < linha.length; i++) {
      const caractere = linha[i];
      if (caractere === '"') {
        if (entreAspas && linha[i + 1] === '"') {
          atual += '"';
          i++;
        } else {
          entreAspas = !entreAspas;
        }
        continue;
      }
      if (caractere === ';' && !entreAspas) {
        partes.push(atual);
        atual = '';
        continue;
      }
      atual += caractere;
    }
    partes.push(atual);
    return partes;
  };

  const cabecalhos = analisarLinha(linhas[0]).map(coluna => canonicalHeader(coluna));
  const registros: CurrentRecord[] = [];

  for (let i = 1; i < linhas.length; i++) {
    const linha = linhas[i];
    const partes = analisarLinha(linha);
    while (partes.length < cabecalhos.length) partes.push('');
    const objeto: CurrentRecord = {};
    for (let j = 0; j < cabecalhos.length; j++) {
      objeto[cabecalhos[j]] = partes[j] ? partes[j].trim() : null;
    }
    registros.push(objeto);
  }

  return registros;
};

const normalizeKey = (value: string | null | undefined) => String(value ?? '').trim().toUpperCase();

const pickFirstNonEmpty = (...values: Array<string | null | undefined>) => {
  for (const value of values) {
    if (value != null) {
      const trimmed = String(value).trim();
      if (trimmed !== '') return trimmed;
    }
  }
  return '';
};

const buildCurrentRecordMap = (currentRecords: CurrentRecord[]) => {
  const map = new Map<string, CurrentRecord>();
  for (const registro of currentRecords) {
    const key = normalizeKey(pickFirstNonEmpty(registro['INSCRICAO'], registro['MASP'], registro['HGV-0'], registro['NOME']));
    if (!key) continue;
    map.set(key, registro);
  }
  return map;
};

const normalizeSituacao = (valor: string | null | undefined) => {
  const situacao = String(valor ?? '').trim().toUpperCase();
  if (situacao === 'EXONERAÇÃO' || situacao === 'EXONERACAO') return 'EXONERADO';
  return situacao;
};

const formatDescription = (change: Change, currentOrgaoDestino?: string): React.ReactNode => {
  const situacao = normalizeSituacao(change.toSituacao);
  const destino = currentOrgaoDestino?.trim() || change.orgaoDestino?.trim();
  const pessoa = <strong className="text-amber-400">{change.nome}</strong>;
  let description: React.ReactNode;

  if (situacao === 'EXONERADO') {
    description = <>Exoneração de {pessoa}.</>;
  } else if (situacao === 'DESISTENTE') {
    description = <>{pessoa} desistiu de tomar posse.</>;
  } else if (situacao === 'APOSENTADO') {
    description = <>Aposentadoria de {pessoa}.</>;
  } else if (situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA') {
    description = <>Afastamento de {pessoa}.</>;
  } else {
    description = <>{pessoa} teve alteração de situação para {change.toSituacao}.</>;
  }

  if (destino && situacao !== 'APOSENTADO') {
    description = <>{description} Órgão de destino: <strong className="text-amber-400">{destino}</strong>.</>;
  }

  return description;
};

const isRetirement = (row: HistoryRow | Change) => {
  const situacao = ((row as HistoryRow).toSituacao ?? (row as Change).toSituacao ?? '').trim().toUpperCase();
  return situacao === 'APOSENTADO' || situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA';
};

const extractLatestChanges = (history: HistoryItem[], currentMap: Map<string, CurrentRecord>): HistoryRow[] => {
  console.log('[HistoryPage] extractLatestChanges: iniciando', history.length, 'history items');
  const latestMap = new Map<string, { change: Change; commit: CommitInfo }>();
  const sorted = [...history].sort((a, b) => b.commit.date.localeCompare(a.commit.date));

  for (const item of sorted) {
    for (const change of item.changes) {
      const key = normalizeKey(pickFirstNonEmpty(change.inscricao, change.masp, change.nome));
      if (!key) {
        console.log('[HistoryPage] extractLatestChanges: change sem key', change);
        continue;
      }
      if (!latestMap.has(key)) {
        latestMap.set(key, { change, commit: item.commit });
      }
    }
  }

  const latestRows: HistoryRow[] = Array.from(latestMap.values())
    .map(({ change, commit }) => {
      const key = normalizeKey(pickFirstNonEmpty(change.inscricao, change.masp, change.nome));
      const current = currentMap.get(key);
      if (!current) {
        console.log('[HistoryPage] extractLatestChanges: currentMap não encontrou registro para', key, change.nome, change.toSituacao);
      }
      const currentOrgaoDestino = current?.['ORGAO_DESTINO'] ?? undefined;
      const currentDataExoneracao = current?.['DATA_EXONERACAO'] ?? current?.['DATA_INATIVIDADE'] ?? undefined;
      return {
        ...change,
        commitDate: commit.date,
        currentOrgaoDestino,
        currentDataExoneracao,
      };
    });

  console.log('[HistoryPage] extractLatestChanges: latestRows count', latestRows.length);

  const latestRowByKey = new Map<string, HistoryRow>();
  for (const row of latestRows) {
    const key = normalizeKey(pickFirstNonEmpty(row.inscricao, row.masp, row.nome));
    latestRowByKey.set(key, row);
  }

  const retirementRows: HistoryRow[] = [];
  const addedRetirementKeys = new Set<string>();
  for (const item of sorted) {
    for (const change of item.changes) {
      if (!isRetirement(change)) continue;
      const key = normalizeKey(pickFirstNonEmpty(change.inscricao, change.masp, change.nome));
      if (!key || addedRetirementKeys.has(key)) continue;
      const existing = latestRowByKey.get(key);
      if (existing && isRetirement(existing)) {
        console.log('[HistoryPage] extractLatestChanges: já existe aposentadoria para', key, change.nome);
        continue;
      }

      if (!currentMap.has(key)) {
        console.log('[HistoryPage] extractLatestChanges: retirement key sem currentMap', key, change.nome, change.toSituacao);
      }
      const current = currentMap.get(key);
      const currentOrgaoDestino = current?.['ORGAO_DESTINO'] ?? undefined;
      const currentDataExoneracao = current?.['DATA_EXONERACAO'] ?? current?.['DATA_INATIVIDADE'] ?? undefined;
      retirementRows.push({
        ...change,
        commitDate: item.commit.date,
        currentOrgaoDestino,
        currentDataExoneracao,
      });
      addedRetirementKeys.add(key);
    }
  }

  console.log('[HistoryPage] extractLatestChanges: retirementRows count', retirementRows.length);
  return [...latestRows, ...retirementRows].sort((a, b) => b.commitDate.localeCompare(a.commitDate));
};

const HistoryPage: React.FC = () => {
  const [historyRows, setHistoryRows] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historySource, setHistorySource] = useState<string | null>(null);

  useEffect(() => {
    const caminhos = [
      '/data/dados.csv',
      '/evasao/data/dados.csv',
      'data/dados.csv',
      './data/dados.csv',
      '/evasao/dist/data/dados.csv',
      '/evasao/dist/assets/dados.csv',
      '/evasao/dados.csv',
      '/dados.csv',
      'dist/data/dados.csv',
      'assets/dados.csv',
    ];

    const criarUrlSemCache = (baseUrl: string) => baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'v=' + Date.now();

    const fetchCurrentData = async () => {
      console.log('[HistoryPage] fetchCurrentData: iniciando');
      for (const caminho of caminhos) {
        try {
          console.log('[HistoryPage] fetchCurrentData: tentando', caminho);
          const response = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
          console.log('[HistoryPage] fetchCurrentData: resposta', caminho, response.status);
          if (!response.ok) continue;
          let texto = await response.text();
          texto = texto.replace(/^\uFEFF/, '');
          const registros = parseCsv(texto);
          console.log('[HistoryPage] fetchCurrentData: registros extraídos', caminho, registros.length);
          if (registros.length === 0) continue;
          return registros;
        } catch (erro) {
          console.log('[HistoryPage] fetchCurrentData: falha', caminho, erro);
          continue;
        }
      }
      console.log('[HistoryPage] fetchCurrentData: nenhum arquivo atual encontrado');
      return [] as CurrentRecord[];
    };

    const loadHistory = async () => {
      try {
        console.log('[HistoryPage] loadHistory: iniciando');
        const baseUrl = import.meta.env.BASE_URL ?? './';
        const caminhosHistorico = [
          `${baseUrl}alteracoes-registros.json`,
          'alteracoes-registros.json',
          '/alteracoes-registros.json',
          '/evasao/alteracoes-registros.json',
        ];
        console.log('[HistoryPage] loadHistory: baseUrl=', baseUrl, 'caminhosHistorico=', caminhosHistorico);

        const [currentRecords, historyResponse] = await Promise.all([
          fetchCurrentData(),
          (async () => {
            let response: Response | null = null;
            for (const caminho of caminhosHistorico) {
              try {
                console.log('[HistoryPage] loadHistory: tentando histórico', caminho);
                response = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
                console.log('[HistoryPage] loadHistory: resposta histórico', caminho, response?.status);
                if (response.ok) {
                  setHistorySource(caminho);
                  return response;
                }
              } catch (erro) {
                console.log('[HistoryPage] loadHistory: falha histórico', caminho, erro);
                // tentar próximo caminho
              }
            }
            return response;
          })(),
        ]);

        if (!historyResponse || !historyResponse.ok) {
          throw new Error(`Falha ao carregar histórico (status ${historyResponse?.status ?? 'sem resposta'})`);
        }

        const payload = await historyResponse.json();
        const historyData: HistoryItem[] = Array.isArray(payload.history)
          ? payload.history
          : Array.isArray(payload)
            ? payload
            : [];
        console.log('[HistoryPage] loadHistory: historyData items', historyData.length);
        if (historyData.length > 0) {
          console.log('[HistoryPage] loadHistory: first item', historyData[0]);
        }

        const currentMap = buildCurrentRecordMap(currentRecords);
        console.log('[HistoryPage] loadHistory: currentMap size', currentMap.size);
        setHistoryRows(extractLatestChanges(historyData, currentMap));
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erro desconhecido ao carregar o histórico.');
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, []);

  const retirementCount = useMemo(() => historyRows.filter(isRetirement).length, [historyRows]);

  const summaryText = useMemo(() => {
    if (loading) return 'Carregando histórico de alterações...';
    if (error) return 'Não foi possível carregar o histórico.';
    return `Hisórico de alterações do Observatório das Evasões`;
  }, [historyRows.length, retirementCount, loading, error]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-4 sm:p-6 lg:p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-10 text-center">
          <h1 className="text-4xl md:text-5xl font-extrabold text-red-400">Histórico de Alterações</h1>
        </header>

        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6">
          <div>
            <p className="text-gray-300">{summaryText}</p>
            {historySource && !loading && !error}
          </div>
          <div className="flex flex-wrap gap-3 justify-center sm:justify-end">
            <a
              href="./index.html"
              className="inline-flex items-center px-5 py-3 rounded-lg bg-gray-800 border border-gray-700 text-sm font-semibold text-white hover:bg-gray-700 transition-colors"
            >
              Voltar ao dashboard
            </a>
          </div>
        </div>

        {loading && (
          <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">Carregando histórico de alterações...</div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-700 bg-red-950/40 p-6 text-center text-red-300">
            <strong>Erro:</strong> {error}
          </div>
        )}

        {!loading && !error && historyRows.length === 0 && (
          <div className="rounded-2xl border border-gray-800 bg-gray-900 p-8 text-center text-gray-400">
            Não há alterações de situação relevantes registradas no histórico.
          </div>
        )}

        {!loading && !error && historyRows.length > 0 && (
          <div className="overflow-x-auto rounded-3xl border border-gray-800 bg-gray-900 shadow-xl">
            <table className="min-w-full divide-y divide-gray-800 text-left">
              <thead className="bg-gray-950">
                <tr>
                  <th className="px-4 py-4 text-sm font-semibold uppercase tracking-wider text-gray-400">Data / Hora</th>
                  <th className="px-4 py-4 text-sm font-semibold uppercase tracking-wider text-gray-400">Alteração</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 bg-gray-900">
                {historyRows.map((row, index) => (
                  <tr key={`${row.masp}-${row.commitDate}-${index}`}>
                    <td className="whitespace-nowrap px-4 py-4 text-sm text-gray-300">{formatDate(row.commitDate)}</td>
                    <td className="px-4 py-4 text-sm text-gray-300">{formatDescription(row, row.currentOrgaoDestino)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPage;
