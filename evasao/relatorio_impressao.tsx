import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

type Registro = Record<string, string>;
type ListaAtiva = 'exonerados' | 'desistentes' | 'nomeados';

type LinhaRelatorio = {
  nome: string;
  dataPrincipal: string;
  publicacaoOuObservacao?: string;
  orgao: string;
};

const caminhos = (arquivo: string) => [
  `${import.meta.env.BASE_URL}data/${arquivo}`,
  `/evasao/data/${arquivo}`,
  `../data/${arquivo}`,
  `/data/${arquivo}`,
];

const parseCsv = (texto: string): Registro[] => {
  const linhas = texto.replace(/^\uFEFF/, '').split(/\r?\n/).filter((linha) => linha.trim());
  if (!linhas.length) return [];

  const parseLinha = (linha: string) => {
    const valores: string[] = [];
    let valor = '';
    let entreAspas = false;
    for (let i = 0; i < linha.length; i += 1) {
      if (linha[i] === '"') {
        if (entreAspas && linha[i + 1] === '"') {
          valor += '"';
          i += 1;
        } else {
          entreAspas = !entreAspas;
        }
      } else if (linha[i] === ';' && !entreAspas) {
        valores.push(valor);
        valor = '';
      } else {
        valor += linha[i];
      }
    }
    valores.push(valor);
    return valores;
  };

  const cabecalhos = parseLinha(linhas[0]).map((valor) => valor.trim().replace(/^\uFEFF/, ''));
  return linhas.slice(1).map((linha) => {
    const valores = parseLinha(linha);
    return Object.fromEntries(cabecalhos.map((cabecalho, indice) => [cabecalho, valores[indice]?.trim() ?? '']));
  });
};

const carregarCsv = async (arquivo: string): Promise<Registro[]> => {
  for (const caminho of caminhos(arquivo)) {
    try {
      const resposta = await fetch(`${caminho}?v=${Date.now()}`, { cache: 'no-store' });
      if (resposta.ok) return parseCsv(await resposta.text());
    } catch {
      // Tenta o próximo caminho.
    }
  }
  throw new Error(`Não foi possível carregar ${arquivo}.`);
};

const normalizar = (valor: string | undefined) => String(valor ?? '').trim().replace(/\s+/g, ' ').toUpperCase();
const numero = (valor: string | undefined) => {
  const resultado = Number(String(valor ?? '').replace(',', '.'));
  return Number.isFinite(resultado) ? resultado : null;
};
const booleano = (valor: string | undefined) => ['TRUE', '1', 'SIM'].includes(normalizar(valor));
const chaveConcurso = (concurso: string, cargo: string, modalidade: string) =>
  [concurso, cargo, modalidade].map(normalizar).join('||');

const dataBrasil = (valor: string): number => {
  const match = valor.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!match) return Number.POSITIVE_INFINITY;
  return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1])).getTime();
};

const ordenarPorData = (a: LinhaRelatorio, b: LinhaRelatorio) =>
  dataBrasil(a.dataPrincipal) - dataBrasil(b.dataPrincipal) || a.nome.localeCompare(b.nome, 'pt-BR');

