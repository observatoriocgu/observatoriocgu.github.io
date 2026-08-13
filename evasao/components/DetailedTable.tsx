import React, { useState, useMemo } from 'react';

interface DetailedTableProps {
  data: any[];
  estaCarregando?: boolean;
  dadosAprovacoesOutrosConcursos?: any[];
  dadosOutrosConcursos?: any[];
}

const DetailedTable: React.FC<DetailedTableProps> = ({ 
  data, 
  estaCarregando = false,
  dadosAprovacoesOutrosConcursos = [],
  dadosOutrosConcursos = []
}) => {
  const [areaSelecionada, setAreaSelecionada] = useState<string>('TODAS');

  // Função para normalizar nomes para comparação
  const normalizarNomeChave = (valor: string | null | undefined) => 
    String(valor ?? '').trim().replace(/\s+/g, ' ').toUpperCase();

  const parseNumber = (valor: string | number | null | undefined): number | null => {
    if (valor === null || valor === undefined || valor === '') return null;
    const texto = String(valor).trim().replace(/\./g, '').replace(',', '.');
    const numero = Number(texto);
    return Number.isFinite(numero) ? numero : null;
  };

  const analisarDataBrasil = (valor: string | null | undefined): Date | null => {
    if (!valor) return null;
    const match = String(valor).trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!match) return null;
    const dia = Number(match[1]);
    const mes = Number(match[2]) - 1;
    const ano = Number(match[3]);
    const data = new Date(ano, mes, dia);
    if (Number.isNaN(data.getTime())) return null;
    data.setHours(0, 0, 0, 0);
    return data;
  };

  const concursoEstaVencido = (dataVencimento: string | null | undefined): boolean => {
    const vencimento = analisarDataBrasil(dataVencimento ?? '');
    if (!vencimento) return false;
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    return vencimento.getTime() < hoje.getTime();
  };

  const construirChaveTripla = (concurso: string, cargo: string, modalidade: string) =>
    `${String(concurso ?? '').trim().toLowerCase()}|${String(cargo ?? '').trim().toLowerCase()}|${String(modalidade ?? '').trim().toLowerCase()}`;

  // Verificar quais órgãos/locais o auditor está aguardando nomeação em outros concursos
  const getAguardandoNomeacaoPorOrgao = (nome?: string): string[] => {
    if (!nome || dadosAprovacoesOutrosConcursos.length === 0 || dadosOutrosConcursos.length === 0) return [];

    const nomeNormalizado = normalizarNomeChave(nome);
    const mapaConcursosInfo = new Map<string, any>();
    for (const concursoRaw of dadosOutrosConcursos) {
      const chave = construirChaveTripla(
        concursoRaw['CONCURSO'] || concursoRaw['concurso'] || '',
        concursoRaw['CARGO'] || concursoRaw['cargo'] || '',
        concursoRaw['MODALIDADE'] || concursoRaw['modalidade'] || '',
      );
      if (!mapaConcursosInfo.has(chave)) {
        mapaConcursosInfo.set(chave, concursoRaw);
      }
    }

    const orgaos = new Set<string>();

    for (const aprovacao of dadosAprovacoesOutrosConcursos) {
      const nomeAprovacao = normalizarNomeChave(aprovacao['NOME'] || aprovacao['Nome'] || '');
      if (nomeAprovacao !== nomeNormalizado) continue;

      const ignorar = String(aprovacao['IGNORAR'] || aprovacao['Ignorar'] || '').toLowerCase() === 'true';
      const renunciou = String(aprovacao['RENUNCIOU'] || aprovacao['RENUNCIOU?'] || '').toLowerCase() === 'true';
      if (ignorar || renunciou) continue;

      const concurso = String(aprovacao['CONCURSO'] || aprovacao['Concurso'] || '').trim();
      const cargo = String(aprovacao['CARGO'] || aprovacao['Cargo'] || '').trim();
      const modalidade = String(aprovacao['MODALIDADE'] || aprovacao['Modalidade'] || '').trim();
      const concursoRelacionado = mapaConcursosInfo.get(construirChaveTripla(concurso, cargo, modalidade));
      if (!concursoRelacionado) continue;

      const posicaoNumero = parseNumber(aprovacao['POSICAO'] || aprovacao['Posicao'] || '');
      const numeroVagas = parseNumber(concursoRelacionado['NUMERO_VAGAS'] || concursoRelacionado['NUMERO VAGAS'] || '');
      const ultimaVagaNomeada = parseNumber(concursoRelacionado['ULTIMA_VAGA_NOMEADA'] || concursoRelacionado['ULTIMA VAGA NOMEADA'] || '');
      const fimDeFila = String(aprovacao['FIM_DE_FILA'] || aprovacao['FIM DE FILA'] || '').toLowerCase() === 'true';
      const tipoAprovacao = fimDeFila
        ? 'Fim de Fila'
        : (
            posicaoNumero != null &&
            ultimaVagaNomeada != null &&
            ultimaVagaNomeada > 0 &&
            posicaoNumero <= ultimaVagaNomeada
          )
          ? 'Nomeado'
          : (
              posicaoNumero != null &&
              numeroVagas != null &&
              numeroVagas > 0 &&
              posicaoNumero <= numeroVagas
            )
            ? 'Aprovado nas vagas'
            : 'Cadastro de Reservas';

      if (concursoEstaVencido(concursoRelacionado['DATA_VENCIMENTO'] || concursoRelacionado['DATA VENCIMENTO'] || '') && tipoAprovacao !== 'Nomeado') {
        continue;
      }

      if (concurso) {
        orgaos.add(concurso);
      }
    }

    return Array.from(orgaos).sort((a, b) => a.localeCompare(b));
  };

  const estaAguardandoNomeacao = (nome?: string): boolean => getAguardandoNomeacaoPorOrgao(nome).length > 0;

  // Debug: log dos dados recebidos
  console.log('DetailedTable data:', data);
  console.log('Data length:', data?.length);

  // Lista de áreas únicas
  const areas = useMemo(() => {
    if (!data || data.length === 0) return ['TODAS'];
    const uniqueAreas = Array.from(new Set(data.map(item => item['ÁREA'] || item['AREA'] || 'Outros')));
    console.log('Areas found:', uniqueAreas);
    console.log('Selected area:', areaSelecionada);
    console.log('Is VETERANO selected:', areaSelecionada === 'VETERANO');
    return ['TODAS', ...uniqueAreas.sort()];
  }, [data]);

  // Filtrar dados pela área selecionada e ordenar por posição do concurso
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) {
      console.log('No data available for filtering');
      return [];
    }
    
    let filtered = areaSelecionada === 'TODAS' 
      ? data 
      : data.filter(item => (item['ÁREA'] || item['AREA'] || 'Outros') === areaSelecionada);
    
    console.log('Filtered data length:', filtered.length);
    console.log('Sample filtered item:', filtered[0]);
    
    // Ordenar por posição do concurso
    return filtered.sort((a, b) => {
      const posA = parseInt(a['POSICAO_CONCURSO'] || a['POSICAO CONCURSO'] || '0');
      const posB = parseInt(b['POSICAO_CONCURSO'] || b['POSICAO CONCURSO'] || '0');
      return posA - posB;
    });
  }, [data, areaSelecionada]);

  // Função para determinar a cor da linha baseada no status
  const getRowColor = (situacao: string, index: number) => {
    const baseColors = {
      'EM EXERCÍCIO': 'bg-green-900/30',
      'EXONERADO': 'bg-red-900/30',
      'DESISTENTE': 'bg-yellow-900/30',
      'INAPTO ADMISSIONAL': 'bg-purple-900/30',
      'APOSENTADO': 'bg-purple-400/50',
      'AFASTAMENTO PRELIMINAR À APOSENTADORIA': 'bg-purple-300/40',
      '???': 'bg-gray-900/30',
    };

    const alternateColors = {
      'EM EXERCÍCIO': 'bg-green-800/20',
      'EXONERADO': 'bg-red-800/20',
      'DESISTENTE': 'bg-yellow-800/20',
      'INAPTO ADMISSIONAL': 'bg-purple-800/20',
      'APOSENTADO': 'bg-purple-300/40',
      'AFASTAMENTO PRELIMINAR À APOSENTADORIA': 'bg-purple-200/30',
      '???': 'bg-gray-800/20',
    };

    const status = situacao?.toUpperCase() || '-';
    const isEven = index % 2 === 0;
    
    return isEven ? (baseColors[status] || baseColors['???']) : (alternateColors[status] || alternateColors['???']);
  };

  // Função para determinar a cor do texto do status
  const getStatusColor = (situacao: string) => {
    const colors = {
      'EM EXERCÍCIO': 'text-green-400',
      'EXONERADO': 'text-red-400',
      'DESISTENTE': 'text-yellow-400',
      'INAPTO ADMISSIONAL': 'text-purple-400',
      'APOSENTADO': 'text-purple-100',
      'AFASTAMENTO PRELIMINAR À APOSENTADORIA': 'text-purple-200',
      '???': 'text-gray-400',
    };

    const status = situacao?.toUpperCase() || '???';
    return colors[status] || colors['???'];
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-4 sm:p-6 lg:p-8 pt-20">
      <div className="max-w-7xl mx-auto">
        <header className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-extrabold text-red-600 mb-2 drop-shadow-lg">
            Tabela Detalhada de Candidatos
          </h1>
          <p className="text-lg text-amber-400 font-medium">
            Auditores e Técnicos Federais de Finanças e Controle &mdash; CGU
          </p>
        </header>

        {/* Seletor de Área */}
        <div className="mb-6 flex flex-col items-center">
          <div className="text-sm text-gray-300 mb-3">Filtrar por área:</div>
          <div className="flex flex-wrap gap-2 justify-center">
            {areas.map(area => (
              <button
                key={area}
                onClick={() => setAreaSelecionada(area)}
                className={`px-4 py-2 rounded text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-400 ${
                  areaSelecionada === area 
                    ? 'bg-red-600 text-white shadow-lg' 
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700'
                }`}
              >
                {area}
              </button>
            ))}
          </div>
        </div>

        {/* Informações do filtro */}
        <div className="mb-4 text-center text-gray-400 text-sm">
          {estaCarregando ? (
            <span className="text-yellow-400">Carregando dados...</span>
          ) : data && data.length > 0 ? (
            <>Mostrando {filteredData.length} candidatos {areaSelecionada !== 'TODAS' && `da área ${areaSelecionada}`}</>
          ) : (
            <span className="text-red-400">Nenhum dado encontrado</span>
          )}
        </div>

        {/* Tabela */}
        <div className="bg-gray-900 rounded-xl shadow-2xl border border-gray-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-300 uppercase text-xs">
                <tr>
                  {(() => {
                    console.log('Rendering header for area:', areaSelecionada);
                    return areaSelecionada === 'VETERANO';
                  })() ? (
                    // Cabeçalho para área VETERANO
                    <>
                      <th className="px-3 py-3 text-left font-semibold">Nome</th>
                      <th className="px-3 py-3 text-left font-semibold">Área</th>
                      <th className="px-3 py-3 text-left font-semibold">Situação</th>
                      <th className="px-3 py-3 text-left font-semibold">Órgão</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Inatividade</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Pub. Inatividade</th>
                      <th className="px-3 py-3 text-left font-semibold">Observação</th>
                      <th className="px-3 py-3 text-left font-semibold">Aguardando nomeação</th>
                    </>
                  ) : (
                    // Cabeçalho padrão para outras áreas
                    <>
                      <th className="px-3 py-3 text-left font-semibold">Posição</th>
                      <th className="px-3 py-3 text-left font-semibold">Nome</th>
                      <th className="px-3 py-3 text-left font-semibold">Área</th>
                      <th className="px-3 py-3 text-left font-semibold">PCD</th>
                      <th className="px-3 py-3 text-left font-semibold">Situação</th>
                      <th className="px-3 py-3 text-left font-semibold">Órgão</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Nomeação</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Exoneração</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Pub. Exoneração</th>
                      <th className="px-3 py-3 text-left font-semibold">Data Nomeação s/ Efeito</th>
                      <th className="px-3 py-3 text-left font-semibold">Observação</th>
                      <th className="px-3 py-3 text-left font-semibold">Aguardando nomeação</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {estaCarregando ? (
                  <tr>
                    <td colSpan={areaSelecionada === 'VETERANO' ? 8 : 12} className="px-6 py-8 text-center text-yellow-400">
                      <div className="flex items-center justify-center space-x-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-yellow-400"></div>
                        <span>Carregando dados...</span>
                      </div>
                    </td>
                  </tr>
                ) : filteredData.length === 0 ? (
                  <tr>
                    <td colSpan={areaSelecionada === 'VETERANO' ? 8 : 12} className="px-6 py-8 text-center text-gray-400">
                      {data && data.length > 0 
                        ? `Nenhum candidato encontrado para a área ${areaSelecionada}`
                        : 'Nenhum dado disponível. Verifique se o arquivo dados.csv foi carregado.'
                      }
                    </td>
                  </tr>
                ) : (
                  filteredData.map((item, index) => (
                    <tr 
                      key={`${item['INSCRICAO'] || index}`}
                      className={`${getRowColor(item['SITUACAO'], index)} hover:bg-gray-700/50 transition-colors duration-150`}
                    >
                      {areaSelecionada === 'VETERANO' ? (
                        // Layout para área VETERANO
                        <>
                          <td className="px-3 py-2 font-medium text-gray-200">
                            {item['NOME'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-cyan-400">
                            {item['AREA'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            <span className={`font-medium ${getStatusColor(item['SITUACAO'])}`}>
                              {item['SITUACAO'] || '???'}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            {item['ORGAO_DESTINO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_INATIVIDADE'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_PUBLICACAO_INATIVIDADE'] ||'-'}
                          </td>
                          <td className="px-3 py-2 text-gray-400 text-xs max-w-xs truncate" title={item['OBSERVACAO'] || ''}>
                            {item['OBSERVACAO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-normal">
                            {(() => {
                              const orgaos = item['SITUACAO'] === 'EM EXERCÍCIO' ? getAguardandoNomeacaoPorOrgao(item['NOME']) : [];
                              return orgaos.length > 0 ? (
                                <span className="bg-yellow-500 text-black px-2 py-1 rounded text-xs font-medium whitespace-normal">
                                  {orgaos.join(', ')}
                                </span>
                              ) : (
                                '-'
                              );
                            })()}
                          </td>
                        </>
                      ) : (
                        // Layout padrão para outras áreas
                        <>
                          <td className="px-3 py-2 whitespace-nowrap font-medium text-amber-400">
                            {item['POSICAO_CONCURSO'] || '-'}
                          </td>
                          <td className="px-3 py-2 font-medium text-gray-200">
                            {item['NOME'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-cyan-400">
                            {item['AREA'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-center">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              (item['PCD'] || '').toUpperCase() === 'SIM' 
                                ? 'bg-blue-900/50 text-blue-300' 
                                : 'bg-gray-800/50 text-gray-400'
                            }`}>
                              {item['PCD'] || 'NÃO'}
                            </span>
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            <span className={`font-medium ${getStatusColor(item['SITUACAO'] || item['SITUAÇÃO'])}`}>
                              {item['SITUACAO'] || item['SITUAÇÃO'] || '???'}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            {item['ORGAO_DESTINO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_NOMEACAO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_EXONERACAO'] || item['DATA EXONERACAO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_PUBLICACAO_EXONERACAO'] || item['DATA PUBLICACAO EXONERAÇÃO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                            {item['DATA_NOMEACAO_SEM_EFEITO'] || item['DATA NOMEACAO SEM EFEITO'] || '-'}
                          </td>
                          <td className="px-3 py-2 text-gray-400 text-xs max-w-xs truncate" title={item['OBSERVACAO'] || ''}>
                            {item['OBSERVACAO'] || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-normal">
                            {(() => {
                              const orgaos = item['SITUACAO'] === 'EM EXERCÍCIO' ? getAguardandoNomeacaoPorOrgao(item['NOME']) : [];
                              return orgaos.length > 0 ? (
                                <span className="bg-yellow-500 text-black px-2 py-1 rounded text-xs font-medium whitespace-normal">
                                  {orgaos.join(', ')}
                                </span>
                              ) : (
                                '-'
                              );
                            })()}
                          </td>
                        </>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Estatísticas do filtro */}
        <div className="mt-6 text-center text-sm text-gray-400">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 max-w-2xl mx-auto">
            {Object.entries(
              filteredData.reduce((acc, item) => {
                const status = item['SITUACAO'] || '???';
                acc[status] = (acc[status] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            ).map(([status, count]) => (
              <div key={status} className="text-center">
                <div className={`text-lg font-bold ${getStatusColor(status)}`}>
                  {count}
                </div>
                <div className="text-xs text-gray-500">
                  {status}
                </div>
              </div>
            ))}
          </div>
        </div>

        <footer className="text-center mt-8 text-gray-500 text-sm">
          <p>&copy; {new Date().getFullYear()} Observatório das Evasões. Dados extraídos do Diário Oficial da União (DOU).</p>
        </footer>
      </div>
    </div>
  );
};

export default DetailedTable;