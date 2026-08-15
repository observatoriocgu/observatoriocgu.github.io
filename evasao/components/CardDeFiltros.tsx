import React, { useEffect, useMemo, useState } from 'react';

import {
  AREAS_SEM_ESPECIALIDADE,
  COR_POR_CONCURSO,
  COR_POR_MOTIVO,
  ID_CONCURSO_2021,
  ID_CONCURSO_VETERANO,
  MOTIVOS_PADRAO,
  MOTIVOS_SAIDA,
  rotuloDoConcurso,
} from '../constants';
import { RegistroAuditor } from '../types';
import { areaDe, motivoDe, saidas } from '../lib/painel';
import FiltroMultiplo, { OpcaoFiltro } from './FiltroMultiplo';

export const CONCURSOS = [ID_CONCURSO_2021, ID_CONCURSO_VETERANO];

export interface FiltrosEncadeados {
  concursos: string[];
  areas: string[];
  motivos: string[];
  definirConcursos: (valores: string[]) => void;
  definirAreas: (valores: string[]) => void;
  definirMotivos: (valores: string[]) => void;
  opcoesConcurso: OpcaoFiltro[];
  opcoesArea: OpcaoFiltro[];
  opcoesMotivo: OpcaoFiltro[];
  /** Todo mundo do(s) concurso(s) marcado(s) — o nível de cima da cascata. */
  registrosDoConcurso: RegistroAuditor[];
  /** Resumo curto do recorte, para o card fechado. */
  resumo: string;
}

/**
 * Os três filtros encadeados do painel: o concurso manda na especialidade, e os
 * dois juntos mandam no tipo de saída. Cada grupo só lista o que existe no
 * recorte que vem de cima.
 *
 * Só o concurso mostra número. Abaixo dele o total mudaria a cada clique no
 * filtro de cima, e um total que dança confunde mais do que informa: o que
 * responde "quantos?" é o gráfico, não a caixinha.
 *
 * A seleção guarda a INTENÇÃO do leitor, não o que está à vista: `areas` nasce
 * com todas as áreas da base, inclusive "Veterano", que fica invisível enquanto
 * o concurso dele estiver fechado. É o que faz a especialidade já vir junto
 * quando ele abre o concurso, em vez de abrir um concurso que não mostra ninguém.
 */
export const useFiltrosEncadeados = (registros: RegistroAuditor[]): FiltrosEncadeados => {
  const [concursos, definirConcursos] = useState<string[]>([ID_CONCURSO_2021]);
  const [areas, definirAreas] = useState<string[]>([]);
  const [motivos, definirMotivos] = useState<string[]>([...MOTIVOS_PADRAO]);

  const todasAsSaidas = useMemo(() => saidas(registros), [registros]);

  const opcoesConcurso = useMemo((): OpcaoFiltro[] => {
    const totais = new Map<string, number>();
    for (const registro of todasAsSaidas) {
      totais.set(registro.CONCURSO, (totais.get(registro.CONCURSO) ?? 0) + 1);
    }
    return CONCURSOS.map((id) => ({
      valor: id,
      rotulo: rotuloDoConcurso(id),
      cor: COR_POR_CONCURSO[id],
      total: totais.get(id) ?? 0,
    }));
  }, [todasAsSaidas]);

  const registrosDoConcurso = useMemo(
    () => registros.filter((registro) => concursos.includes(registro.CONCURSO)),
    [registros, concursos]
  );

  const opcoesArea = useMemo((): OpcaoFiltro[] => {
    // Toda área que exista em alguém do concurso, tenha ou não saída — senão uma
    // especialidade sem nenhuma evasão simplesmente sumiria do filtro.
    const encontradas = new Set(registrosDoConcurso.map(areaDe));
    const especialidades = Array.from(encontradas)
      .filter((area) => !AREAS_SEM_ESPECIALIDADE.includes(area))
      .sort((a, b) => a.localeCompare(b, 'pt-BR'));
    // As duas que não são especialidade vão para o fim, na ordem da constante:
    // primeiro o veterano, que é "não se aplica", e só depois a lacuna.
    const ordenadas = [...especialidades, ...AREAS_SEM_ESPECIALIDADE.filter((area) => encontradas.has(area))];
    return ordenadas.map((area) => ({ valor: area, rotulo: area }));
  }, [registrosDoConcurso]);

  const opcoesMotivo = useMemo((): OpcaoFiltro[] => {
    const encontrados = new Set(
      saidas(registrosDoConcurso)
        .filter((registro) => areas.includes(areaDe(registro)))
        .map(motivoDe)
    );
    // A ordem é a da constante, não a do dado: é a mesma da legenda do gráfico.
    return MOTIVOS_SAIDA.filter((motivo) => encontrados.has(motivo)).map((motivo) => ({
      valor: motivo,
      rotulo: motivo,
      cor: COR_POR_MOTIVO[motivo],
    }));
  }, [registrosDoConcurso, areas]);

  // As especialidades só se sabem depois que o CSV chega, então a marcação
  // inicial é aplicada aqui, uma vez, sem sobrescrever escolha do leitor.
  const [areasIniciadas, setAreasIniciadas] = useState(false);
  useEffect(() => {
    if (areasIniciadas || registros.length === 0) return;
    definirAreas(Array.from(new Set(registros.map(areaDe))));
    setAreasIniciadas(true);
  }, [registros, areasIniciadas]);

  const resumo = useMemo(
    () =>
      [
        resumirGrupo(concursos, opcoesConcurso, 'nenhum concurso', 'concursos', 'todos'),
        resumirGrupo(areas, opcoesArea, 'nenhuma especialidade', 'especialidades'),
        resumirGrupo(motivos, opcoesMotivo, 'nenhum tipo de saída', 'tipos de saída'),
      ]
        .filter(Boolean)
        .join(' · '),
    [concursos, areas, motivos, opcoesConcurso, opcoesArea, opcoesMotivo]
  );

  return {
    concursos,
    areas,
    motivos,
    definirConcursos,
    definirAreas,
    definirMotivos,
    opcoesConcurso,
    opcoesArea,
    opcoesMotivo,
    registrosDoConcurso,
    resumo,
  };
};

