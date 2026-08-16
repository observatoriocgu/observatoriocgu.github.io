import React from 'react';
import { DESCRICAO_POR_FONTE, ROTULO_POR_FONTE } from '../constants';
import { DetalheSaida } from '../types';
import { formatarDataIsoParaBr } from '../lib/dados';

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
 * As cores do LINK para o documento da fonte.
 *
 * Mesma família de cor do selo correspondente, sem o preenchimento: o selo diz
 * de onde veio, o link ao lado abre o documento, e um não pode ser confundido
 * com o outro num aglomerado de pílulas coloridas. Fonte sem cor própria — ou
 * sem documento, como o SIAPE — cai no neutro.
 */
const CORES_DE_LINK: Record<TemaSelo, Record<string, string>> = {
  escuro: {
    DOU: 'border-amber-500/40 text-amber-400 hover:border-amber-400 hover:bg-amber-500/10',
    RANKING: 'border-violet-500/40 text-violet-300 hover:border-violet-400 hover:bg-violet-500/10',
    MANUAL: 'border-emerald-500/40 text-emerald-300 hover:border-emerald-400 hover:bg-emerald-500/10',
  },
  claro: {
    DOU: 'border-amber-600 text-amber-800 hover:bg-amber-100',
    RANKING: 'border-violet-600 text-violet-800 hover:bg-violet-100',
    MANUAL: 'border-emerald-600 text-emerald-800 hover:bg-emerald-100',
  },
};

const LINK_NEUTRO: Record<TemaSelo, string> = {
  escuro: 'border-gray-700 text-gray-400 hover:border-gray-500 hover:bg-gray-800/40',
  claro: 'border-gray-300 text-gray-600 hover:bg-gray-100',
};

/** O documento em que a fonte se apoia, aberto em nova aba. */
export const LinkDaFonte: React.FC<{
  fonte: string;
  href: string;
  rotulo: string;
  titulo?: string;
  compacto?: boolean;
  tema?: TemaSelo;
}> = ({ fonte, href, rotulo, titulo, compacto = false, tema = 'escuro' }) => {
  const chave = String(fonte ?? '').trim().toUpperCase();

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={titulo}
      className={`inline-flex items-center whitespace-nowrap rounded border px-2 py-0.5 transition-colors ${
        compacto ? 'text-[10px]' : 'text-xs'
      } ${CORES_DE_LINK[tema][chave] ?? LINK_NEUTRO[tema]}`}
    >
      {rotulo}
    </a>
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

/**
 * O que o link do destino abre.
 *
 * No DOU é o ato de nomeação no órgão de chegada, e ele tem data própria — que
 * não é a da saída, e costuma vir ANTES dela: a posse no novo órgão se publica
 * enquanto a vacância na CGU ainda tramita. No ranking é a ficha de aprovações
 * da pessoa, que não tem data de posse nenhuma para mostrar.
 *
 * Recebe os campos soltos, e não o `DetalheSaida`, porque a tabela detalhada
 * mostra o mesmo link a partir do `RegistroAuditor` cru. A regra "ranking abre
 * ficha, DOU abre ato" tem de ficar num lugar só: copiada na tabela, ela chamaria
 * de "ato" a página de aprovações no primeiro destino vindo do ranking.
 */
export const rotuloDoLinkDeDestino = (fonteDestino: string, dataDestino: string): string => {
  if (fonteDestino === 'RANKING') return 'ficha no ranking';
  const data = formatarDataIsoParaBr(dataDestino);
  return data ? `ato de ${data}` : 'ato de nomeação';
};

export const tituloDoLinkDeDestino = (fonteDestino: string, nome: string, destino: string): string =>
  fonteDestino === 'RANKING'
    ? `Aprovações de ${nome} no rankingdosconcursos. É indício com fonte, não ato publicado.`
    : `Ato de nomeação em ${destino}, publicado no DOU`;

/**
 * O rótulo à esquerda de cada linha de procedência.
 *
 * Coluna de largura fixa e alinhada à direita a partir do `sm`: os dois rótulos
 * têm comprimentos diferentes, e sem a coluna os selos começariam em pontos
 * distintos, desfazendo justamente a leitura vertical que separa as duas
 * afirmações. Abaixo do `sm` a coluna some e a linha simplesmente quebra.
 * O cinza médio serve aos dois temas: some no fundo escuro sem sumir no claro.
 */
const ROTULO = 'text-xs text-gray-500 sm:w-32 sm:flex-shrink-0 sm:text-right';

/**
 * A procedência de uma saída, em duas linhas rotuladas.
 *
 * SÃO DUAS AFIRMAÇÕES, E CADA UMA TEM SUA LINHA. "Fulano saiu da CGU em agosto"
 * e "fulano foi para o TCU" não vêm do mesmo lugar nem valem o mesmo: a primeira
 * é leitura do cadastro e do ato de vacância, a segunda é o ato de nomeação no
 * órgão de chegada ou, mais fraco, uma aprovação em concurso (D24). Enquanto os
 * selos das duas dividiam a mesma faixa, o leitor via seis pílulas em fila e não
 * tinha como saber qual atestava o quê — o `SIAPE` da saída parecia responder
 * pelo destino, e o link do ato de vacância parecia ser o da nomeação.
 *
 * MORA AQUI, E NÃO EM CADA TELA, porque três páginas mostram a mesma saída — os
 * destinos, as últimas saídas e o histórico de alterações — e uma regra de
 * procedência copiada em três lugares é uma regra que a quarta tela quebra. Cada
 * página escreve a FRASE do seu jeito, e chama este bloco para dizer de onde
 * veio o que ela afirmou.
 *
 * Recebe o `DetalheSaida` pronto, do `detalharSaida`: é ele quem sabe compor as
 * fontes com `fontesDaSaida` e escolher entre o ato arquivado e o do in.gov.br.
 */
export const LinhasDeProcedencia: React.FC<{ saida: DetalheSaida; tema?: TemaSelo }> = ({
  saida,
  tema = 'escuro',
}) => (
  <div className="space-y-1">
    {/* Quem atesta que a pessoa saiu, e o ato que o observatório leu. */}
    <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
      <span className={ROTULO}>saída da CGU:</span>
      <span className="flex flex-wrap items-center gap-2">
        <SelosDaLinha fontes={saida.fontesSaida} compacto tema={tema} />
        {saida.atoUrl ? (
          <LinkDaFonte
            fonte="DOU"
            href={saida.atoUrl}
            rotulo={`ato de ${formatarDataIsoParaBr(saida.dataPublicacao) || 'data não informada'}`}
            titulo={saida.atoTitulo || 'Ato de saída publicado no DOU'}
            compacto
            tema={tema}
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

    {/* Quem atesta o órgão de chegada. Só existe quando alguma fonte o disse —
        sem fonte, o destino não vai à tela (D14). */}
    {Boolean(saida.destino && saida.fonteDestino) && (
      <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
        <span className={ROTULO}>órgão de destino:</span>
        <span className="flex flex-wrap items-center gap-2">
          <SelosDaLinha fontes={[saida.fonteDestino]} compacto tema={tema} />
          {saida.urlDestino && (
            <LinkDaFonte
              fonte={saida.fonteDestino}
              href={saida.urlDestino}
              rotulo={rotuloDoLinkDeDestino(saida.fonteDestino, saida.dataDestino)}
              titulo={tituloDoLinkDeDestino(saida.fonteDestino, saida.nome, saida.destino)}
              compacto
              tema={tema}
            />
          )}
        </span>
      </div>
    )}
  </div>
);
