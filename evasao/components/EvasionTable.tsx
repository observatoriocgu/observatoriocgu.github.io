import React, { useState } from 'react';
import { DetalheSaida } from '../types';
import { formatarCompetenciaLonga, formatarDataIsoParaBr } from '../lib/dados';
import { SAIDA_POSSE } from '../lib/painel';
import { LinkDaFonte, SelosDaLinha } from './Selos';

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
 * O que o link do destino abre.
 *
 * No DOU é o ato de nomeação no órgão de chegada, e ele tem data própria — que
 * não é a da saída, e costuma vir ANTES dela: a posse no novo órgão se publica
 * enquanto a vacância na CGU ainda tramita. No ranking é a ficha de aprovações
 * da pessoa, que não tem data de posse nenhuma para mostrar.
 */
const rotuloDoDestino = (saida: DetalheSaida): string => {
  if (saida.fonteDestino === 'RANKING') return 'ficha no ranking';
  const data = formatarDataIsoParaBr(saida.dataDestino);
  return data ? `ato de ${data}` : 'ato de nomeação';
};

const tituloDoDestino = (saida: DetalheSaida): string =>
  saida.fonteDestino === 'RANKING'
    ? `Aprovações de ${saida.nome} no rankingdosconcursos. É indício com fonte, não ato publicado.`
    : `Ato de nomeação em ${saida.destino}, publicado no DOU`;

/** Rótulo do lado esquerdo de uma linha de procedência, com largura fixa. */
const Rotulo: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="text-xs text-gray-500 sm:w-32 sm:flex-shrink-0 sm:text-right">{children}</span>
);

/**
 * Uma pessoa dentro de um destino.
 *
 * SÃO DUAS AFIRMAÇÕES, E CADA UMA TEM SUA LINHA. "Fulano saiu da CGU em agosto"
 * e "fulano foi para o TCU" não vêm do mesmo lugar nem valem o mesmo: a primeira
 * é leitura do cadastro e do ato de vacância, a segunda é o ato de nomeação no
 * órgão de chegada ou, mais fraco, uma aprovação em concurso (D24). Enquanto os
 * selos das duas dividiam a mesma faixa, o leitor via seis pílulas em fila e não
 * tinha como saber qual atestava o quê — o `SIAPE` da saída parecia responder
 * pelo destino, e o link do ato de vacância parecia ser o da nomeação.
 *
 * Daí o empilhamento: o fato na primeira linha, a procedência da SAÍDA na
 * segunda, a do DESTINO na terceira, cada uma com seus selos e o link do
 * documento correspondente. Onde não há ato, a linha diz isso em vez de omitir.
 */
const LinhaAuditor: React.FC<{ saida: DetalheSaida }> = ({ saida }) => {
  const localizacao = [saida.area, saida.unidade].filter(Boolean).join(' · ');
  const temDestino = Boolean(saida.destino && saida.fonteDestino);

  return (
    <li className="rounded border border-gray-700/50 bg-gray-800/40 px-4 py-2">
      <div className="min-w-0">
        <div className="font-medium text-gray-200">{saida.nome}</div>
        <div className="text-xs text-gray-400">{localizacao || '—'}</div>
      </div>

      <div className="mt-2 space-y-1">
        {/* 1. O que aconteceu, e quando. */}
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

        {/* 2. Quem atesta que a pessoa saiu, e o ato que o observatório leu. */}
        <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
          <Rotulo>saída da CGU:</Rotulo>
          <span className="flex flex-wrap items-center gap-2">
            <SelosDaLinha fontes={saida.fontesSaida} compacto />
            {saida.atoUrl ? (
              <LinkDaFonte
                fonte="DOU"
                href={saida.atoUrl}
                rotulo={`ato de ${formatarDataIsoParaBr(saida.dataPublicacao) || 'data não informada'}`}
                titulo={saida.atoTitulo || 'Ato de saída publicado no DOU'}
                compacto
              />
            ) : (
              <span
                className="text-xs text-gray-600"
                title="A busca por nome no DOU não encontrou ato para esta saída."
              >
                sem ato no DOU
              </span>
            )}
          </span>
        </div>

        {/* 3. Quem atesta o órgão de chegada. Só existe quando alguma fonte o
            disse — sem fonte, o destino não vai à tela (D14). */}
        {temDestino && (
          <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
            <Rotulo>órgão de destino:</Rotulo>
            <span className="flex flex-wrap items-center gap-2">
              <SelosDaLinha fontes={[saida.fonteDestino]} compacto />
              {saida.urlDestino && (
                <LinkDaFonte
                  fonte={saida.fonteDestino}
                  href={saida.urlDestino}
                  rotulo={rotuloDoDestino(saida)}
                  titulo={tituloDoDestino(saida)}
                  compacto
                />
              )}
            </span>
          </div>
        )}
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
