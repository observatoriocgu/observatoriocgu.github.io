import React, { useState } from 'react';
import { DetalheSaida } from '../types';
import { formatarCompetenciaLonga } from '../lib/dados';
import { SAIDA_POSSE } from '../lib/painel';
import { LinhasDeProcedencia } from './Selos';

export interface GrupoDeDestino {
  rotulo: string;
  total: number;
  itens: DetalheSaida[];
}

export interface GrupoDeSaida extends GrupoDeDestino {
  /** Vazio quando nenhuma saída do grupo tem órgão de chegada registrado. */
  destinos: GrupoDeDestino[];
}

interface EvasionTableProps {
  grupos: GrupoDeSaida[];
}

/**
 * Uma pessoa dentro de um destino.
 *
 * O fato na primeira linha — o que aconteceu e quando —, e logo abaixo o bloco
 * de procedência, que diz quem atesta a saída e quem atesta o órgão de chegada,
 * cada um na sua linha. O bloco é o mesmo das últimas saídas e do histórico de
 * alterações, e mora em `LinhasDeProcedencia` justamente por isso.
 */
const LinhaAuditor: React.FC<{ saida: DetalheSaida }> = ({ saida }) => {
  const localizacao = [saida.area, saida.unidade].filter(Boolean).join(' · ');

  return (
    <li className="rounded border border-gray-700/50 bg-gray-800/40 px-4 py-2">
      <div className="min-w-0">
        <div className="font-medium text-gray-200">{saida.nome}</div>
        <div className="text-xs text-gray-400">{localizacao || '—'}</div>
      </div>

      <div className="mt-2 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-300">
            {saida.motivo} em {formatarCompetenciaLonga(saida.mesSaida)}
          </span>

          {saida.provisoria && (
            <span
              title="Ausência observada uma única vez. Só vira saída quando o mês seguinte confirmar."
              className="rounded border border-orange-500/50 bg-orange-500/10 px-1.5 py-0.5 text-xs text-orange-300"
            >
              provisória
            </span>
          )}
        </div>

        <LinhasDeProcedencia saida={saida} />
      </div>
    </li>
  );
};

const Seta: React.FC<{ aberto: boolean; className?: string }> = ({ aberto, className = '' }) => (
  <svg
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    className={`h-4 w-4 flex-shrink-0 transform ${aberto ? 'rotate-90' : ''} ${className}`}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
  >
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
  </svg>
);

/** Uma linha clicável da tabela, em qualquer um dos dois níveis. */
const LinhaDeGrupo: React.FC<{
  rotulo: string;
  total: number;
  aberto: boolean;
  aoAlternar: () => void;
  /** Segundo nível: recuo, tipografia menor e cor mais fria que o nível de cima. */
  subnivel?: boolean;
}> = ({ rotulo, total, aberto, aoAlternar, subnivel = false }) => (
  <tr
    onClick={aoAlternar}
    onKeyDown={(evento) => {
      if (evento.key === 'Enter' || evento.key === ' ') {
        evento.preventDefault();
        aoAlternar();
      }
    }}
    tabIndex={0}
    role="button"
    aria-expanded={aberto}
    className={`cursor-pointer transition-colors duration-200 hover:bg-gray-800/60 ${
      subnivel ? 'bg-gray-900/40' : ''
    }`}
  >
    <td className={`max-w-[180px] align-middle md:max-w-none ${subnivel ? 'py-2 pl-12 pr-6' : 'px-6 py-4'}`}>
      <div
        className={`flex w-full items-center gap-2 text-left ${
          subnivel ? 'text-sm text-gray-300' : 'font-medium text-gray-200'
        }`}
      >
        <Seta aberto={aberto} className={subnivel ? 'text-gray-500' : 'text-red-400'} />
        <span className="block whitespace-normal break-words">{rotulo}</span>
      </div>
    </td>
    <td
      className={`text-right font-bold ${subnivel ? 'py-2 pr-6 text-sm text-amber-400' : 'px-6 py-4 text-red-400'}`}
    >
      {total}
    </td>
  </tr>
);

