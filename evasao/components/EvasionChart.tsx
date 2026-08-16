import React from 'react';
import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  Filler,
  Title,
  Tooltip,
  Legend
);

/**
 * Uma série do gráfico.
 *
 * `valores` tem exatamente o comprimento de `rotulos`; `null` é buraco, e o
 * Chart.js não desenha ponto nem barra — que é o que se quer para `ENTRADAS` e
 * `SAIDAS` na primeira competência da série, onde não existe mês anterior.
 */
export interface SerieGrafico {
  rotulo: string;
  cor: string;
  valores: (number | null)[];
  tipo?: 'barra' | 'linha';
  /** Linhas de texto por categoria, exibidas no tooltip abaixo do valor. */
  detalhes?: string[][];
  /** Sufixo do valor no tooltip, ex.: `%`. */
  sufixo?: string;
}

interface EvasionChartProps {
  rotulos: string[];
  series: SerieGrafico[];
  altura?: number;
  /** Empilha as barras. Linhas nunca empilham. */
  empilhar?: boolean;
  /** Rótulo por extenso de cada categoria, quando `rotulos` veio abreviado. */
  rotulosCompletos?: string[];
  tituloEixoEsquerda?: string;
  /** `false` deixa o eixo esquerdo se ajustar aos dados — o efetivo vive entre 1.500 e 1.800. */
  eixoEsquerdaComZero?: boolean;
  /** Teto do eixo esquerdo, para curvas em pontos percentuais. */
  maximoEixoEsquerda?: number;
  /** Quantos rótulos de x mostrar no máximo; o resto o Chart.js pula. */
  maximoRotulosX?: number;
  /**
   * Como o gráfico se chama, para a tabela que o acompanha. Ver `TabelaDaSerie`.
   */
  descricao?: string;
}

/**
 * A mesma série, em tabela, visível só para quem lê por leitor de tela.
 *
 * O gráfico é um `<canvas>`: para quem não o enxerga ele é um retângulo, e os
 * números só existiam dentro do tooltip, que exige apontar o mouse para uma
 * barra. A tabela é a mesma informação por outro caminho — e não custa dado
 * nenhum a mais, porque a série já está montada em `series[].valores`.
 *
 * O `<canvas>` fica `aria-hidden`, senão o leitor anuncia as duas coisas.
 */
const TabelaDaSerie: React.FC<{
  rotulos: string[];
  rotulosCompletos?: string[];
  series: SerieGrafico[];
  descricao?: string;
}> = ({ rotulos, rotulosCompletos, series, descricao }) => (
  // O `sr-only` vai na DIV, e não na tabela. Ele esconde encolhendo a caixa para
  // 1x1 e recortando o resto, e `<table>` trata `height` como MÍNIMO: a tabela
  // cresce até caber o conteúdo, ignora o recorte e, mesmo invisível, estica a
  // área rolável da página — 1.324 px de vão embaixo de cada gráfico. Numa `div`
  // a altura vale, e o que passa dela fica escondido.
  <div className="sr-only">
    <table>
      <caption>{descricao ?? 'Os números do gráfico acima'}</caption>
      <thead>
        <tr>
          <th scope="col">Competência</th>
          {series.map((serie) => (
            <th key={serie.rotulo} scope="col">
              {serie.rotulo}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rotulos.map((rotulo, indice) => (
          <tr key={rotulo}>
            <th scope="row">{rotulosCompletos?.[indice] ?? rotulo}</th>
            {series.map((serie) => {
              const valor = serie.valores[indice];
              // `null` é buraco na série, e não zero: dizer "0" aqui afirmaria
              // que ninguém saiu num mês que o gráfico deixa em branco de propósito.
              return (
                <td key={serie.rotulo}>
                  {valor === null || valor === undefined ? 'sem dado' : `${valor}${serie.sufixo ?? ''}`}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** Quantas linhas de detalhe cabem num tooltip antes de virar parede de texto. */
const LIMITE_DETALHES = 10;

const EvasionChart: React.FC<EvasionChartProps> = ({
  rotulos,
  series,
  altura = 260,
  empilhar = false,
  rotulosCompletos,
  tituloEixoEsquerda,
  eixoEsquerdaComZero = true,
  maximoEixoEsquerda,
  maximoRotulosX,
  descricao,
}) => {
  const datasets = series.map((serie) => {
    const ehLinha = serie.tipo === 'linha';
    return {
      type: ehLinha ? ('line' as const) : ('bar' as const),
      label: serie.rotulo,
      data: serie.valores,
      backgroundColor: serie.cor,
      borderColor: serie.cor,
      borderWidth: ehLinha ? 2 : 0,
      borderRadius: ehLinha ? 0 : 4,
      pointRadius: ehLinha ? 0 : undefined,
      pointHoverRadius: ehLinha ? 4 : undefined,
      tension: ehLinha ? 0.25 : undefined,
      fill: false,
      barPercentage: 0.95,
      categoryPercentage: 0.9,
      stack: empilhar && !ehLinha ? 'principal' : undefined,
      spanGaps: false,
    };
  });

  const opcoes: any = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: series.length > 1,
        position: 'top',
        labels: {
          color: '#d1d5db',
          font: { size: 12 },
          padding: 14,
          usePointStyle: true,
        },
      },
      title: { display: false },
      tooltip: {
        callbacks: {
          title: (contexto: any[]) => {
            if (contexto.length === 0) return '';
            const indice = contexto[0].dataIndex;
            return rotulosCompletos?.[indice] ?? contexto[0].label;
          },
          label: (contexto: any) => {
            const serie = series[contexto.datasetIndex];
            const valor = contexto.parsed.y;
            if (valor === null || valor === undefined) return '';
            const formatado = Number.isInteger(valor) ? valor : valor.toFixed(1);
            return `${serie.rotulo}: ${formatado}${serie.sufixo ?? ''}`;
          },
          afterBody: (contexto: any[]) => {
            const linhas: string[] = [];
            for (const item of contexto) {
              const serie = series[item.datasetIndex];
              const detalhes = serie?.detalhes?.[item.dataIndex];
              if (!detalhes || detalhes.length === 0) continue;
              if (contexto.length > 1) linhas.push('', serie.rotulo);
              linhas.push(...detalhes.slice(0, LIMITE_DETALHES));
              if (detalhes.length > LIMITE_DETALHES) {
                linhas.push(`… e mais ${detalhes.length - LIMITE_DETALHES}`);
              }
            }
            return linhas;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: empilhar,
        ticks: {
          color: '#d1d5db',
          maxRotation: 0,
          minRotation: 0,
          autoSkip: true,
          maxTicksLimit: maximoRotulosX,
        },
        grid: { display: false },
      },
      y: {
        stacked: empilhar,
        beginAtZero: eixoEsquerdaComZero,
        max: maximoEixoEsquerda,
        ticks: { color: '#9ca3af' },
        grid: { color: '#374151' },
        title: tituloEixoEsquerda
          ? { display: true, text: tituloEixoEsquerda, color: '#9ca3af' }
          : undefined,
      },
    },
  };

  return (
    <>
      <div
        style={{ width: '100%', height: altura }}
        className="bg-gray-900/50 rounded border border-gray-800 p-2"
        aria-hidden="true"
      >
        <Chart type="bar" data={{ labels: rotulos, datasets }} options={opcoes} />
      </div>
      <TabelaDaSerie
        rotulos={rotulos}
        rotulosCompletos={rotulosCompletos}
        series={series}
        descricao={descricao}
      />
    </>
  );
};

export default EvasionChart;