const RelatorioImpressao: React.FC = () => {
  const [listaAtiva, setListaAtiva] = useState<ListaAtiva>('exonerados');
  const [dados, setDados] = useState<Registro[]>([]);
  const [aprovacoes, setAprovacoes] = useState<Registro[]>([]);
  const [concursos, setConcursos] = useState<Registro[]>([]);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    Promise.all([
      carregarCsv('dados.csv'),
      carregarCsv('aprovacoes_outros_concursos.csv'),
      carregarCsv('outros_concursos.csv'),
    ])
      .then(([dadosCarregados, aprovacoesCarregadas, concursosCarregados]) => {
        setDados(dadosCarregados);
        setAprovacoes(aprovacoesCarregadas);
        setConcursos(concursosCarregados);
      })
      .catch((error) => setErro(error instanceof Error ? error.message : 'Erro ao carregar os dados.'))
      .finally(() => setCarregando(false));
  }, []);

  const listas = useMemo(() => {
    const exonerados = dados
      .filter((registro) => normalizar(registro.SITUACAO) === 'EXONERADO')
      .map((registro) => ({
        nome: registro.NOME,
        dataPrincipal: registro.DATA_EXONERACAO,
        publicacaoOuObservacao: registro.DATA_PUBLICACAO_EXONERACAO || registro.OBSERVACAO || '—',
        orgao: registro.ORGAO_DESTINO || 'Desconhecido',
      }))
      .sort(ordenarPorData);

    const desistentes = dados
      .filter((registro) => normalizar(registro.SITUACAO) === 'DESISTENTE')
      .map((registro) => ({
        nome: registro.NOME,
        dataPrincipal: registro.DATA_NOMEACAO,
        publicacaoOuObservacao: registro.DATA_NOMEACAO_SEM_EFEITO || registro.OBSERVACAO || '—',
        orgao: registro.ORGAO_DESTINO || 'Desconhecido',
      }))
      .sort(ordenarPorData);

    const auditoresEmExercicio = new Map(
      dados
        .filter((registro) => ['EM EXERCÍCIO', 'EM EXERCICIO'].includes(normalizar(registro.SITUACAO)))
        .map((registro) => [normalizar(registro.NOME), registro]),
    );
    const concursosPorChave = new Map(concursos.map((concurso) => [
      chaveConcurso(concurso.CONCURSO, concurso.CARGO, concurso.MODALIDADE),
      concurso,
    ]));
    const nomeacoesConsolidadas = new Map<string, LinhaRelatorio>();

    for (const aprovacao of aprovacoes) {
      if (booleano(aprovacao.IGNORAR) || booleano(aprovacao.RENUNCIOU) || booleano(aprovacao.FIM_DE_FILA)) continue;
      const auditor = auditoresEmExercicio.get(normalizar(aprovacao.NOME));
      if (!auditor) continue;
      const concurso = concursosPorChave.get(chaveConcurso(aprovacao.CONCURSO, aprovacao.CARGO, aprovacao.MODALIDADE));
      if (!concurso) continue;
      const posicao = numero(aprovacao.POSICAO);
      const ultimaVagaNomeada = numero(concurso.ULTIMA_VAGA_NOMEADA);
      if (posicao == null || ultimaVagaNomeada == null || posicao > ultimaVagaNomeada) continue;

      const orgao = aprovacao.CONCURSO || concurso.CONCURSO || 'Desconhecido';
      const linha = {
        nome: auditor.NOME,
        dataPrincipal: concurso.DATA_ULTIMA_NOMEACAO || '—',
        orgao,
      };
      const chave = `${normalizar(linha.nome)}||${normalizar(orgao)}`;
      const atual = nomeacoesConsolidadas.get(chave);
      const instanteLinha = dataBrasil(linha.dataPrincipal);
      const instanteAtual = atual ? dataBrasil(atual.dataPrincipal) : Number.POSITIVE_INFINITY;
      if (!atual || (instanteLinha !== Number.POSITIVE_INFINITY && (instanteAtual === Number.POSITIVE_INFINITY || instanteLinha > instanteAtual))) {
        nomeacoesConsolidadas.set(chave, linha);
      }
    }

    return {
      exonerados,
      desistentes,
      nomeados: Array.from(nomeacoesConsolidadas.values()).sort(ordenarPorData),
    };
  }, [dados, aprovacoes, concursos]);

  const configuracoes = {
    exonerados: {
      titulo: 'Servidores exonerados',
      dataPrincipal: 'Data de exoneração',
      publicacao: 'Publicação da exoneração',
    },
    desistentes: {
      titulo: 'Servidores desistentes',
      dataPrincipal: 'Data de nomeação',
      publicacao: 'Nomeação sem efeito',
    },
    nomeados: {
      titulo: 'Servidores nomeados recentemente em outros concursos',
      dataPrincipal: 'Data da última nomeação',
      publicacao: null,
    },
  } as const;

  const configuracao = configuracoes[listaAtiva];
  const linhas = listas[listaAtiva];

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900 p-4 md:p-8">
      <div className="mx-auto max-w-7xl bg-white shadow-lg rounded-xl p-5 md:p-8 print-area">
        <header className="mb-6 border-b-2 border-slate-800 pb-4">
          <p className="text-sm font-semibold uppercase tracking-wide text-red-700">Observatório das Evasões</p>
          <h1 className="text-3xl font-bold mt-1">{configuracao.titulo}</h1>
          <p className="text-sm text-slate-600 mt-1">Auditores e Técnicos Federais de Finanças e Controle &mdash; CGU</p>
        </header>

        <div className="print-hidden mb-6 flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Selecionar lista do relatório">
            {(Object.keys(configuracoes) as ListaAtiva[]).map((lista) => (
              <button
                key={lista}
                type="button"
                onClick={() => setListaAtiva(lista)}
                className={`px-4 py-2 rounded-lg font-medium border ${listaAtiva === lista ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-800 border-slate-300 hover:bg-slate-100'}`}
              >
                {configuracoes[lista].titulo}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => window.print()}
            className="px-5 py-2 rounded-lg bg-red-700 text-white font-semibold hover:bg-red-800"
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
            <p className="mb-3 text-sm text-slate-600 total-registros">Total de registros: {linhas.length}</p>
            <div className="overflow-x-auto print-table-wrapper">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-800 text-white">
                    <th className="border border-slate-500 px-2 py-2 text-center w-12">Nº</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">Nome</th>
                    <th className="border border-slate-500 px-3 py-2 text-left">{configuracao.dataPrincipal}</th>
                    {configuracao.publicacao && (
                      <th className="border border-slate-500 px-3 py-2 text-left">{configuracao.publicacao}</th>
                    )}
                    <th className="border border-slate-500 px-3 py-2 text-left">Órgão de destino</th>
                  </tr>
                </thead>
                <tbody>
                  {linhas.map((linha, indice) => (
                    <tr key={`${linha.nome}-${linha.orgao}-${indice}`} className="even:bg-slate-100">
                      <td className="border border-slate-300 px-2 py-2 text-center">{indice + 1}</td>
                      <td className="border border-slate-300 px-3 py-2 font-medium">{linha.nome || '—'}</td>
                      <td className="border border-slate-300 px-3 py-2 whitespace-nowrap">{linha.dataPrincipal || '—'}</td>
                      {configuracao.publicacao && (
                        <td className="border border-slate-300 px-3 py-2">{linha.publicacaoOuObservacao || '—'}</td>
                      )}
                      <td className="border border-slate-300 px-3 py-2">{linha.orgao || 'Desconhecido'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </main>
  );
};

const container = document.getElementById('root');
if (container) createRoot(container).render(<RelatorioImpressao />);