const ListaDePessoas: React.FC<{ itens: DetalheSaida[]; subnivel?: boolean }> = ({ itens, subnivel = false }) => (
  <tr className="bg-gray-900/60">
    <td colSpan={2} className={subnivel ? 'py-3 pl-12 pr-6' : 'px-6 py-3'}>
      <ul className="space-y-2">
        {itens.map((saida) => (
          <LinhaAuditor key={saida.id} saida={saida} />
        ))}
      </ul>
    </td>
  </tr>
);

/**
 * A tabela de destinos, em dois níveis.
 *
 * O de cima é o TIPO da saída; o de baixo, o órgão de chegada, e só existe em
 * quem tem para onde ir — aposentadoria não ganha subnível de um item só.
 *
 * "Posse em outro cargo" nasce aberto porque é o grosso da evasão e a quebra
 * por órgão é a resposta que a seção promete no título: fechado, o leitor teria
 * de clicar para ver o único conteúdo que veio buscar.
 */
const EvasionTable: React.FC<EvasionTableProps> = ({ grupos }) => {
  const [fechados, setFechados] = useState<Record<string, boolean>>({});
  const [abertos, setAbertos] = useState<Record<string, boolean>>({});

  // O padrão de cada grupo é fechado, menos o de posse; o estado guarda a
  // DIVERGÊNCIA em relação a esse padrão, para que o grupo aberto por padrão
  // possa ser fechado pelo leitor como qualquer outro.
  const estaAberto = (chave: string, padraoAberto = false) =>
    padraoAberto ? !fechados[chave] : !!abertos[chave];

  const alternar = (chave: string, padraoAberto = false) => {
    if (padraoAberto) setFechados((anterior) => ({ ...anterior, [chave]: !anterior[chave] }));
    else setAbertos((anterior) => ({ ...anterior, [chave]: !anterior[chave] }));
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full table-auto text-left">
        <thead className="border-b border-gray-700 bg-gray-800 text-sm uppercase text-gray-300">
          <tr>
            <th className="px-6 py-3 font-semibold">Destino</th>
            <th className="px-6 py-3 text-right font-semibold">Auditores</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700">
          {grupos.map((grupo) => {
            const padraoAberto = grupo.rotulo === SAIDA_POSSE;
            const aberto = estaAberto(grupo.rotulo, padraoAberto);
            return (
              <React.Fragment key={grupo.rotulo}>
                <LinhaDeGrupo
                  rotulo={grupo.rotulo}
                  total={grupo.total}
                  aberto={aberto}
                  aoAlternar={() => alternar(grupo.rotulo, padraoAberto)}
                />

                {/* Sem órgão registrado em ninguém, o grupo vai direto às pessoas. */}
                {aberto && grupo.destinos.length === 0 && grupo.itens.length > 0 && (
                  <ListaDePessoas itens={grupo.itens} />
                )}

                {aberto &&
                  grupo.destinos.map((destino) => {
                    const chave = `${grupo.rotulo} · ${destino.rotulo}`;
                    const destinoAberto = estaAberto(chave);
                    return (
                      <React.Fragment key={chave}>
                        <LinhaDeGrupo
                          rotulo={destino.rotulo}
                          total={destino.total}
                          aberto={destinoAberto}
                          aoAlternar={() => alternar(chave)}
                          subnivel
                        />
                        {destinoAberto && destino.itens.length > 0 && (
                          <ListaDePessoas itens={destino.itens} subnivel />
                        )}
                      </React.Fragment>
                    );
                  })}
              </React.Fragment>
            );
          })}
          {grupos.length === 0 && (
            <tr>
              <td colSpan={2} className="px-6 py-6 text-center text-gray-400">
                Nenhuma saída registrada.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default EvasionTable;
