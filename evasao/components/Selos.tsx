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
 * ilegível no outro, então cada um tem o seu cinza — mesmos rótulos, mesma
 * semântica, contraste diferente.
 */
export type TemaSelo = 'escuro' | 'claro';

/**
 * A cor do selo é a MESMA para toda fonte, e é cinza.
 *
 * Cada fonte já teve a sua (âmbar para o DOU, azul para o SIAPE, violeta para o
 * ranking, e mais três). O resultado em tela era uma fila de pílulas coloridas
 * ao lado de uma frase sobre pessoa nomeada, e a cor puxava o olho para a
 * PROCEDÊNCIA quando o que a página conta é a SAÍDA. Quem quer saber de onde
 * veio o dado lê o rótulo — que continua ali, escrito — ou o `title`. A cor não
 * carregava informação que o texto já não desse; carregava ênfase, e a ênfase
 * estava no lugar errado. NÃO reintroduzir cor por fonte: o selo é nota de
 * rodapé, não manchete.
 */
const COR_DO_SELO: Record<TemaSelo, string> = {
  escuro: 'border-gray-700 text-gray-400 bg-gray-800/40',
  claro: 'border-gray-300 text-gray-600 bg-gray-100',
};

/** Um tom abaixo do selo com fonte: é ausência de dado, não dado. */
const SEM_FONTE: Record<TemaSelo, string> = {
  escuro: 'border-gray-800 text-gray-500 bg-gray-900/40',
  claro: 'border-gray-200 text-gray-500 bg-white',
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
      } ${chave in ROTULO_POR_FONTE ? COR_DO_SELO[tema] : SEM_FONTE[tema]}`}
    >
      {rotulo}
    </span>
  );
};

/**
 * O LINK para o documento da fonte, cinza como o selo — e pela mesma razão.
 *
 * O que distingue o link do selo ao lado não é mais a cor, é o comportamento: o
 * link muda de tom ao passar o mouse e leva a lugar nenhum senão ao documento.
 * Sem preenchimento, para que a fila não vire um bloco só.
 */
const COR_DO_LINK: Record<TemaSelo, string> = {
  escuro: 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200 hover:bg-gray-800/40',
  claro: 'border-gray-300 text-gray-600 hover:border-gray-400 hover:text-gray-900 hover:bg-gray-100',
};

/** O documento em que a fonte se apoia, aberto em nova aba. */
export const LinkDaFonte: React.FC<{
  href: string;
  rotulo: string;
  titulo?: string;
  compacto?: boolean;
  tema?: TemaSelo;
}> = ({ href, rotulo, titulo, compacto = false, tema = 'escuro' }) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    title={titulo}
    className={`inline-flex items-center whitespace-nowrap rounded border px-2 py-0.5 transition-colors ${
      compacto ? 'text-[10px]' : 'text-xs'
    } ${COR_DO_LINK[tema]}`}
  >
    {rotulo}
  </a>
);

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
  // O diário municipal é ato, como o DOU, mas o link abre a BUSCA que o
  // encontrou, e não uma página de ato: o Querido Diário indexa o diário
  // inteiro, e a data que temos é a da edição, não a de uma peça dentro dela.
  if (fonteDestino === 'DIARIO') return 'ato em diário municipal';
  if (fonteDestino === 'GOOGLE') return 'ato no órgão de chegada';
  const data = formatarDataIsoParaBr(dataDestino);
  return data ? `ato de ${data}` : 'ato de nomeação';
};

export const tituloDoLinkDeDestino = (fonteDestino: string, nome: string, destino: string): string => {
  if (fonteDestino === 'RANKING') {
    return `Aprovações de ${nome} no rankingdosconcursos. É indício com fonte, não ato publicado.`;
  }
  if (fonteDestino === 'DIARIO') {
    return `Ato de nomeação de ${nome} em ${destino}, publicado no diário oficial do município`;
  }
  if (fonteDestino === 'GOOGLE') {
    return `Ato de posse ou nomeação de ${nome} publicado pelo próprio ${destino}`;
  }
  return `Ato de nomeação em ${destino}, publicado no DOU`;
};

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
