import React, { useState, useEffect } from 'react';
import CounterCard from './components/CounterCard';
import EvasionTable from './components/EvasionTable';
import EvasionChart from './components/EvasionChart';
import CollaborationForm from './components/CollaborationForm';
import AnnouncementModal from './components/AnnouncementModal';
import AprovadosOutrosConcursosTable from './components/AprovadosOutrosConcursosTable';
import { DATA_INICIO_OBSERVACAO } from './constants';
import { DadosDestinoEvasao } from './types';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faCalendarAlt, faUsers, faPersonShelter, faHourglassEnd } from '@fortawesome/free-solid-svg-icons';

type RecentChange = {
  key: string;
  commitDate: string;
  nome: string;
  fromSituacao: string;
  toSituacao: string;
  orgaoDestino?: string | null;
};

type TipoAprovacao = 'Nomeado' | 'Aprovado nas vagas' | 'Cadastro de Reservas' | 'Fim de Fila';

type AprovacaoOutroConcursoRaw = Record<string, string | null>;

type OutroConcursoRaw = Record<string, string | null>;

type AprovacaoOutroConcursoNormalizada = {
  nome: string;
  concurso: string;
  cargo: string;
  modalidade: string;
  posicao: string;
  ignorar: boolean;
  renunciou: boolean;
  fimDeFila: boolean;
  observacao: string;
};

