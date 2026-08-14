import React, { useState } from 'react';
import { DetalheSaida } from '../types';
import { formatarCompetenciaLonga, formatarDataIsoParaBr } from '../lib/dados';
import { SelosDaLinha } from './Selos';

export interface GrupoDeDestino {
  rotulo: string;
  total: number;
  itens: DetalheSaida[];
}

interface EvasionTableProps {
  grupos: GrupoDeDestino[];
}

const normalizarBusca = (valor: string) =>
  valor.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase('pt-BR').trim();

/**
 * Uma pessoa dentro de um destino.
 *
 * Toda linha carrega os dois selos da D14 — de onde veio a informação e se foi
 * conferida por gente — e, quando há ato, o link para o trecho do DOU que o
 * observatório leu. Onde não há ato, a linha diz isso em vez de omitir.
 */
const LinhaAuditor: React.FC<{ saida: DetalheSaida }> = ({ saida }) => {
  const localizacao = [saida.area, saida.unidade].filter(Boolean).join(' · ');

  return (
    <li className="flex flex-col gap-2 rounded border border-gray-700/50 bg-gray-800/40 px-4 py-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="font-medium text-gray-200">{saida.nome}</div>
        <div className="text-xs text-gray-400">{localizacao || '—'}</div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-400">
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

        {/* Selo do destino quando há órgão; do motivo quando não há. É sempre o
            selo do campo que a linha está afirmando. */}
        <SelosDaLinha
          fonte={saida.destino ? saida.fonteDestino : saida.fonteMotivo}
          verificado={saida.verificado}
        />

        {saida.atoUrl ? (
          <a
            href={saida.atoUrl}
            target="_blank"
            rel="noopener noreferrer"
            title={saida.atoTitulo || 'Ato publicado no DOU'}
            className="rounded border border-amber-500/40 px-2 py-0.5 text-xs text-amber-400 transition-colors hover:border-amber-400 hover:bg-amber-500/10"
          >
            ato de {formatarDataIsoParaBr(saida.dataPublicacao) || 'data não informada'}
          </a>
        ) : (
          <span className="text-xs text-gray-600" title="A busca por nome no DOU não encontrou ato para esta saída.">
            sem ato no DOU
          </span>
        )}
      </div>
    </li>
  );
};

const EvasionTable: React.FC<EvasionTableProps> = ({ grupos }) => {
  const [abertos, setAbertos] = useState<Record<string, boolean>>({});
  const [busca, setBusca] = useState('');

  const termo = normalizarBusca(busca);
  const visiveis = termo ? grupos.filter((grupo) => normalizarBusca(grupo.rotulo).includes(termo)) : grupos;

  const alternar = (rotulo: string) => setAbertos((anterior) => ({ ...anterior, [rotulo]: !anterior[rotulo] }));

  return (
    <div>
      <label htmlFor="busca-destino-evasao" className="mb-2 block text-sm font-medium text-gray-300">
        Pesquisar por órgão
      </label>
      <input
        id="busca-destino-evasao"
        type="search"
        value={busca}
        onChange={(evento) => setBusca(evento.target.value)}
        placeholder="Digite o nome do órgão..."
        className="mb-4 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-400 md:max-w-md"
      />

      <div className="overflow-x-auto">
        <table className="w-full table-auto text-left">
          <thead className="border-b border-gray-700 bg-gray-800 text-sm uppercase text-gray-300">
            <tr>
              <th className="px-6 py-3 font-semibold">Órgão de destino</th>
              <th className="px-6 py-3 text-right font-semibold">Auditores</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {visiveis.map((grupo) => {
              const aberto = !!abertos[grupo.rotulo];
              return (
                <React.Fragment key={grupo.rotulo}>
                  <tr
                    onClick={() => alternar(grupo.rotulo)}
                    onKeyDown={(evento) => {
                      if (evento.key === 'Enter' || evento.key === ' ') {
                        evento.preventDefault();
                        alternar(grupo.rotulo);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-expanded={aberto}
                    className="cursor-pointer transition-colors duration-200 hover:bg-gray-800/60"
                  >
                    <td className="max-w-[180px] px-6 py-4 align-middle md:max-w-none">
                      <div className="flex w-full items-center gap-2 text-left text-gray-200">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className={`h-4 w-4 transform text-red-400 ${aberto ? 'rotate-90' : ''}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                        <span className="block whitespace-normal break-words">{grupo.rotulo}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-red-400">{grupo.total}</td>
                  </tr>

                  {aberto && grupo.itens.length > 0 && (
                    <tr className="bg-gray-900/60">
                      <td colSpan={2} className="px-6 py-3">
                        <ul className="space-y-2">
                          {grupo.itens.map((saida) => (
                            <LinhaAuditor key={saida.id} saida={saida} />
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {visiveis.length === 0 && (
              <tr>
                <td colSpan={2} className="px-6 py-6 text-center text-gray-400">
                  Nenhum órgão encontrado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default EvasionTable;
