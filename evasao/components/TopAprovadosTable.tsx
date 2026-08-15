import React from 'react';
import { formatarCompetenciaLonga } from '../lib/dados';
import { AprovadoDoTopo, TopoDaEspecialidade } from '../lib/painel';

interface TopAprovadosTableProps {
  especialidades: TopoDaEspecialidade[];
}

/**
 * O nome de cabeçalho de uma especialidade.
 *
 * `TI` é o valor gravado no dado, e é assim que o filtro e os gráficos o
 * mostram — em cabeçalho de coluna, porém, a sigla sozinha fica torta ao lado
 * de "Contabilidade Pública e Finanças". A tradução vive aqui, e só aqui: é
 * decisão desta tabela, não do vocabulário do observatório.
 */
const CABECALHO_DA_AREA: Readonly<Record<string, string>> = {
  TI: 'Tecnologia da Informação',
};

const cabecalhoDaArea = (area: string): string => CABECALHO_DA_AREA[area] ?? area;

/** `142.5` → `142,5`. A nota vem do edital como o texto do ato a escreveu. */
const formatarNota = (nota: string): string => nota.replace('.', ',');

/**
 * Duas marcas: está na CGU, ou não está.
 *
 * Quem nunca tomou posse leva o mesmo X de quem saiu — porque a pergunta da
 * tabela é "este aprovado está na CGU?", e a resposta é não nos dois casos. O
 * que os separa é a legenda embaixo do nome, que diz qual dos dois nãos é: sem
 * ela, o X sozinho contaria como evasão quem nunca chegou a entrar.
 *
 * O `title` não é enfeite: é onde a marca diz de que fato ela é resumo. Um X
 * sem data e sem motivo obrigaria o leitor a acreditar na cor.
 */
const Marca: React.FC<{ aprovado: AprovadoDoTopo }> = ({ aprovado }) => {
  if (aprovado.situacao === 'ativo') {
    return (
      <span
        title="Consta do quadro da CGU na competência mais recente"
        aria-label="continua na CGU"
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-sm font-bold text-emerald-400"
      >
        ✓
      </span>
    );
  }

  const quando = aprovado.mesSaida ? formatarCompetenciaLonga(aprovado.mesSaida) : '';
  const explicacao =
    aprovado.situacao === 'saiu'
      ? `Saiu da CGU em ${quando} — ${aprovado.motivo.toLocaleLowerCase('pt-BR')}`
      : 'Não consta do quadro da CGU em competência nenhuma do SIAPE: não chegou a tomar posse, ou saiu antes do primeiro registro';

  return (
    <span
      title={explicacao}
      aria-label={aprovado.situacao === 'saiu' ? `saiu da CGU em ${quando}` : 'nunca tomou posse na CGU'}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-500/15 text-sm font-bold text-red-400"
    >
      ✕
    </span>
  );
};

const Celula: React.FC<{ aprovado?: AprovadoDoTopo }> = ({ aprovado }) => {
  if (!aprovado) return <td className="border-t border-gray-800 px-2 py-2 text-gray-600">—</td>;

  const naCgu = aprovado.situacao === 'ativo';
  return (
    <td className="border-t border-gray-800 px-2 py-2 align-middle">
      <div className="flex items-start gap-2">
        <Marca aprovado={aprovado} />
        <div className="min-w-0">
          <div className={`text-xs leading-tight ${naCgu ? 'text-gray-300' : 'text-red-200'}`}>{aprovado.nome}</div>
          {aprovado.situacao === 'sem_registro' && (
            <div className="text-[11px] font-semibold leading-tight text-red-400">nem tomou posse</div>
          )}
        </div>
      </div>
    </td>
  );
};

/**
 * Os dez primeiros colocados de cada especialidade, um por linha da
 * classificação, e se cada um continua na CGU.
 *
 * A tabela é larga por natureza — quatro nomes por linha —, então ela rola na
 * horizontal em vez de espremer o nome de ninguém em duas letras por linha.
 */
export const TopAprovadosTable: React.FC<TopAprovadosTableProps> = ({ especialidades }) => {
  const linhas = especialidades.reduce((maior, e) => Math.max(maior, e.aprovados.length), 0);
  const comEmpate = especialidades.filter((especialidade) => especialidade.empatadosNoCorte.length > 0);

  if (linhas === 0) {
    return <div className="text-sm text-gray-400">Lista de aprovados indisponível.</div>;
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left">
          <thead>
            <tr className="text-xs uppercase tracking-wider text-gray-400">
              <th scope="col" className="w-14 px-2 py-2 font-semibold">
                Posição
              </th>
              {especialidades.map((especialidade) => (
                <th key={especialidade.area} scope="col" className="px-3 py-2 font-semibold">
                  {cabecalhoDaArea(especialidade.area)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: linhas }, (_, indice) => (
              <tr key={indice} className="odd:bg-gray-800/30">
                <th scope="row" className="border-t border-gray-800 px-2 py-2 text-sm font-bold text-amber-400">
                  {indice + 1}º
                </th>
                {especialidades.map((especialidade) => (
                  <Celula key={especialidade.area} aprovado={especialidade.aprovados[indice]} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-gray-400">
        <span className="inline-flex items-center gap-2">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/15 font-bold text-emerald-400">
            ✓
          </span>
          continua na CGU
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-red-500/15 font-bold text-red-400">
            ✕
          </span>
          não está na CGU
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="text-[11px] font-semibold text-red-400">nem tomou posse</span>
          passou no concurso e nunca constou do quadro
        </span>
        <span className="text-gray-500">Passe o cursor sobre a marca para ver a data e o motivo da saída.</span>
      </div>

      {/* Quem empatou em nota com o último da tabela e ficou de fora. O corte
          aí é critério do observatório — o edital classifica por lista de vaga
          e não ordena essas pessoas entre si —, então ele aparece escrito. */}
      {comEmpate.length > 0 && (
        <div className="mt-3 space-y-1 text-xs text-gray-500">
          {comEmpate.map((especialidade) => (
            <p key={especialidade.area}>
              Empate no corte de {cabecalhoDaArea(especialidade.area)}:{' '}
              {especialidade.empatadosNoCorte.map((aprovado, indice) => (
                <React.Fragment key={aprovado.nome}>
                  {indice > 0 ? ', ' : ''}
                  <span className="text-gray-400">{aprovado.nome}</span>
                </React.Fragment>
              ))}{' '}
              {especialidade.empatadosNoCorte.length === 1 ? 'tirou' : 'tiraram'} a mesma nota do último colocado (
              {formatarNota(especialidade.empatadosNoCorte[0].nota)}) e {especialidade.empatadosNoCorte.length === 1 ? 'ficou' : 'ficaram'} de fora da
              tabela pelo desempate — o edital classifica por lista de vaga e não ordena essas pessoas entre si.
            </p>
          ))}
        </div>
      )}
    </>
  );
};

export default TopAprovadosTable;
