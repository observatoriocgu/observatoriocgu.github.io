import React from 'react';
import { DESCRICAO_POR_FONTE, ROTULO_POR_FONTE } from '../constants';

/**
 * Os dois selos da D14.
 *
 * A máquina diz de onde tirou o dado (`SeloFonte`) e se alguém conferiu
 * (`SeloVerificado`). Não existe nota de confiança automática: o observatório
 * não se autoavalia. Nenhuma afirmação sobre pessoa nomeada — motivo de saída,
 * órgão de destino — vai à tela sem estes dois ao lado.
 */

/**
 * O painel é escuro e a tabela detalhada é clara. Um selo legível num tema é
 * ilegível no outro, então cada um tem sua paleta — mesmos rótulos, mesma
 * semântica, contraste diferente.
 */
export type TemaSelo = 'escuro' | 'claro';

const CORES_POR_FONTE: Record<TemaSelo, Record<string, string>> = {
  escuro: {
    DOU: 'border-amber-500/50 text-amber-300 bg-amber-500/10',
    SIAPE: 'border-sky-500/50 text-sky-300 bg-sky-500/10',
    RANKING: 'border-violet-500/50 text-violet-300 bg-violet-500/10',
    BUSCA: 'border-gray-600 text-gray-400 bg-gray-800/40',
    MANUAL: 'border-emerald-500/50 text-emerald-300 bg-emerald-500/10',
  },
  claro: {
    DOU: 'border-amber-600 text-amber-900 bg-amber-100',
    SIAPE: 'border-sky-600 text-sky-900 bg-sky-100',
    RANKING: 'border-violet-600 text-violet-900 bg-violet-100',
    BUSCA: 'border-gray-400 text-gray-700 bg-gray-100',
    MANUAL: 'border-emerald-600 text-emerald-900 bg-emerald-100',
  },
};

const SEM_FONTE: Record<TemaSelo, string> = {
  escuro: 'border-gray-700 text-gray-500 bg-gray-900/40',
  claro: 'border-gray-300 text-gray-500 bg-white',
};

const CORES_VERIFICADO: Record<TemaSelo, { sim: string; nao: string }> = {
  escuro: {
    sim: 'border-emerald-500/50 text-emerald-300 bg-emerald-500/10',
    nao: 'border-gray-700 text-gray-500 bg-gray-900/40',
  },
  claro: {
    sim: 'border-emerald-600 text-emerald-900 bg-emerald-100',
    nao: 'border-gray-300 text-gray-500 bg-white',
  },
};

export const SeloFonte: React.FC<{ fonte: string; compacto?: boolean; tema?: TemaSelo }> = ({
  fonte,
  compacto = false,
  tema = 'escuro',
}) => {
  const chave = String(fonte ?? '').trim().toUpperCase();
  const rotulo = ROTULO_POR_FONTE[chave] ?? (chave || 'sem fonte');
  const descricao = DESCRICAO_POR_FONTE[chave] ?? 'Nenhuma fonte registrada para este campo.';

  return (
    <span
      title={`Fonte: ${descricao}`}
      className={`inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 font-medium ${
        compacto ? 'text-[10px]' : 'text-xs'
      } ${CORES_POR_FONTE[tema][chave] ?? SEM_FONTE[tema]}`}
    >
      {rotulo}
    </span>
  );
};

export const SeloVerificado: React.FC<{ verificado: boolean; compacto?: boolean; tema?: TemaSelo }> = ({
  verificado,
  compacto = false,
  tema = 'escuro',
}) => (
  <span
    title={
      verificado
        ? 'Conferido por uma pessoa contra o ato original.'
        : 'Ainda não conferido por uma pessoa — o dado vem só do que a máquina leu.'
    }
    className={`inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 font-medium ${
      compacto ? 'text-[10px]' : 'text-xs'
    } ${verificado ? CORES_VERIFICADO[tema].sim : CORES_VERIFICADO[tema].nao}`}
  >
    {verificado ? 'conferido' : 'não conferido'}
  </span>
);

/** Os dois selos juntos, que é como a interface quase sempre os mostra. */
export const SelosDaLinha: React.FC<{
  fonte: string;
  verificado: boolean;
  compacto?: boolean;
  tema?: TemaSelo;
}> = ({ fonte, verificado, compacto = false, tema = 'escuro' }) => (
  <span className="inline-flex items-center gap-1">
    <SeloFonte fonte={fonte} compacto={compacto} tema={tema} />
    <SeloVerificado verificado={verificado} compacto={compacto} tema={tema} />
  </span>
);