/**
 * Resumo de um grupo para o card fechado.
 *
 * Conta só o que está à vista: a seleção guarda também opções que o filtro de
 * cima escondeu, e "5 de 4" não faria sentido nenhum.
 */
export const resumirGrupo = (
  selecionados: string[],
  opcoes: OpcaoFiltro[],
  /** A frase inteira do caso vazio, com artigo: "nenhuma especialidade". */
  vazio: string,
  plural: string,
  /** Concordância do caso "todos marcados", que segue o gênero do `plural`. */
  todos: 'todas' | 'todos' = 'todas'
): string => {
  if (opcoes.length === 0) return '';
  const visiveis = opcoes.filter((opcao) => selecionados.includes(opcao.valor));
  if (visiveis.length === 0) return vazio;
  // Um só: vale mais dizer qual do que dizer quantos.
  if (visiveis.length === 1) return visiveis[0].rotulo;
  if (visiveis.length === opcoes.length) return `${plural}: ${todos}`;
  return `${plural}: ${visiveis.length} de ${opcoes.length}`;
};

interface CardDeFiltrosProps {
  filtros: FiltrosEncadeados;
  /** Começa aberto? No dashboard não; no histórico, sim. */
  aberto?: boolean;
  /** Um quarto grupo, depois dos três. O histórico usa para entrada/saída. */
  children?: React.ReactNode;
  /** O que acrescentar ao resumo do card fechado por causa do quarto grupo. */
  resumoExtra?: string;
}

/**
 * O card dos filtros.
 *
 * É um `details` nativo: teclado e leitor de tela vêm de graça, sem estado
 * nosso. O resumo ao lado do título existe para que fechado não vire opaco —
 * dá para saber o que está aplicado sem abrir.
 */
const CardDeFiltros: React.FC<CardDeFiltrosProps> = ({ filtros, aberto = false, children, resumoExtra }) => {
  const resumo = [filtros.resumo, resumoExtra].filter(Boolean).join(' · ');
  return (
    <details open={aberto} className="group mb-8 rounded-xl border border-gray-800 bg-gray-900/60">
      <summary className="flex cursor-pointer list-none items-center gap-2 p-5 text-sm font-semibold text-gray-200 [&::-webkit-details-marker]:hidden">
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4 flex-shrink-0 text-gray-500 transition-transform duration-200 group-open:rotate-180"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        Filtros
        <span className="truncate text-xs font-normal text-gray-500 group-open:hidden">{resumo}</span>
      </summary>
      {/* Os grupos lado a lado, com as caixinhas empilhadas dentro de cada um. */}
      <div
        className={`grid grid-cols-1 gap-6 px-5 pb-5 ${children ? 'sm:grid-cols-2 lg:grid-cols-4' : 'sm:grid-cols-3'}`}
      >
        <FiltroMultiplo
          titulo="Concurso"
          opcoes={filtros.opcoesConcurso}
          selecionados={filtros.concursos}
          aoMudar={filtros.definirConcursos}
        />
        <FiltroMultiplo
          titulo="Especialidade"
          opcoes={filtros.opcoesArea}
          selecionados={filtros.areas}
          aoMudar={filtros.definirAreas}
          mensagemVazia="Marque um concurso ao lado."
        />
        <FiltroMultiplo
          titulo="Tipo de saída"
          opcoes={filtros.opcoesMotivo}
          selecionados={filtros.motivos}
          aoMudar={filtros.definirMotivos}
          mensagemVazia="Nenhuma saída no concurso e na especialidade marcados."
        />
        {children}
      </div>
    </details>
  );
};

export default CardDeFiltros;
