import React from 'react';

export interface OpcaoFiltro {
  valor: string;
  rotulo: string;
  /** Cor do marcador, quando a opção corresponde a uma série do gráfico. */
  cor?: string;
  /** Quantos registros a opção representa no recorte atual. */
  total?: number;
}

interface FiltroMultiploProps {
  titulo: string;
  opcoes: OpcaoFiltro[];
  selecionados: string[];
  aoMudar: (selecionados: string[]) => void;
  /** O que dizer quando o filtro de cima não deixou nenhuma opção aqui. */
  mensagemVazia?: string;
}

/**
 * Um grupo de caixinhas.
 *
 * Seleção vazia mostra nada, e não tudo: com marcar e desmarcar, "nenhuma
 * marcada" é uma escolha deliberada do leitor, e fazer o gráfico voltar a
 * mostrar o conjunto inteiro nesse caso confundiria mais do que ajudaria.
 *
 * `selecionados` pode conter valor que não está em `opcoes` — e ele sobrevive a
 * qualquer clique daqui. Os filtros são encadeados (concurso manda na
 * especialidade, que manda no tipo de saída), então uma opção some da lista
 * quando o filtro de cima muda. Se o clique reescrevesse a seleção só com o que
 * está à vista, marcar uma especialidade apagaria em silêncio a escolha que o
 * leitor tinha feito nas que sumiram — e ela não voltaria ao reabrir o concurso.
 */
const FiltroMultiplo: React.FC<FiltroMultiploProps> = ({
  titulo,
  opcoes,
  selecionados,
  aoMudar,
  mensagemVazia,
}) => {
  const marcados = new Set(selecionados);
  const daLista = new Set(opcoes.map((opcao) => opcao.valor));
  const ocultos = selecionados.filter((valor) => !daLista.has(valor));

  /** Emite a seleção visível pedida, sem perder o que está fora da lista. */
  const emitir = (visiveis: string[]) => aoMudar([...visiveis, ...ocultos]);

  const alternar = (valor: string) => {
    const novo = new Set(marcados);
    if (novo.has(valor)) novo.delete(valor);
    else novo.add(valor);
    // Preserva a ordem em que as opções são exibidas, não a de clique.
    emitir(opcoes.filter((opcao) => novo.has(opcao.valor)).map((opcao) => opcao.valor));
  };

  const todosMarcados = opcoes.length > 0 && opcoes.every((opcao) => marcados.has(opcao.valor));

  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 flex items-baseline gap-2 text-sm text-gray-300">
        {titulo}
        {opcoes.length > 0 && (
          <button
            type="button"
            onClick={() => emitir(todosMarcados ? [] : opcoes.map((opcao) => opcao.valor))}
            className="text-xs text-gray-500 underline decoration-dotted hover:text-amber-400"
          >
            {todosMarcados ? 'limpar' : 'marcar todas'}
          </button>
        )}
      </legend>
      {opcoes.length === 0 && mensagemVazia && (
        <p className="rounded border border-dashed border-gray-700 px-2.5 py-1 text-sm text-gray-500">
          {mensagemVazia}
        </p>
      )}
      {/* Uma caixinha por linha: com os três grupos lado a lado, empilhar na
          vertical é o que deixa cada coluna legível de cima a baixo. */}
      <div className="flex flex-col gap-2">
        {opcoes.map((opcao) => {
          const marcado = marcados.has(opcao.valor);
          return (
            <label
              key={opcao.valor}
              className={`flex cursor-pointer select-none items-center gap-2 rounded border px-2.5 py-1 text-sm transition-colors ${
                marcado
                  ? 'border-red-500 bg-red-500/15 text-gray-100'
                  : 'border-gray-700 bg-gray-800/60 text-gray-400 hover:border-gray-600 hover:text-gray-300'
              }`}
            >
              <input
                type="checkbox"
                checked={marcado}
                onChange={() => alternar(opcao.valor)}
                className="h-3.5 w-3.5 accent-red-500"
              />
              {opcao.cor && (
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 flex-shrink-0 rounded-sm"
                  style={{ backgroundColor: opcao.cor, opacity: marcado ? 1 : 0.4 }}
                />
              )}
              {/* `flex-1` empurra o total para a direita, alinhando os números
                  numa coluna só em vez de deixá-los correndo atrás do rótulo. */}
              <span className="flex-1">{opcao.rotulo}</span>
              {opcao.total !== undefined && (
                <span className={marcado ? 'text-amber-400' : 'text-gray-600'}>{opcao.total}</span>
              )}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};

export default FiltroMultiplo;
