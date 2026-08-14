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
  eixo?: 'esquerda' | 'direita';
  /** Séries de fundo/contexto ficam fora da legenda sem sair do gráfico. */
  ocultaDaLegenda?: boolean;
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
  rotacionarRotulos?: boolean;
  /** Rótulo por extenso de cada categoria, quando `rotulos` veio abreviado. */
  rotulosCompletos?: string[];
  tituloEixoEsquerda?: string;
  tituloEixoDireita?: string;
  /** `false` deixa o eixo esquerdo se ajustar aos dados — o efetivo vive entre 1.500 e 1.800. */
  eixoEsquerdaComZero?: boolean;
  /** Teto do eixo esquerdo, para curvas em pontos percentuais. */
  maximoEixoEsquerda?: number;
  /** Quantos rótulos de x mostrar no máximo; o resto o Chart.js pula. */
  maximoRotulosX?: number;
}

/** Quantas linhas de detalhe cabem num tooltip antes de virar parede de texto. */
const LIMITE_DETALHES = 10;

const EvasionChart: React.FC<EvasionChartProps> = ({
  rotulos,
  series,
  altura = 260,
  empilhar = false,
  rotacionarRotulos = false,
  rotulosCompletos,
  tituloEixoEsquerda,
  tituloEixoDireita,
  eixoEsquerdaComZero = true,
  maximoEixoEsquerda,
  maximoRotulosX,
}) => {
  const usaEixoDireita = series.some((serie) => serie.eixo === 'direita');

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
      yAxisID: serie.eixo === 'direita' ? 'y2' : 'y',
      stack: empilhar && !ehLinha ? 'principal' : undefined,
      spanGaps: false,
    };
  });

  const ocultas = new Set(series.filter((serie) => serie.ocultaDaLegenda).map((serie) => serie.rotulo));

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
          filter: (item: any) => !ocultas.has(item.text),
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
          maxRotation: rotacionarRotulos ? 90 : 0,
          minRotation: rotacionarRotulos ? 90 : 0,
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
      ...(usaEixoDireita
        ? {
            y2: {
              position: 'right',
              beginAtZero: true,
              ticks: { color: '#9ca3af' },
              grid: { display: false },
              title: tituloEixoDireita
                ? { display: true, text: tituloEixoDireita, color: '#9ca3af' }
                : undefined,
            },
          }
        : {}),
    },
  };

  return (
    <div style={{ width: '100%', height: altura }} className="bg-gray-900/50 rounded border border-gray-800 p-2">
      <Chart type="bar" data={{ labels: rotulos, datasets }} options={opcoes} />
    </div>
  );
};

export default EvasionChart;
