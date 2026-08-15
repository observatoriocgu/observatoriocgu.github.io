import React from 'react';
import { DESCRICAO_POR_FONTE, ROTULO_POR_FONTE } from '../constants';

/**
 * O selo de procedência (D14, revisto pela D20).
 *
 * A máquina diz de ONDE tirou o dado, e só isso. Nenhuma afirmação sobre pessoa
 * nomeada — motivo de saída, órgão de destino — vai à tela sem um destes ao lado.
 *
 * O QUE SAIU, E POR QUÊ. Havia também um selo "conferido / não conferido". Ele
 * foi removido: como quase nada passa por conferência humana individual, o que
 * a tela mostrava, na prática, era "não conferido" ao lado de dado correto lido
 * direto do ato oficial — o selo gerava desconfiança sobre a informação em vez
 * de qualificá-la. No lugar entrou o que de fato responde à pergunta "posso
 * confiar nisto?": QUANTAS fontes independentes dizem a mesma coisa. Uma saída
 * com `SIAPE` e `DOU` lado a lado está atestada pelo cadastro de pessoal e pelo
 * ato publicado; uma com `DOU` sozinho é ato publicado que o cadastro ainda não
 * alcançou. O leitor tira a conclusão a partir do fato, não do nosso adjetivo.
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

/**
 * Todas as fontes que atestam o mesmo fato, lado a lado.
 *
 * Duas fontes não são enfeite: significam que o cadastro de pessoal e o ato
 * publicado dizem a mesma coisa, um sem depender do outro. Uma fonte só é a
 * resposta honesta quando é só o que existe até agora.
 */
export const SelosDaLinha: React.FC<{
  fontes: string[];
  compacto?: boolean;
  tema?: TemaSelo;
}> = ({ fontes, compacto = false, tema = 'escuro' }) => {
  const distintas = [...new Set(fontes.filter(Boolean))];
  if (distintas.length === 0) return null;
  return (
    <span className="inline-flex items-center gap-1">
      {distintas.map((fonte) => (
        <SeloFonte key={fonte} fonte={fonte} compacto={compacto} tema={tema} />
      ))}
    </span>
  );
};