type OutroConcursoNormalizado = {
  concurso: string;
  cargo: string;
  modalidade: string;
  numeroVagas: number | null;
  dataHomologacao: string;
  ultimaVagaNomeada: number | null;
  dataVencimento: string;
  prorrogavel: boolean;
  observacao: string;
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

const buildCurrentRecordMap = (records: any[]) => {
  const map = new Map<string, any>();
  for (const record of records) {
    const key = normalizeKey(pickFirstNonEmpty(record['INSCRICAO'], record['MASP'], record['HGV-0'], record['NOME']));
    if (!key) continue;
    map.set(key, record);
  }
  return map;
};

const getCurrentOrgaoDestino = (record: any): string | null => {
  const destino = String(record?.['ORGAO_DESTINO'] ?? '').trim();
  return destino || null;
};

const normalizarNomeChave = (valor: string | null | undefined) => String(valor ?? '').trim().replace(/\s+/g, ' ').toUpperCase();

const normalizarTexto = (valor: string | null | undefined) => String(valor ?? '').trim();

const analisarCsvSeparadoPorPontoVirgula = (texto: string) => {
  const linhas = texto.split(/\r?\n/).filter(l => l.trim() !== '');
  if (linhas.length === 0) return [];

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

  const cabecalhos = analisarLinha(linhas[0]).map(coluna => coluna.trim());
  const registros: Record<string, string | null>[] = [];

  for (let i = 1; i < linhas.length; i++) {
    const partes = analisarLinha(linhas[i]);
    while (partes.length < cabecalhos.length) partes.push('');
    const item: Record<string, string | null> = {};
    for (let j = 0; j < cabecalhos.length; j++) {
      item[cabecalhos[j]] = partes[j] ? partes[j].trim() : null;
    }
    registros.push(item);
  }

  return registros;
};

const parseBoolean = (valor: string | null | undefined) => {
  const normalizado = String(valor ?? '').trim().toLowerCase();
  return ['true', '1', 'sim', 'yes'].includes(normalizado);
};

const parseNumber = (valor: string | null | undefined): number | null => {
  const texto = normalizarTexto(valor);
  if (!texto) return null;
  const somenteDigitos = texto.replace(/[^\d,.-]/g, '').replace(',', '.');
  const numero = Number(somenteDigitos);
  return Number.isFinite(numero) ? numero : null;
};

const normalizarLinhaAprovacao = (linha: AprovacaoOutroConcursoRaw): AprovacaoOutroConcursoNormalizada | null => {
  const nome = normalizarTexto(pickFirstNonEmpty(linha['NOME'], linha['Nome'], linha['NOME_APROVADO'], linha['Nome aprovado']));
  let concursoOriginal = normalizarTexto(pickFirstNonEmpty(linha['CONCURSO'], linha['Concurso']));
  if (!nome || !concursoOriginal) return null;

  let ignorar = parseBoolean(pickFirstNonEmpty(linha['IGNORAR'], linha['Ignorar']));
  if (concursoOriginal.startsWith('*')) {
    ignorar = true;
    concursoOriginal = concursoOriginal.slice(1).trim();
  }

  const concurso = concursoOriginal.replace(/\s*\(CR\)\s*$/i, '').trim();
  if (!concurso) return null;

  return {
    nome,
    concurso,
    cargo: normalizarTexto(pickFirstNonEmpty(linha['CARGO'], linha['Cargo'])),
    modalidade: normalizarTexto(pickFirstNonEmpty(linha['MODALIDADE'], linha['Modalidade'])) || 'Ampla concorrencia',
    posicao: normalizarTexto(pickFirstNonEmpty(linha['POSICAO'], linha['POSIÇÃO'], linha['POSICAO_CANDIDATO'], linha['POSIÇÃO CANDIDATO'])),
    ignorar,
    renunciou: parseBoolean(pickFirstNonEmpty(linha['RENUNCIOU'], linha['RENUNCIOU?'], linha['RENUNCIOU_OUTRO_CONCURSO'])),
    fimDeFila: parseBoolean(pickFirstNonEmpty(linha['FIM_DE_FILA'], linha['FIM DE FILA'])),
    observacao: normalizarTexto(pickFirstNonEmpty(linha['OBSERVAÇÃO'], linha['OBSERVACAO'], linha['OBSERVAÇÃO APROVAÇÃO'], linha['OBSERVACAO APROVACAO'])),
  };
};

const normalizarLinhaOutroConcurso = (linha: OutroConcursoRaw): OutroConcursoNormalizado | null => {
  const concurso = normalizarTexto(pickFirstNonEmpty(linha['CONCURSO'], linha['Concurso']));
  const cargo = normalizarTexto(pickFirstNonEmpty(linha['CARGO'], linha['Cargo']));
  const modalidade = normalizarTexto(pickFirstNonEmpty(linha['MODALIDADE'], linha['Modalidade']));

  if (!concurso || !cargo || !modalidade) return null;

  return {
    concurso,
    cargo,
    modalidade,
    numeroVagas: parseNumber(pickFirstNonEmpty(linha['NUMERO_VAGAS'], linha['NÚMERO_VAGAS'])),
    dataHomologacao: normalizarTexto(pickFirstNonEmpty(linha['DATA_HOMOLOGACAO'], linha['DATA HOMOLOGACAO'], linha['DATA_HOMOLOGAÇÃO'], linha['DATA HOMOLOGAÇÃO'])),
    ultimaVagaNomeada: parseNumber(pickFirstNonEmpty(linha['ULTIMA_VAGA_NOMEADA'], linha['ÚLTIMA_VAGA_NOMEADA'])),
    dataVencimento: normalizarTexto(pickFirstNonEmpty(linha['DATA_VENCIMENTO'], linha['DATA VENCIMENTO'])),
    prorrogavel: parseBoolean(pickFirstNonEmpty(linha['PRORROGAVEL'], linha['PRORROGÁVEL'])),
    observacao: normalizarTexto(pickFirstNonEmpty(linha['OBSERVACAO'], linha['OBSERVAÇÃO'])),
  };
};

const construirChaveTripla = (concurso: string, cargo: string, modalidade: string) => {
  return [normalizeKey(concurso), normalizeKey(cargo), normalizeKey(modalidade)].join('||');
};

/**
 * Saídas de AFFC da CGU publicadas no DOU, geradas por
 * `evasao/scripts/dou_saidas_affc.py`. O JSON guarda datas, nunca a contagem de
 * dias — quem conta é o navegador, para o card não congelar no dia do crawler.
 */
interface EventoSaidaDou {
  tipo: 'vacancia' | 'aposentadoria' | 'exoneracao';
  rotulo: string;
  titulo: string;
  dataPublicacao: string; // AAAA-MM-DD
  urlDou: string;
  arquivo: string | null;
}

interface SaidasDou {
  geradoEm: string;
  dataMaisRecente: string;
  tipoMaisRecente: string;
  eventos: EventoSaidaDou[];
}

const TIPOS_SAIDA_DOU: Array<{ tipo: EventoSaidaDou['tipo']; rotuloCurto: string }> = [
  { tipo: 'vacancia', rotuloCurto: 'Vacância' },
  { tipo: 'aposentadoria', rotuloCurto: 'Aposentadoria' },
  { tipo: 'exoneracao', rotuloCurto: 'Exoneração' },
];

const diasDesde = (dataIso: string): number | null => {
  const [ano, mes, dia] = dataIso.split('-').map(Number);
  if (!ano || !mes || !dia) return null;
  // Meio-dia UTC dos dois lados: evita que o fuso do Brasil jogue a conta um dia
  // para trás ou para frente.
  const evento = Date.UTC(ano, mes - 1, dia, 12);
  const agora = new Date();
  const hoje = Date.UTC(agora.getFullYear(), agora.getMonth(), agora.getDate(), 12);
  return Math.max(0, Math.round((hoje - evento) / 86400000));
};

const formatarDataBr = (dataIso: string): string => {
  const [ano, mes, dia] = dataIso.split('-');
  return `${dia}/${mes}/${ano}`;
};

const App: React.FC = () => {
  const [diasDesdeUltimaEvasao, setDiasDesdeUltimaEvasao] = useState<number | null>(null);
  const [saidasDou, setSaidasDou] = useState<SaidasDou | null>(null);
  const [erroSaidasDou, setErroSaidasDou] = useState<string | null>(null);

  // Saídas de AFFC no DOU — alimenta o card "dias sem perder um Auditor".
  useEffect(() => {
    let montado = true;
    const base = (import.meta as any).env?.BASE_URL ?? './';
    const caminhos = [
      `${base}dias_sem_perder_affc.json`,
      'dias_sem_perder_affc.json',
      '/evasao/dias_sem_perder_affc.json',
    ];

    (async () => {
      for (const caminho of caminhos) {
        try {
          const resposta = await fetch(`${caminho}?v=${Date.now()}`);
          if (!resposta.ok) continue;
          const dados = (await resposta.json()) as SaidasDou;
          if (!dados?.dataMaisRecente) continue;
          if (montado) {
            setSaidasDou(dados);
            setErroSaidasDou(null);
          }
          return;
        } catch {
          // tenta o próximo caminho
        }
      }
      if (montado) setErroSaidasDou('Não foi possível carregar as saídas do DOU.');
    })();

    return () => {
      montado = false;
    };
  }, []);

  const [dadosBrutos, setDadosBrutos] = useState<any[]>([]);
  const [dadosAprovacoesOutrosConcursos, setDadosAprovacoesOutrosConcursos] = useState<AprovacaoOutroConcursoRaw[]>([]);
  const [dadosOutrosConcursos, setDadosOutrosConcursos] = useState<OutroConcursoRaw[]>([]);
  const [recentChanges, setRecentChanges] = useState<RecentChange[]>([]);
  const [recentChangesError, setRecentChangesError] = useState<string | null>(null);

  const [dataUltimaEvasao, setDataUltimaEvasao] = useState<Date | null>(null);
  const [areaSelecionada, setAreaSelecionada] = useState<string>('TODAS');
  const [estaCarregando, setEstaCarregando] = useState(true);
  const [mostrarPorUnidade, setMostrarPorUnidade] = useState(false);

  // helper para parsear datas no formato DD/MM/YYYY
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

  // Função para calcular diferença em dias
  const calcularDiferencaDias = (dataFim: Date, dataInicio: Date): number => {
    const diferencaEmMs = dataFim.getTime() - dataInicio.getTime();
    return Math.floor(diferencaEmMs / (1000 * 3600 * 24));
  };

  const formatCommitDate = (dateString: string | undefined | null): string => {
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

  const normalizeSituacao = (valor: string | null | undefined) => {
    const situacao = String(valor ?? '').trim().toUpperCase();
    if (situacao === 'EXONERAÇÃO' || situacao === 'EXONERACAO') return 'EXONERADO';
    return situacao;
  };

  const formatRecentChangeDescription = (change: RecentChange): React.ReactNode => {
    const situacao = normalizeSituacao(change.toSituacao);
    const pessoa = <strong>{change.nome}</strong>;
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

    if (change.orgaoDestino) {
      description = <>{description} Órgão de destino: <strong>{change.orgaoDestino}</strong>.</>;
    }

    return description;
  };

  useEffect(() => {
    if (dadosBrutos.length === 0 || recentChanges.length === 0) return;

    const currentMap = buildCurrentRecordMap(dadosBrutos);
    let changed = false;

    const updatedChanges = recentChanges.map(change => {
      const current = currentMap.get(change.key);
      const currentDestino = current ? getCurrentOrgaoDestino(current) : null;
      const destino = currentDestino || change.orgaoDestino || null;

      if (destino !== change.orgaoDestino) {
        changed = true;
        return { ...change, orgaoDestino: destino };
      }
      return change;
    });

    if (changed) {
      setRecentChanges(updatedChanges);
    }
  }, [dadosBrutos, recentChanges]);

  // diasDesdeUltimaEvasao será calculado apenas após carregamento dos dados
  useEffect(() => {
    if (!estaCarregando) {
      const hoje = new Date();
      const dataParaCalculo = dataUltimaEvasao ?? DATA_INICIO_OBSERVACAO;
      const diferencaEmDias = calcularDiferencaDias(hoje, dataParaCalculo);
      setDiasDesdeUltimaEvasao(diferencaEmDias);
    }
  }, [dataUltimaEvasao, estaCarregando]);

  // Ao montar, tentamos carregar `dados.csv` de alguns caminhos possíveis e parseá-lo.
  useEffect(() => {
    let montado = true;

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

    const analisarCsv = (texto: string) => {
      // Parser robusto para CSV com separador ';' e suporte a campos entre aspas duplas.
      const linhas = texto.split(/\r?\n/).filter(l => l.trim() !== '');
      if (linhas.length === 0) return [];

      const analisarLinha = (linha: string) => {
        const partes: string[] = [];
        let atual = '';
        let entreAspas = false;
        for (let i = 0; i < linha.length; i++) {
          const caractere = linha[i];
          if (caractere === '"') {
            // escape de aspas duplas "" dentro de campo
            if (entreAspas && linha[i + 1] === '"') {
              atual += '"';
              i++; // pular a segunda aspas
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

      const linhaCabecalho = linhas[0];
      const cabecalhos = analisarLinha(linhaCabecalho).map(coluna => coluna.trim());
      const linhasProcessadas: any[] = [];

      for (let i = 1; i < linhas.length; i++) {
        const linha = linhas[i];
        const partes = analisarLinha(linha);
        // garantir que temos o mesmo número de colunas: preencher com '' quando faltar
        while (partes.length < cabecalhos.length) partes.push('');
        const objeto: Record<string, string> = {};
        for (let j = 0; j < cabecalhos.length; j++) {
          objeto[cabecalhos[j]] = partes[j] ? partes[j].trim() : null;
        }
        linhasProcessadas.push(objeto);
      }
      return linhasProcessadas;
    };

    async function tryLoad() {
      const criarUrlSemCache = (baseUrl: string) => baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'v=' + Date.now();
      for (const caminho of caminhos) {
        try {
          const resposta = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
          if (!resposta.ok) continue;
          let textoConteudo = await resposta.text();
          // remover BOM se presente
          textoConteudo = textoConteudo.replace(/^\uFEFF/, '');
          // log do caminho e tamanho do conteúdo para depuração
          // eslint-disable-next-line no-console
          console.debug('carregado', caminho, 'tamanho', textoConteudo.length);
          const dadosParsed = analisarCsv(textoConteudo);

          if ((!Array.isArray(dadosParsed) || dadosParsed.length === 0) && textoConteudo.trim().length > 0) {
            // se parse devolveu vazio, registrar um trecho do texto para ajudar depurar
            // eslint-disable-next-line no-console
            console.warn('parseCsv retornou array vazio para', caminho, 'trecho:', textoConteudo.slice(0, 400));
          }
          if (!Array.isArray(dadosParsed) || dadosParsed.length === 0) {
            console.warn('dados.csv não tem formato esperado (array) em', caminho);
            continue;
          }

          // Dados foram carregados com sucesso

          // Determinar última data de publicação presente nos registros
          let ultimaData: Date | null = null;
          
          for (const rec of dadosParsed) {
            const situacao = rec['SITUACAO'];
            let dRaw: string | null = null;
            
            if (situacao === 'EXONERADO' || situacao === 'DESISTENTE') {
              dRaw = rec['DATA_PUBLICACAO_EXONERACAO'] ?? null;
            } else if (situacao === 'APOSENTADO' || situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA') {
              dRaw = rec['DATA_PUBLICACAO_INATIVIDADE'] ?? null;
            }
            
            const dataAnalisada = analisarDataBrasil(dRaw);
            if (dataAnalisada && (!ultimaData || dataAnalisada.getTime() > ultimaData.getTime())) {
              ultimaData = dataAnalisada;
            }
          }

          if (montado) {
            // Expor os dados lidos para depuração no console do navegador
            try {
              (window as any).__TODOS_RAW = dadosParsed;
            } catch (e) {
              // ignorar se não puder escrever em window
            }


            setDadosBrutos(dadosParsed);
            setDataUltimaEvasao(ultimaData ?? null);
            setEstaCarregando(false);
          }

          return;
        } catch (erro) {
          // tentar próximo caminho
          // eslint-disable-next-line no-console
          console.debug('Falha ao carregar', caminho, erro);
        }
      }

      // nenhum caminho funcionou — manter dados embutidos
      // eslint-disable-next-line no-console
      console.warn('Não foi possível carregar dados.csv; usando dados internos.');
      setEstaCarregando(false);
    }

    tryLoad();

    return () => { montado = false; };
  }, []);

  useEffect(() => {
    let montado = true;

    const caminhos = [
      '/data/aprovacoes_outros_concursos.csv',
      '/evasao/data/aprovacoes_outros_concursos.csv',
      'data/aprovacoes_outros_concursos.csv',
      './data/aprovacoes_outros_concursos.csv',
      '/evasao/dist/data/aprovacoes_outros_concursos.csv',
      '/evasao/dist/assets/aprovacoes_outros_concursos.csv',
      '/evasao/aprovacoes_outros_concursos.csv',
      '/aprovacoes_outros_concursos.csv',
      'dist/data/aprovacoes_outros_concursos.csv',
      'assets/aprovacoes_outros_concursos.csv',
    ];

    const criarUrlSemCache = (baseUrl: string) => baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'v=' + Date.now();

    async function tryLoad() {
      for (const caminho of caminhos) {
        try {
          const resposta = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
          if (!resposta.ok) continue;
          let textoConteudo = await resposta.text();
          textoConteudo = textoConteudo.replace(/^\uFEFF/, '');
          const dadosParsed = analisarCsvSeparadoPorPontoVirgula(textoConteudo) as AprovacaoOutroConcursoRaw[];
          if (!Array.isArray(dadosParsed) || dadosParsed.length === 0) continue;

          if (montado) {
            setDadosAprovacoesOutrosConcursos(dadosParsed);
          }
          return;
        } catch (erro) {
          // eslint-disable-next-line no-console
          console.debug('Falha ao carregar aprovacoes_outros_concursos.csv', caminho, erro);
        }
      }

      if (montado) {
        // eslint-disable-next-line no-console
        console.warn('Nao foi possivel carregar aprovacoes_outros_concursos.csv; secao ficara vazia.');
        setDadosAprovacoesOutrosConcursos([]);
      }
    }

    tryLoad();

    return () => { montado = false; };
  }, []);

  useEffect(() => {
    let montado = true;

    const caminhos = [
      '/data/outros_concursos.csv',
      '/evasao/data/outros_concursos.csv',
      'data/outros_concursos.csv',
      './data/outros_concursos.csv',
      '/evasao/dist/data/outros_concursos.csv',
      '/evasao/dist/assets/outros_concursos.csv',
      '/evasao/outros_concursos.csv',
      '/outros_concursos.csv',
      'dist/data/outros_concursos.csv',
      'assets/outros_concursos.csv',
    ];

    const criarUrlSemCache = (baseUrl: string) => baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'v=' + Date.now();

    async function tryLoad() {
      for (const caminho of caminhos) {
        try {
          const resposta = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
          if (!resposta.ok) continue;
          let textoConteudo = await resposta.text();
          textoConteudo = textoConteudo.replace(/^\uFEFF/, '');
          const dadosParsed = analisarCsvSeparadoPorPontoVirgula(textoConteudo) as OutroConcursoRaw[];
          if (!Array.isArray(dadosParsed) || dadosParsed.length === 0) continue;

          if (montado) {
            setDadosOutrosConcursos(dadosParsed);
          }
          return;
        } catch (erro) {
          // eslint-disable-next-line no-console
          console.debug('Falha ao carregar outros_concursos.csv', caminho, erro);
        }
      }

      if (montado) {
        // eslint-disable-next-line no-console
        console.warn('Nao foi possivel carregar outros_concursos.csv; secao ficara com menos detalhes.');
        setDadosOutrosConcursos([]);
      }
    }

    tryLoad();

    return () => { montado = false; };
  }, []);

  useEffect(() => {
    let montado = true;
    const baseUrl = import.meta.env.BASE_URL ?? './';
    const caminhosHistorico = [
      `${baseUrl}alteracoes-registros.json`,
      'alteracoes-registros.json',
      '/alteracoes-registros.json',
      '/evasao/alteracoes-registros.json',
    ];

    const criarUrlSemCache = (baseUrl: string) => baseUrl + (baseUrl.includes('?') ? '&' : '?') + 'v=' + Date.now();

    const carregarHistorico = async () => {
      for (const caminho of caminhosHistorico) {
        try {
          const resposta = await fetch(criarUrlSemCache(caminho), { cache: 'no-store', headers: { 'cache-control': 'no-cache' } as any });
          if (!resposta.ok) continue;
          const payload = await resposta.json();
          const historyItems = Array.isArray(payload.history)
            ? payload.history
            : Array.isArray(payload)
              ? payload
              : [];

          const currentMap = buildCurrentRecordMap(dadosBrutos);
          const changes: RecentChange[] = [];
          for (const item of historyItems) {
            if (!item || !Array.isArray(item.changes) || !item.commit?.date) continue;
            for (const change of item.changes) {
              const key = normalizeKey(pickFirstNonEmpty(change.inscricao, change.masp, change.nome));
              if (!key) continue;
              const current = currentMap.get(key);
              const currentDestino = current ? getCurrentOrgaoDestino(current) : null;
              changes.push({
                key,
                commitDate: item.commit.date,
                nome: change.nome ?? '',
                fromSituacao: change.fromSituacao ?? '',
                toSituacao: change.toSituacao ?? '',
                orgaoDestino: currentDestino || change.orgaoDestino || null,
              });
            }
          }

          const ordenadas = changes.sort((a, b) => b.commitDate.localeCompare(a.commitDate)).slice(0, 5);
          if (montado) {
            setRecentChanges(ordenadas);
            setRecentChangesError(null);
          }
          return;
        } catch (erro) {
          // tentar próximo caminho
          // eslint-disable-next-line no-console
          console.debug('Falha ao carregar histórico', caminho, erro);
        }
      }

      if (montado) {
        setRecentChangesError('Não foi possível carregar as alterações recentes.');
      }
    };

    carregarHistorico();
    return () => { montado = false; };
  }, []);

  // === FUNÇÕES PURAS PARA REGRAS DE NEGÓCIO ===

  // Agrega dados por destino (regra de negócio centralizada)
  const agregarPorDestino = (registros: any[]): {
    dadosDestino: DadosDestinoEvasao[];
    detalhesDestino: Record<string, { name: string; data?: string | null; dataPublicacao?: string | null; dataNomeacaoSemEfeito?: string | null; situacao?: string | null; area?: string | null; unidade?: string | null; observacao?: string | null }[]>;
  } => {
    const mapa = new Map<string, number>();
    const detalhes: Record<string, { name: string; data?: string | null; dataPublicacao?: string | null; dataNomeacaoSemEfeito?: string | null; situacao?: string | null; area?: string | null; unidade?: string | null; observacao?: string | null }[]> = {
      'Destino desconhecido': []
    };
    let contagemDesconhecidos = 0;

    for (const registro of registros) {
      const orgao = registro['ORGAO_DESTINO'];
      const situacao = registro['SITUACAO'] ?? null;
      
      // Regra de negócio para determinar chave do destino
      const chave = situacao === 'APOSENTADO' 
        ? 'Aposentados' 
        : situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA' 
        ? 'Afastados para aposentadoria' 
        : (['EXONERADO', 'DESISTENTE'].includes(situacao) && (orgao === null || orgao === undefined || String(orgao).trim() === '')) 
        ? 'Destino desconhecido' 
        : String(orgao).trim();

      // Contagem
      if (chave === 'Destino desconhecido') {
        contagemDesconhecidos += 1;
      } else {
        const anterior = mapa.get(chave) ?? 0;
        mapa.set(chave, anterior + 1);
      }

      // Detalhes
      const nome = registro['NOME'] ?? '';
      const data = situacao === 'EXONERADO' 
        ? registro['DATA_EXONERACAO'] 
        : situacao === 'DESISTENTE' 
        ? registro['DATA_NOMEACAO_SEM_EFEITO'] 
        : ['APOSENTADO', 'AFASTAMENTO PRELIMINAR À APOSENTADORIA'].includes(situacao) 
        ? registro['DATA_INATIVIDADE'] 
        : null;
      const dataPublicacao = situacao === 'EXONERADO' 
        ? registro['DATA_PUBLICACAO_EXONERACAO'] 
        : ['APOSENTADO', 'AFASTAMENTO PRELIMINAR À APOSENTADORIA'].includes(situacao) 
        ? registro['DATA_PUBLICACAO_INATIVIDADE'] 
        : null;
      const area = registro['AREA'] ?? null;
      const unidade = registro['UNIDADE'] ?? registro['Unidade'] ?? null;
      const observacao = registro['OBSERVACAO'] ?? null;

      if (!detalhes[chave]) detalhes[chave] = [];
      detalhes[chave].push({ name: nome, data, dataPublicacao, situacao, area, unidade, observacao });
    }

    // Converter mapa para array
    const dadosDestino: DadosDestinoEvasao[] = Array.from(mapa.entries()).map(([destino, quantidade]) => ({ destino, count: quantidade }));
    if (contagemDesconhecidos > 0) {
      dadosDestino.push({ destino: 'Destino desconhecido', count: contagemDesconhecidos });
    }

    // Ordenação
    dadosDestino.sort((a, b) => {
      const ordem = destino => {
        if (destino === 'Afastados para aposentadoria') return 3;
        if (destino === 'Aposentados') return 2;
        return 1; // demais
      };
      const diff = ordem(a.destino) - ordem(b.destino);
      return diff !== 0 ? diff : b.count - a.count;
    });

    // Ordenar nomes dentro de cada destino
    for (const chave of Object.keys(detalhes)) {
      detalhes[chave].sort((a, b) => {
        const obterDataChave = (it: any) => analisarDataBrasil(it.data);
        const da = obterDataChave(a);
        const db = obterDataChave(b);
        if (!da && db) return -1;
        if (da && !db) return 1;
        if (da && db) return db.getTime() - da.getTime();
        return a.name.localeCompare(b.name);
      });
    }

    return { dadosDestino, detalhesDestino: detalhes };
  };

  // Agrega dados por mês (regra de negócio centralizada)
  const agregarPorMes = (registros: any[], campoData: string): {
    pontosMensais: { label: string; value: number; tipo: string }[];
    detalhesMensais: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]>;
  } => {
    const mapaMensalIso: Map<string, number> = new Map();
    const isoParaRotulo: Record<string, string> = {};
    const detalhes: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]> = {};

    for (const registro of registros) {
      const dataBruta = registro[campoData] ?? null;
      const dataFormatada = analisarDataBrasil(dataBruta);
      if (!dataFormatada) continue;
      
      const codigoIso = `${dataFormatada.getFullYear()}-${String(dataFormatada.getMonth() + 1).padStart(2, '0')}`;
      const mesAbreviado = dataFormatada.toLocaleString('pt-BR', { month: 'short' }).replace('.', '');
      const rotuloExibicao = `${mesAbreviado.toUpperCase()}/${dataFormatada.getFullYear()}`;
      
      mapaMensalIso.set(codigoIso, (mapaMensalIso.get(codigoIso) ?? 0) + 1);
      isoParaRotulo[codigoIso] = rotuloExibicao;
      
      if (!detalhes[rotuloExibicao]) detalhes[rotuloExibicao] = [];
      const nome = registro['NOME'] ?? '';
      const area = registro['AREA'] ?? null;
      const unidade = registro['UNIDADE'] ?? registro['Unidade'] ?? null;
      detalhes[rotuloExibicao].push({ name: nome, date: dataBruta, area, unidade });
    }

    const pontosMensais = Array.from(mapaMensalIso.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([codigoIso, valor]) => ({ label: isoParaRotulo[codigoIso], value: valor, tipo: 'exoneração' }));

    // Ordenar detalhes por data
    for (const rotulo of Object.keys(detalhes)) {
      detalhes[rotulo].sort((a, b) => {
        const da = analisarDataBrasil(a.date);
        const db = analisarDataBrasil(b.date);
        if (da && db) return da.getTime() - db.getTime();
        if (da && !db) return -1;
        if (!da && db) return 1;
        return a.name.localeCompare(b.name);
      });
    }

    return { pontosMensais, detalhesMensais: detalhes };
  };

  // Agrega dados por unidade (regra de negócio centralizada)
  const agregarPorUnidade = (registrosEvasao: any[], registrosInatividade: any[]): {
    pontosUnidadeEvasao: { label: string; value: number; tipo: string }[];
    pontosUnidadeInatividade: { label: string; value: number; tipo: string }[];
    detalhesUnidade: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]>;
    detalhesUnidadeInatividade: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]>;
  } => {
    const mapaUnidadeEvasao: Map<string, number> = new Map();
    const mapaUnidadeInatividade: Map<string, number> = new Map();
    const detalhes: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]> = {};
    const detalhesInatividade: Record<string, { name: string; date?: string | null; area?: string | null; unidade?: string | null }[]> = {};

    // Processar exonerações
    for (const registro of registrosEvasao) {
      const unidade = String(registro['UNIDADE'] ?? registro['Unidade'] ?? 'Unidade desconhecida').trim();
      
      if (unidade === '') {
        continue;
      }

      mapaUnidadeEvasao.set(unidade, (mapaUnidadeEvasao.get(unidade) ?? 0) + 1);
      
      if (!detalhes[unidade]) detalhes[unidade] = [];
      const nome = registro['NOME'] ?? '';
      const area = registro['AREA'] ?? null;
      const dataBruta = registro['DATA_EXONERACAO'] ?? null;
      detalhes[unidade].push({ name: nome, date: dataBruta, area, unidade });
    }

    // Processar inatividades
    for (const registro of registrosInatividade) {
      const unidade = String(registro['UNIDADE'] ?? registro['Unidade'] ?? 'Unidade desconhecida').trim();
      
      if (unidade === '') {
        continue;
      }

      mapaUnidadeInatividade.set(unidade, (mapaUnidadeInatividade.get(unidade) ?? 0) + 1);
      
      if (!detalhesInatividade[unidade]) detalhesInatividade[unidade] = [];
      const nome = registro['NOME'] ?? '';
      const area = registro['AREA'] ?? null;
      const dataBruta = registro['DATA_INATIVIDADE'] ?? null;
      detalhesInatividade[unidade].push({ name: nome, date: dataBruta, area, unidade });
    }

    // Obter todas as unidades únicas
    const todasUnidades = new Set([...mapaUnidadeEvasao.keys(), ...mapaUnidadeInatividade.keys()]);

    // Criar array com informações de cada unidade
    const unidadesComTotais = Array.from(todasUnidades)
      .map(unidade => ({
        unidade,
        totalEvasao: mapaUnidadeEvasao.get(unidade) ?? 0,
        totalInatividade: mapaUnidadeInatividade.get(unidade) ?? 0,
        total: (mapaUnidadeEvasao.get(unidade) ?? 0) + (mapaUnidadeInatividade.get(unidade) ?? 0)
      }))
      .sort((a, b) => b.total - a.total); // Ordenar por total (maior primeiro)

    // Criar os dois arrays de pontos, ambos com a mesma ordem (por total)
    const pontosUnidadeEvasaoSeparados = unidadesComTotais.map(item => ({ label: item.unidade, value: item.totalEvasao, tipo: 'unidade' }));
    const pontosUnidadeInatividadeSeparados = unidadesComTotais.map(item => ({ label: item.unidade, value: item.totalInatividade, tipo: 'unidade' }));

    // Ordenar detalhes por nome
    for (const unidade of Object.keys(detalhes)) {
      detalhes[unidade].sort((a, b) => a.name.localeCompare(b.name));
    }
    for (const unidade of Object.keys(detalhesInatividade)) {
      detalhesInatividade[unidade].sort((a, b) => a.name.localeCompare(b.name));
    }

    return { pontosUnidadeEvasao: pontosUnidadeEvasaoSeparados, pontosUnidadeInatividade: pontosUnidadeInatividadeSeparados, detalhesUnidade: detalhes, detalhesUnidadeInatividade: detalhesInatividade };
  };

  const mapaAuditoresEmExercicio = new Map<string, { nome: string; area?: string | null; unidade?: string | null }>();
  for (const registro of dadosBrutos) {
    if (registro['SITUACAO'] !== 'EM EXERCÍCIO') continue;
    const nome = normalizarTexto(registro['NOME']);
    if (!nome) continue;
    const chaveNome = normalizarNomeChave(nome);
    if (!mapaAuditoresEmExercicio.has(chaveNome)) {
      mapaAuditoresEmExercicio.set(chaveNome, {
        nome,
        area: registro['AREA'] ?? null,
        unidade: registro['UNIDADE'] ?? registro['Unidade'] ?? null,
      });
    }
  }

  const ordemTipoAprovacao = (tipo: TipoAprovacao) => {
    if (tipo === 'Nomeado') return 0;
    if (tipo === 'Aprovado nas vagas') return 1;
    if (tipo === 'Cadastro de Reservas') return 2;
    return 3;
  };

  const compararPosicao = (a: number | null, b: number | null) => {
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return a - b;
  };

  const concursoEstaVencido = (dataVencimento: string): boolean => {
    const data = analisarDataBrasil(dataVencimento);
    if (!data) return false;
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    data.setHours(0, 0, 0, 0);
    return data.getTime() < hoje.getTime();
  };

  const formatarDataValidade = (dataVencimento: string) => {
    const data = analisarDataBrasil(dataVencimento);
    if (!data) return 'Data indisponível';
    return data.toLocaleDateString('pt-BR');
  };

  const calcularVencimentoParaOrdenacao = (
    dataHomologacao: string,
    dataVencimento: string,
    prorrogavel: boolean,
  ): number | null => {
    const vencimento = analisarDataBrasil(dataVencimento);
    if (!vencimento) return null;
    if (!prorrogavel) return vencimento.getTime();

    const homologacao = analisarDataBrasil(dataHomologacao);
    if (!homologacao || homologacao.getTime() >= vencimento.getTime()) return vencimento.getTime();

    const duracaoOriginal = vencimento.getTime() - homologacao.getTime();
    return vencimento.getTime() + duracaoOriginal;
  };

  // Agrupa dados de aprovados em outros concursos por concurso/órgão
  const agregarPorAprovacaoOutroConcurso = (
    registros: AprovacaoOutroConcursoRaw[],
    concursos: OutroConcursoRaw[],
    areaFiltro: string | null,
  ): {
    dadosAprovado: { concurso: string; count: number; statusConcurso: string; dataVencimentoOrdenacao: number | null }[];
    detalhesAprovado: Record<string, { name: string; area?: string | null; unidade?: string | null; tipoAprovacao: TipoAprovacao; aprovacoes: { tipoAprovacao: TipoAprovacao; cargo: string; modalidade: string; posicao: number | null; numeroVagas: number | null; ultimaVagaNomeada: number | null; observacao?: string | null }[] }[]>;
  } => {
    const mapaConcursosInfo = new Map<string, OutroConcursoNormalizado>();
    for (const concursoRaw of concursos) {
      const concursoNormalizado = normalizarLinhaOutroConcurso(concursoRaw);
      if (!concursoNormalizado) continue;
      mapaConcursosInfo.set(
        construirChaveTripla(concursoNormalizado.concurso, concursoNormalizado.cargo, concursoNormalizado.modalidade),
        concursoNormalizado,
      );
    }

    const detalhesPorConcurso = new Map<string, Map<string, { name: string; area?: string | null; unidade?: string | null; aprovacoes: { tipoAprovacao: TipoAprovacao; cargo: string; modalidade: string; posicao: number | null; numeroVagas: number | null; ultimaVagaNomeada: number | null; observacao?: string | null }[] }>>();
    const detalhes: Record<string, { name: string; area?: string | null; unidade?: string | null; tipoAprovacao: TipoAprovacao; aprovacoes: { tipoAprovacao: TipoAprovacao; cargo: string; modalidade: string; posicao: number | null; numeroVagas: number | null; ultimaVagaNomeada: number | null; observacao?: string | null }[] }[]> = {};
    const statusConcursoMap = new Map<string, { homologado: boolean; dataVencimento: string; prorrogavel: boolean; dataVencimentoOrdenacao: number | null }>();

    for (const registro of registros) {
      const aprovado = normalizarLinhaAprovacao(registro);
      if (!aprovado || aprovado.ignorar || aprovado.renunciou) continue;

      const concursoRelacionado = mapaConcursosInfo.get(
        construirChaveTripla(aprovado.concurso, aprovado.cargo, aprovado.modalidade),
      );
      if (!concursoRelacionado) continue;
      const concursoVencido = concursoEstaVencido(concursoRelacionado.dataVencimento);

      const posicaoNumero = parseNumber(aprovado.posicao);
      const numeroVagas = concursoRelacionado.numeroVagas;
      const ultimaVagaNomeada = concursoRelacionado.ultimaVagaNomeada;
      const tipoAprovacao: TipoAprovacao = aprovado.fimDeFila
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

      if (concursoVencido && tipoAprovacao !== 'Nomeado') continue;

      const auditorEmExercicio = mapaAuditoresEmExercicio.get(normalizarNomeChave(aprovado.nome));
      if (!auditorEmExercicio) continue;

      if (areaFiltro && auditorEmExercicio.area !== areaFiltro) continue;

      const statusAtual = statusConcursoMap.get(aprovado.concurso) ?? { homologado: false, dataVencimento: '', prorrogavel: false, dataVencimentoOrdenacao: null };
      const homologado = statusAtual.homologado || !!concursoRelacionado.dataHomologacao;
      const dataVencimento = (() => {
        if (!concursoRelacionado.dataVencimento) return statusAtual.dataVencimento;
        if (!statusAtual.dataVencimento) return concursoRelacionado.dataVencimento;
        const dataNova = analisarDataBrasil(concursoRelacionado.dataVencimento);
        const dataAtual = analisarDataBrasil(statusAtual.dataVencimento);
        if (dataNova && dataAtual) return dataNova.getTime() > dataAtual.getTime() ? concursoRelacionado.dataVencimento : statusAtual.dataVencimento;
        return statusAtual.dataVencimento || concursoRelacionado.dataVencimento;
      })();

      statusConcursoMap.set(aprovado.concurso, {
        homologado,
        dataVencimento,
        prorrogavel: statusAtual.prorrogavel || concursoRelacionado.prorrogavel,
        dataVencimentoOrdenacao: Math.max(
          statusAtual.dataVencimentoOrdenacao ?? Number.NEGATIVE_INFINITY,
          calcularVencimentoParaOrdenacao(
            concursoRelacionado.dataHomologacao,
            concursoRelacionado.dataVencimento,
            concursoRelacionado.prorrogavel,
          ) ?? Number.NEGATIVE_INFINITY,
        ),
      });

      let porPessoa = detalhesPorConcurso.get(aprovado.concurso);
      if (!porPessoa) {
        porPessoa = new Map();
        detalhesPorConcurso.set(aprovado.concurso, porPessoa);
      }

      const chavePessoa = normalizarNomeChave(auditorEmExercicio.nome);
      let agregadoPessoa = porPessoa.get(chavePessoa);
      if (!agregadoPessoa) {
        agregadoPessoa = {
          name: auditorEmExercicio.nome,
          area: auditorEmExercicio.area ?? null,
          unidade: auditorEmExercicio.unidade ?? null,
          aprovacoes: [],
        };
        porPessoa.set(chavePessoa, agregadoPessoa);
      }

      agregadoPessoa.aprovacoes.push({
        tipoAprovacao,
        cargo: concursoRelacionado.cargo,
        modalidade: concursoRelacionado.modalidade,
        posicao: posicaoNumero,
        numeroVagas,
        ultimaVagaNomeada,
        observacao: aprovado.observacao || concursoRelacionado.observacao || null,
      });
    }

    for (const [concurso, porPessoa] of detalhesPorConcurso.entries()) {
      const pessoasConsolidadas = Array.from(porPessoa.values()).map(pessoa => {
        const tipoConsolidado: TipoAprovacao = pessoa.aprovacoes.reduce<TipoAprovacao>((melhor, item) => {
          return ordemTipoAprovacao(item.tipoAprovacao) < ordemTipoAprovacao(melhor)
            ? item.tipoAprovacao
            : melhor;
        }, 'Fim de Fila');

        pessoa.aprovacoes.sort((a, b) => {
          const porTipo = ordemTipoAprovacao(a.tipoAprovacao) - ordemTipoAprovacao(b.tipoAprovacao);
          if (porTipo !== 0) return porTipo;
          const porCargo = a.cargo.localeCompare(b.cargo);
          if (porCargo !== 0) return porCargo;
          const porModalidade = a.modalidade.localeCompare(b.modalidade);
          if (porModalidade !== 0) return porModalidade;
          return compararPosicao(a.posicao, b.posicao);
        });

        return {
          name: pessoa.name,
          area: pessoa.area,
          unidade: pessoa.unidade,
          tipoAprovacao: tipoConsolidado,
          aprovacoes: pessoa.aprovacoes,
        };
      });

      pessoasConsolidadas.sort((a, b) => {
        const porTipo = ordemTipoAprovacao(a.tipoAprovacao) - ordemTipoAprovacao(b.tipoAprovacao);
        if (porTipo !== 0) return porTipo;

        const aPrimeira = a.aprovacoes[0];
        const bPrimeira = b.aprovacoes[0];

        if (aPrimeira && bPrimeira) {
          const porCargo = aPrimeira.cargo.localeCompare(bPrimeira.cargo);
          if (porCargo !== 0) return porCargo;
          const porModalidade = aPrimeira.modalidade.localeCompare(bPrimeira.modalidade);
          if (porModalidade !== 0) return porModalidade;
          const porPosicao = compararPosicao(aPrimeira.posicao, bPrimeira.posicao);
          if (porPosicao !== 0) return porPosicao;
        }

        return a.name.localeCompare(b.name);
      });

      detalhes[concurso] = pessoasConsolidadas;
    }

    const dadosAprovado = Array.from(detalhesPorConcurso.entries())
      .map(([concurso, porPessoa]) => {
        const count = porPessoa.size;
        const status = statusConcursoMap.get(concurso);
        let statusConcurso = 'Aguardando Homologação';
        if (status?.homologado) {
          statusConcurso = `Valido até ${formatarDataValidade(status.dataVencimento)}${status.prorrogavel ? ' (Prorrogável)' : ''}`;
        }
        return {
          concurso,
          count,
          statusConcurso,
          dataVencimentoOrdenacao: status?.dataVencimentoOrdenacao === Number.NEGATIVE_INFINITY
            ? null
            : status?.dataVencimentoOrdenacao ?? null,
        };
      })
      .sort((a, b) => (b.count - a.count) || a.concurso.localeCompare(b.concurso));

    return { dadosAprovado, detalhesAprovado: detalhes };
  };

  // Conta auditores em exercício que estão aguardando nomeação em outros concursos
  // Cada auditor é contado apenas uma vez, mesmo que esteja aguardando em múltiplos concursos
  const contarAuditoresEmExercicioAguardandoNomeacao = (registros: AprovacaoOutroConcursoRaw[], concursos: OutroConcursoRaw[]): number => {
    const mapaConcursosInfo = new Map<string, OutroConcursoNormalizado>();
    for (const concursoRaw of concursos) {
      const concursoNormalizado = normalizarLinhaOutroConcurso(concursoRaw);
      if (!concursoNormalizado) continue;
      mapaConcursosInfo.set(
        construirChaveTripla(concursoNormalizado.concurso, concursoNormalizado.cargo, concursoNormalizado.modalidade),
        concursoNormalizado,
      );
    }

    const auditoresUnicos = new Set<string>();
    
    for (const registro of registros) {
      const aprovado = normalizarLinhaAprovacao(registro);
      if (!aprovado || aprovado.ignorar || aprovado.renunciou) continue;

      const concursoRelacionado = mapaConcursosInfo.get(
        construirChaveTripla(aprovado.concurso, aprovado.cargo, aprovado.modalidade),
      );
      if (!concursoRelacionado) continue;

      const posicaoNumero = parseNumber(aprovado.posicao);
      const numeroVagas = concursoRelacionado.numeroVagas;
      const ultimaVagaNomeada = concursoRelacionado.ultimaVagaNomeada;
      const tipoAprovacao: TipoAprovacao = aprovado.fimDeFila
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

      if (concursoEstaVencido(concursoRelacionado.dataVencimento) && tipoAprovacao !== 'Nomeado') continue;

      const chaveNome = normalizarNomeChave(aprovado.nome);
      if (!mapaAuditoresEmExercicio.has(chaveNome)) continue;
      auditoresUnicos.add(chaveNome);
    }
    
    return auditoresUnicos.size;
  };

  // === APLICAÇÃO DAS REGRAS DE NEGÓCIO ===

  // Conjunto base de dados
  const todosRegistros = dadosBrutos.filter(r => ['EXONERADO', 'DESISTENTE', 'APOSENTADO', 'AFASTAMENTO PRELIMINAR À APOSENTADORIA'].includes(r['SITUACAO']));
  const registrosEvasao = dadosBrutos.filter(r => ['EXONERADO', 'DESISTENTE'].includes(r['SITUACAO']));
  const registrosEvasaoComUnidade = dadosBrutos.filter(r => r['SITUACAO'] === 'EXONERADO'); // Apenas exonerados têm unidade
  const registrosInatividade = dadosBrutos.filter(r => ['APOSENTADO', 'AFASTAMENTO PRELIMINAR À APOSENTADORIA'].includes(r['SITUACAO']));

  // Dados completos (sem filtro de área)
  const { dadosDestino: dadosDestinoEvasao, detalhesDestino: detalhesDestino } = agregarPorDestino(todosRegistros);
  const { pontosMensais: pontosMensais, detalhesMensais: detalhesMensais } = agregarPorMes(registrosEvasao, 'DATA_EXONERACAO');
  const { pontosMensais: pontosMensaisInatividade, detalhesMensais: detalhesMensaisInatividade } = agregarPorMes(registrosInatividade, 'DATA_INATIVIDADE');
  const { pontosUnidadeEvasao: pontosUnidadeEvasaoDetalhados, pontosUnidadeInatividade: pontosUnidadeInatividades, detalhesUnidade: detalhesUnidadeEvasao, detalhesUnidadeInatividade } = agregarPorUnidade(registrosEvasaoComUnidade, registrosInatividade);
  const { dadosAprovado: dadosAprovadoOutrosConcursos, detalhesAprovado: detalhesAprovadoOutrosConcursos } = agregarPorAprovacaoOutroConcurso(dadosAprovacoesOutrosConcursos, dadosOutrosConcursos, null);

  // Totais e métricas básicas
  const contagemEvasoes = registrosEvasao.length;
  const contagemInativos = registrosInatividade.length;
  const contagemAuditoresEmExercicioAguardandoNomeacao = contarAuditoresEmExercicioAguardandoNomeacao(dadosAprovacoesOutrosConcursos, dadosOutrosConcursos);
  // Contagem otimizada de aposentados e afastamentos
  const { contagemAposentado, contagemAfastamentoPreliminar } = dadosBrutos.reduce((acumulador, registro) => {
    const situacao = registro['SITUACAO'];
    if (situacao === 'APOSENTADO') {
      acumulador.contagemAposentado++;
    } else if (situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA') {
      acumulador.contagemAfastamentoPreliminar++;
    }
    return acumulador;
  }, { contagemAposentado: 0, contagemAfastamentoPreliminar: 0 });



  // Conta evasões por área (para mostrar no footer do card)
  const contagemAreas: Record<string, number> = {};
    for (const registro of registrosEvasao) {
      const area = String(registro['AREA'] ?? 'Outros');
      contagemAreas[area] = (contagemAreas[area] ?? 0) + 1;
    }  // Conta evasões por tipo (exoneração vs desistência) - otimizado
  const contagemTipos = registrosEvasao.reduce((acumulador, registro) => {
    const situacao = registro['SITUACAO'];
    if (situacao === 'EXONERADO') {
      acumulador['Exonerações'] = (acumulador['Exonerações'] || 0) + 1;
    } else if (situacao === 'DESISTENTE') {
      acumulador['Desistências'] = (acumulador['Desistências'] || 0) + 1;
    }
    return acumulador;
  }, {} as Record<string, number>);


  const areaFooter = (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3 justify-center">
        {Object.entries(contagemAreas).map(([area, quantidade]) => (
          <div key={area} className="text-xs text-gray-400">
            {area}: <span className="font-medium text-amber-400">{quantidade}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 justify-center border-t border-gray-700 pt-2">
        {Object.entries(contagemTipos).map(([tipo, quantidade]) => (
          <div key={tipo} className="text-xs text-gray-400">
            {tipo}: <span className="font-medium text-amber-400">{quantidade}</span>
          </div>
        ))}
      </div>
    </div>
  );

  // Criar pontos unificados que incluem todos os meses (exonerações + inatividade)
  const criarPontosUnificados = (pontosEvasao: any[], pontosInatividade: any[]) => {
    const mapaMeses: Record<string, string> = {
      'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05', 'JUN': '06',
      'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
    };

    const analisarPontoParaIso = (ponto: any) => {
      const [parteMes, parteAno] = ponto.label.split('/');
      return `${parteAno}-${mapaMeses[parteMes] ?? '01'}`;
    };

    const todosIsos = new Set([
      ...pontosEvasao.map(analisarPontoParaIso),
      ...pontosInatividade.map(analisarPontoParaIso)
    ]);

    const mapaEvasao = new Map(pontosEvasao.map(p => [p.label, p.value]));
    const mapaInatividade = new Map(pontosInatividade.map(p => [p.label, p.value]));

    return Array.from(todosIsos).sort().map(codigoIso => {
      const [ano, mes] = codigoIso.split('-');
      const nomesMeses = ['', 'JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
      const rotulo = `${nomesMeses[parseInt(mes)]}/${ano}`;
      return {
        label: rotulo,
        value: (mapaEvasao.get(rotulo) ?? 0) + (mapaInatividade.get(rotulo) ?? 0),
        tipo: 'total'
      };
    });
  };

  const pontosMensaisUnificados = criarPontosUnificados(pontosMensais, pontosMensaisInatividade);

  // Última exoneração (formatada) — calculada a partir dos dados carregados (ou fallback).
  const dataUltimaExoneracaoFormatada = (dataUltimaEvasao ?? DATA_INICIO_OBSERVACAO)
    ? (dataUltimaEvasao ?? DATA_INICIO_OBSERVACAO).toLocaleDateString('pt-BR')
    : '—';

  // Lista de áreas (para filtro)
  const areas = ['TODAS', ...Array.from(new Set(registrosEvasao.map(registro => String(registro['AREA'] ?? 'Outros')))).sort()];

  // === DADOS FILTRADOS POR ÁREA ===
  // Aplicar filtro de área ao conjunto de dados, depois aplicar as mesmas regras de negócio
  const filtrarPorArea = (registros: any[], area: string) => {
    return area === 'TODAS' ? registros : registros.filter(registro => registro['AREA'] === area);
  };

  const todosRegistrosFiltrados = filtrarPorArea(todosRegistros, areaSelecionada);
  const registrosEvasaoFiltrados = filtrarPorArea(registrosEvasao, areaSelecionada);
  const registrosEvasaoComUnidadeFiltrados = filtrarPorArea(registrosEvasaoComUnidade, areaSelecionada);
  const registrosInatividadeFiltrados = filtrarPorArea(registrosInatividade, areaSelecionada);

  // Aplicar as mesmas regras de negócio aos dados filtrados
  const { dadosDestino: dadosDestinoEvasaoFiltrado, detalhesDestino: detalhesDestinoFiltrados } = agregarPorDestino(todosRegistrosFiltrados);
  const { pontosMensais: pontosMensaisFiltrados, detalhesMensais: detalhesMensaisFiltrados } = agregarPorMes(registrosEvasaoFiltrados, 'DATA_EXONERACAO');
  const { pontosMensais: pontosMensaisInatividadeFiltrados, detalhesMensais: detalhesMensaisInatividadeFiltrados } = agregarPorMes(registrosInatividadeFiltrados, 'DATA_INATIVIDADE');
  const { pontosUnidadeEvasao: pontosUnidadeEvasaoFiltradosDetalhados, pontosUnidadeInatividade: pontosUnidadeInatividadeFiltradosDetalhados, detalhesUnidade: detalhesUnidadeEvasaoFiltrados, detalhesUnidadeInatividade: detalhesUnidadeInatividadeFiltrados } = agregarPorUnidade(registrosEvasaoComUnidadeFiltrados, registrosInatividadeFiltrados);
  const { dadosAprovado: dadosAprovadoOutrosCursosFiltrados, detalhesAprovado: detalhesAprovadoOutrosCursosFiltrados } = areaSelecionada === 'TODAS'
    ? { dadosAprovado: dadosAprovadoOutrosConcursos, detalhesAprovado: detalhesAprovadoOutrosConcursos }
    : agregarPorAprovacaoOutroConcurso(dadosAprovacoesOutrosConcursos, dadosOutrosConcursos, areaSelecionada);
  
  // Calcular recorde: maior intervalo (em dias) sem publicação entre datas de publicação
  const datasExoneracao: Date[] = dadosBrutos
    .map(r => {
      const situacao = r['SITUACAO'];
      if (situacao === 'EXONERADO' || situacao === 'DESISTENTE') {
        return analisarDataBrasil(r['DATA_PUBLICACAO_EXONERACAO']);
      } else if (situacao === 'APOSENTADO' || situacao === 'AFASTAMENTO PRELIMINAR À APOSENTADORIA') {
        return analisarDataBrasil(r['DATA_PUBLICACAO_INATIVIDADE']);
      }
      return null;
    })
    .filter((d): d is Date => d instanceof Date)
    .sort((a, b) => a.getTime() - b.getTime());


  let diasRecorde = 0;
  if (datasExoneracao.length === 0) {
    diasRecorde = 0;
  } else if (datasExoneracao.length === 1) {
    const agora = new Date();
    diasRecorde = Math.floor((agora.getTime() - datasExoneracao[0].getTime()) / (1000 * 3600 * 24));
  } else {
    for (let i = 0; i < datasExoneracao.length - 1; i++) {
      const intervalo = Math.floor((datasExoneracao[i + 1].getTime() - datasExoneracao[i].getTime()) / (1000 * 3600 * 24));
      if (intervalo > diasRecorde) diasRecorde = intervalo;
    }
  }

  const baseUrlApp = (import.meta as any).env?.BASE_URL ?? './';

  const eventosDouPorTipo = new Map(
    (saidasDou?.eventos ?? []).map((evento) => [evento.tipo, evento])
  );

  const diasSemPerderAuditor = saidasDou ? diasDesde(saidasDou.dataMaisRecente) : null;
  const eventoMaisRecente = saidasDou
    ? (saidasDou.eventos ?? []).find((e) => e.dataPublicacao === saidasDou.dataMaisRecente)
    : undefined;

  const IconeCalendario = () => <FontAwesomeIcon icon={faCalendarAlt} className="h-10 w-10 md:h-12 md:w-12 text-red-400" />;

  const IconePessoas = () => <FontAwesomeIcon icon={faUsers} className="h-10 w-10 md:h-12 md:w-12 text-red-400" />;

  const IconeInativo = () => <FontAwesomeIcon icon={faPersonShelter} className="h-10 w-10 md:h-12 md:w-12 text-red-400" />;

  const IconeAguardandoNomeacao = () => <FontAwesomeIcon icon={faHourglassEnd} className="h-10 w-10 md:h-12 md:w-12 text-red-400" />;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 p-4 sm:p-6 lg:p-8">
      <AnnouncementModal />
      <div className="max-w-5xl mx-auto">
        <header className="mb-10">
          <div className="text-center mb-4">
            <span className="inline-flex flex-col md:flex-row items-center gap-2 md:gap-3">
              <img 
                src="assets/images/observatorio-cgu-logo-mini.png"
                alt="Logo do Observatório" 
                className="w-20 h-20 md:w-24 md:h-24 flex-shrink-0"
              />
              <h1 className="text-4xl md:text-5xl font-extrabold drop-shadow-lg text-center md:text-left whitespace-normal break-words min-w-0 md:inline-block" style={{color: '#E21111'}}>OBSERVATÓRIO DAS EVASÕES</h1>
            </span>
          </div>
          <p className="text-lg text-amber-400 font-medium text-center">Auditores Federais de Finanças e Controle &mdash; CGU</p>
        </header>

        <main>
          <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <CounterCard
              value={diasSemPerderAuditor ?? '—'}
              label={`Dia${(diasSemPerderAuditor ?? 0) === 1 ? '' : 's'} sem perder um Auditor`}
              icon={<IconeCalendario />}
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
                          <b>{formatarDataBr(eventoMaisRecente.dataPublicacao)}</b>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-2 justify-center pt-1">
                        {TIPOS_SAIDA_DOU.map(({ tipo, rotuloCurto }) => {
                          const evento = eventosDouPorTipo.get(tipo);
                          if (!evento) {
                            return (
                              <span
                                key={tipo}
                                className="px-2 py-1 rounded border border-gray-800 text-gray-600"
                                title="Nenhum ato deste tipo encontrado nos últimos 12 meses"
                              >
                                {rotuloCurto}: —
                              </span>
                            );
                          }
                          const href = evento.arquivo
                            ? `${baseUrlApp}data/dias_sem_perder_AFFC/${evento.arquivo}`
                            : evento.urlDou;
                          return (
                            <a
                              key={tipo}
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              title={evento.titulo}
                              className="px-2 py-1 rounded border border-amber-500/40 text-amber-400 hover:bg-amber-500/10 hover:border-amber-400 transition-colors"
                            >
                              {rotuloCurto}: {formatarDataBr(evento.dataPublicacao)}
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
              value={contagemEvasoes}
              label="Número de evasões"
              icon={<IconePessoas />}
              footer={areaFooter}
              estaCarregando={estaCarregando}
            />
            <CounterCard
              value={contagemInativos}
              label="Auditores transferidos para inatividade"
              icon={<IconeInativo />}
              footer={
                <div className="space-y-2">
                  <div className="text-xs text-gray-400">Desde Janeiro de 2024</div>
                  <div className="flex flex-wrap gap-3 justify-center">
                    <div className="text-xs text-gray-400">Aposentados: <span className="font-medium text-amber-400">{contagemAposentado}</span></div>
                    <div className="text-xs text-gray-400">Afastamento preliminar: <span className="font-medium text-amber-400">{contagemAfastamentoPreliminar}</span></div>
                    <div className="text-xs text-gray-400">Cada Auditor é contado uma única vez. Caso o Auditor tenha primeiro se afastado e depois se aposentado, predomina o status de aposentado.</div>
                  </div>
                </div>
              }
              estaCarregando={estaCarregando}
            />
            <CounterCard
              value={contagemAuditoresEmExercicioAguardandoNomeacao}
              label="Auditores em exercício aguardando nomeação em outros concursos"
              icon={<IconeAguardandoNomeacao />}
              footer={
                <div className="text-xs text-gray-400">
                  <span>Cada Auditor é contado uma única vez, ainda que tenha sido aprovado em múltiplos concursos.</span>
                </div>
              }
              estaCarregando={estaCarregando}
            />

          </section>

          <div className="mb-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mb-4">
              <h3 className="text-lg font-semibold text-red-300">
                {mostrarPorUnidade ? 'Exonerações e Aposentadorias por Unidade' : 'Exonerações e Aposentadorias por mês'}
              </h3>
              <button
                onClick={() => setMostrarPorUnidade(!mostrarPorUnidade)}
                className="px-4 py-2 rounded bg-amber-500 text-black font-bold hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-300 transition-colors"
              >
                {mostrarPorUnidade ? 'Ver por mês' : 'Ver por Unidade'}
              </button>
            </div>

            {mostrarPorUnidade ? (
              <EvasionChart 
                points={areaSelecionada === 'TODAS' ? pontosUnidadeEvasaoDetalhados : pontosUnidadeEvasaoFiltradosDetalhados} 
                details={areaSelecionada === 'TODAS' ? detalhesUnidadeEvasao : detalhesUnidadeEvasaoFiltrados} 
                inactivityPoints={areaSelecionada === 'TODAS' ? pontosUnidadeInatividades : pontosUnidadeInatividadeFiltradosDetalhados}
                inactivityDetails={areaSelecionada === 'TODAS' ? detalhesUnidadeInatividade : detalhesUnidadeInatividadeFiltrados}
                height={400}
              />
            ) : (
              <EvasionChart 
                points={areaSelecionada === 'TODAS' ? pontosMensais : pontosMensaisFiltrados} 
                details={areaSelecionada === 'TODAS' ? detalhesMensais : detalhesMensaisFiltrados} 
                backgroundPoints={pontosMensaisUnificados} 
                inactivityPoints={areaSelecionada === 'TODAS' ? pontosMensaisInatividade : pontosMensaisInatividadeFiltrados}
                inactivityDetails={areaSelecionada === 'TODAS' ? detalhesMensaisInatividade : detalhesMensaisInatividadeFiltrados}
                backgroundInactivityPoints={pontosMensaisInatividade}
                height={220}
              />
            )}
          </div>

          <div className="mb-4 flex flex-col items-center">
            <div className="text-sm text-gray-300 mb-2">Filtrar por especialidade:</div>
            <div className="flex flex-wrap gap-2 justify-center">
              {areas.map(area => (
                <button
                  key={area}
                  onClick={() => setAreaSelecionada(area)}
                  aria-pressed={areaSelecionada === area}
                  className={`px-3 py-1 rounded text-sm font-medium focus:outline-none focus:ring-2 focus:ring-red-400 ${areaSelecionada === area ? 'bg-red-500 text-white shadow-lg' : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700'}`}
                >
                  {area}
                </button>
              ))}
            </div>
          </div>

          <section className="bg-gray-900 rounded-xl p-4 border border-gray-800 mb-8">
            <div className="mb-3">
              <h2 className="text-2xl font-bold text-amber-400">Últimas evasões cadastradas no Observatório</h2>
            </div>
            {recentChangesError ? (
              <div className="text-sm text-red-200">{recentChangesError}</div>
            ) : recentChanges.length === 0 ? (
              <div className="text-sm text-gray-400">Carregando as alterações mais recentes...</div>
            ) : (
              <>
                <ul className="space-y-1 text-sm text-gray-200">
                  {recentChanges.map((change, index) => (
                    <li key={`${change.commitDate}-${change.nome}-${index}`} className="flex flex-wrap items-baseline gap-2">
                      <span className="text-xs text-gray-400 uppercase tracking-wider">{formatCommitDate(change.commitDate)}</span>
                      <span className="text-amber-400">•</span>
                      <span>{formatRecentChangeDescription(change)}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-3 text-sm">
                  <a href="./historico_alteracoes.html" className="text-amber-400 hover:text-amber-300">Ver histórico completo</a>
                </div>
              </>
            )}
          </section>

          <section className="bg-gray-900 rounded-xl p-6 shadow-2xl border border-gray-800">
            <h2 className="text-2xl font-bold text-red-300 mb-4">Destinos da Evasão</h2>
            <p className="text-gray-400 mb-6">
              Esta tabela detalha os órgãos (destinos) para os quais os Auditores se transferiram após a exoneração ou que se mantiveram, desistindo de tomar posse na CGU.
              A CGU perdeu <span className="font-bold text-orange-400">{contagemEvasoes + contagemInativos}</span> Auditores desde Janeiro/2024.
            </p>
            <EvasionTable 
              data={areaSelecionada === 'TODAS' ? dadosDestinoEvasao : dadosDestinoEvasaoFiltrado} 
              details={areaSelecionada === 'TODAS' ? detalhesDestino : detalhesDestinoFiltrados} 
            />
          </section>

          {/* Nova seção: Auditores Aguardando Nomeação */}
          {dadosAprovadoOutrosConcursos.length > 0 && (
            <section className="bg-gray-900 rounded-xl p-6 shadow-2xl border border-gray-800 mt-8">
              <h2 className="text-2xl font-bold text-amber-400 mb-4">Auditores Aguardando Nomeação</h2>
              <p className="text-gray-400 mb-6">
                Esta tabela apresenta os Auditores em exercício na CGU que foram aprovados em outros concursos e estão aguardando suas nomeações.
                Um Auditor pode aparecer em mais de um órgão caso tenha sido aprovado em múltiplos concursos.
              </p>
              <AprovadosOutrosConcursosTable 
                data={dadosAprovadoOutrosCursosFiltrados}
                details={detalhesAprovadoOutrosCursosFiltrados}
              />
            </section>
          )}
        </main>

        {/* Links para páginas auxiliares */}
        <div className="mt-8 mb-6 flex flex-col sm:flex-row items-center justify-center gap-3 text-center">
          <a
            href="./dados_detalhados.html"
            className="inline-flex items-center px-6 py-3 text-base font-medium text-white bg-red-600 border border-transparent rounded-lg shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors duration-200"
          >
            Ver Dados Detalhados →
          </a>
        </div>

        <div className="mt-8 text-sm text-gray-400 space-y-2">
          <p>
            Esta análise considera os candidatos aprovados no concurso CGU 2021 (FGV), homologado em 14/06/2022, e exonerações, afastamentos e aposentadorias de Auditores veteranos a partir de Janeiro de 2024.
          </p>

          <p>
            São contabilizadas tanto exonerações quanto desistências como eventos de evasão.
          </p>
          <p>
            A quantidade de dias sem perder um Auditor, assim como o respectivo recorde, considera a data de publicação no Diário Oficial da União (DOU) das exonerações, afastamentos e aposentadorias.
          </p>
        </div>

        <CollaborationForm />

        <footer className="text-center mt-6 text-gray-500 text-sm">
          <p>&copy; {new Date().getFullYear()} Observatório das Evasões. Dados extraídos do Diário Oficial da União (DOU) e outras fontes públicas.</p>
        </footer>
      </div>
    </div>
  );
};

export default App;
