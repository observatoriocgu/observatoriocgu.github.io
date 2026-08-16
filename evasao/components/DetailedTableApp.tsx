import React, { useEffect, useMemo, useState } from 'react';

import {
  AREAS_SEM_ESPECIALIDADE,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVOS_SAIDA_DETALHADOS,
  SITUACAO_EM_EXERCICIO,
  rotuloDoConcurso,
} from '../constants';
import { RegistroAuditor, SaidasDou } from '../types';
import {
  carregarCsv,
  carregarJsonPublico,
  formatarCompetenciaLonga,
  formatarDataIsoParaBr,
} from '../lib/dados';
import {
  areaDe,
  comoRegistros,
  fontesDaSaida,
  comoDestinosDoRanking,
  mesclarFontesExternas,
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

  useEffect(() => {
    let montado = true;
    (async () => {
      try {
        // O JSON do DOU é opcional: sem ele a tabela ainda se lê, só volta a
        // parar na última competência do SIAPE. As saídas que só o DOU conhece
        // são sobrepostas às linhas de quem ainda consta como em exercício
        // (D22) — sem isto, quem saiu em agosto aparece aqui trabalhando.
        const [linhas, dou, destinos] = await Promise.all([
          carregarCsv('dados.csv'),
          carregarJsonPublico<SaidasDou>('atos_dou.json').catch(() => null),
          carregarCsv('destinos_ranking.csv').catch(() => []),
        ]);
        if (montado) {
          setRegistros(mesclarFontesExternas(
            comoRegistros(linhas),
            dou?.saidasRecentes ?? [],
            comoDestinosDoRanking(destinos),
          ));
        }
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

  useEffect(() => setLimite(PAGINA), [busca, concurso, area, unidade, situacao, motivo]);

  const visiveis = filtrados.slice(0, limite);
  // Saída atestada pelas DUAS fontes: o cadastro mostra a ausência e existe ato
  // publicado dizendo por quê. É o número que responde "quanto disto está
  // documentado em dobro" — que era o que o antigo "conferido" tentava dizer, e
  // dizia mal, porque media conferência humana, que quase nunca acontece.
  const comDuasFontes = filtrados.filter(
    (registro) => saiuDaCgu(registro) && registro.FONTE_MOTIVO
  ).length;

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

        </div>

        {!carregando && !erro && (
          <div className="mb-2 text-center text-xs text-gray-600">
            {filtrados.length.toLocaleString('pt-BR')} Auditor(es) neste recorte ·{' '}
            {filtrados.filter(saiuDaCgu).length.toLocaleString('pt-BR')} já saíram ·{' '}
            {comDuasFontes.toLocaleString('pt-BR')} com saída atestada pelo SIAPE e pelo DOU
            {visiveis.length < filtrados.length && ` · mostrando ${visiveis.length.toLocaleString('pt-BR')}`}
          </div>
        )}

        <div className="border border-black bg-white shadow-lg">
          <div className="max-h-[80vh] overflow-x-auto overflow-y-auto">
            <table className="w-full border-collapse border border-black text-[10px]">
              <thead className="sticky top-0 z-50 bg-white text-[10px] uppercase text-gray-700 shadow-sm">
                <tr>
                  {/* Duas afirmações, quatro colunas, e a ordem é a da leitura:
                      a pessoa SAIU (quando, quem atesta, qual ato) e só então
                      FOI para algum lugar (para onde, quem atesta, qual
                      documento). Enquanto a procedência da saída ficava entre o
                      órgão de destino e o ato, o selo `SIAPE` da saída parecia
                      responder pelo destino — e o destino, que pode vir do
                      ranking, parecia ter ato publicado. O motivo saiu de coluna
                      própria porque a situação já o diz: `VACÂNCIA` ao lado de
                      "Vacância (posse em outro cargo)" gastava uma coluna para
                      repetir a mesma palavra. */}
                  {[
                    'Nome',
                    'Concurso',
                    'Especialidade',
                    'Class.',
                    'Modalidade',
                    'Unidade',
                    'UF',
                    'Situação',
                    'Data de saída',
                    'Selo da saída',
                    'Ato da saída',
                    'Órgão de destino',
                    'Selo do destino',
                    'Ato do destino',
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
                    <td colSpan={14} className="border border-black px-4 py-6 text-center text-orange-600">
                      Carregando dados...
                    </td>
                  </tr>
                )}
                {erro && (
                  <tr>
                    <td colSpan={14} className="border border-black px-4 py-6 text-center text-red-700">
                      {erro}
                    </td>
                  </tr>
                )}
                {!carregando && !erro && visiveis.length === 0 && (
                  <tr>
                    <td colSpan={14} className="border border-black px-4 py-6 text-center text-gray-500">
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
                      {/* A situação é o motivo dito em uma palavra — `VACÂNCIA` é
                          "Vacância (posse em outro cargo)". O que a palavra deixa de
                          fora vai no `title`, inclusive a demissão: esta é a única
                          página com licença para nomeá-la (D18), e a coluna já
                          mostrava `DEMITIDO`. */}
                      <Celula
                        className="whitespace-nowrap"
                        titulo={saiu ? motivoDetalhado(registro) : undefined}
                      >
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
                      <Celula className="whitespace-nowrap">
                        {registro.MES_SAIDA ? formatarCompetenciaLonga(registro.MES_SAIDA) : '-'}
                      </Celula>
                      {/* Quem atesta que a pessoa SAIU — e nada mais. Quem está na CGU
                          não tem saída para sustentar, e por isso a célula fica vazia:
                          um `SIAPE` aqui diria que existe uma saída atestada pelo
                          cadastro onde não existe saída nenhuma. */}
                      <Celula>
                        {saiu ? <SelosDaLinha fontes={fontesDaSaida(registro)} compacto tema="claro" /> : '-'}
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
                      {/* O destino tem procedência PRÓPRIA, e ela não é a da saída: os
                          selos da esquerda atestam que a pessoa saiu, não para onde foi.
                          Enquanto o destino só vinha do DOU dava para deduzir; desde a
                          D24 ele pode vir do Ranking dos Concursos, que é indício e não
                          ato — e é por isso que o selo dele ganhou coluna própria, em vez
                          de continuar colado ao nome do órgão. */}
                      <Celula className="whitespace-nowrap">{registro.ORGAO_DESTINO || '-'}</Celula>
                      <Celula>
                        {registro.ORGAO_DESTINO && registro.FONTE_DESTINO ? (
                          <SeloFonte fonte={registro.FONTE_DESTINO} compacto tema="claro" />
                        ) : (
                          '-'
                        )}
                      </Celula>
                      {/* Nem todo destino tem ATO: o do ranking é a ficha de aprovações
                          da pessoa, uma consulta que qualquer um repete no navegador. O
                          rótulo sai de `Selos.tsx`, para que a tabela não chame de "ato"
                          o que não é. */}
                      <Celula>
                        {registro.ORGAO_DESTINO && registro.URL_DESTINO ? (
                          <a
                            href={registro.URL_DESTINO}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={tituloDoLinkDeDestino(
                              registro.FONTE_DESTINO,
                              registro.NOME,
                              registro.ORGAO_DESTINO
                            )}
                            className="text-blue-700 underline hover:text-blue-900"
                          >
                            {rotuloDoLinkDeDestino(registro.FONTE_DESTINO, registro.DATA_DESTINO)}
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
          tirá-la. A situação resume o motivo da saída, como o ato do DOU o diz — passe o cursor sobre ela para ler o
          motivo por extenso.
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
