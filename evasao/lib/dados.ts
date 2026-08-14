/**
 * Camada de acesso a dado do observatório.
 *
 * Antes da Fase 3 existiam cinco cópias do parser de CSV e do parser de data,
 * com semânticas divergentes: célula vazia virava `null` no `App.tsx` e `''` no
 * `DetailedTableApp.tsx`. Aqui há uma implementação de cada coisa, e a célula
 * vazia é sempre `''` — nunca `null`, nunca `undefined`. Quem quiser distinguir
 * "vazio" de "ausente" usa o próprio `''`.
 */

/** Uma linha crua de CSV: toda coluna é string, campo ausente é `''`. */
export type LinhaCsv = Record<string, string>;

/**
 * Marca de ordem de byte (U+FEFF). O Portal da Transparência entrega os CSVs em
 * UTF-8 com BOM; sem tirá-lo, o primeiro cabeçalho vira `﻿ID_SERVIDOR_PORTAL`
 * e nenhuma coluna casa. Escrito por código para não virar um caractere
 * invisível no meio do fonte.
 */
const BOM = String.fromCharCode(0xfeff);

const semBom = (texto: string): string => (texto.startsWith(BOM) ? texto.slice(1) : texto);

/**
 * Quebra uma linha de CSV separado por `;`, respeitando campos entre aspas
 * duplas e o escape `""`.
 */
const quebrarLinha = (linha: string): string[] => {
  const partes: string[] = [];
  let atual = '';
  let entreAspas = false;

  for (let i = 0; i < linha.length; i += 1) {
    const caractere = linha[i];
    if (caractere === '"') {
      if (entreAspas && linha[i + 1] === '"') {
        atual += '"';
        i += 1;
      } else {
        entreAspas = !entreAspas;
      }
      continue;
    }
    if (caractere === ';' && !entreAspas) {
      partes.push(atual);
      atual = '';
      continue;
    }
    atual += caractere;
  }

  partes.push(atual);
  return partes;
};

/** Lê um CSV `;`-separado. Toda célula sai como string aparada; falta vira `''`. */
export const analisarCsv = (texto: string): LinhaCsv[] => {
  const linhas = semBom(texto).split(/\r?\n/).filter((linha) => linha.trim() !== '');
  if (linhas.length === 0) return [];

  const cabecalhos = quebrarLinha(linhas[0]).map((coluna) => semBom(coluna).trim());

  return linhas.slice(1).map((linha) => {
    const valores = quebrarLinha(linha);
    const registro: LinhaCsv = {};
    for (let i = 0; i < cabecalhos.length; i += 1) {
      registro[cabecalhos[i]] = (valores[i] ?? '').trim();
    }
    return registro;
  });
};

/** `DD/MM/AAAA` → `Date` no fuso local. Qualquer outra coisa → `null`. */
export const analisarDataBr = (valor: string | null | undefined): Date | null => {
  const texto = String(valor ?? '').trim();
  const achado = texto.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!achado) return null;
  const data = new Date(Number(achado[3]), Number(achado[2]) - 1, Number(achado[1]));
  return Number.isNaN(data.getTime()) ? null : data;
};

/**
 * `AAAA-MM-DD` → `Date` ao meio-dia UTC.
 *
 * O meio-dia é de propósito: com 00:00Z o fuso do Brasil (UTC-3) jogaria a data
 * para o dia anterior em toda exibição.
 */
export const analisarDataIso = (valor: string | null | undefined): Date | null => {
  const texto = String(valor ?? '').trim();
  const achado = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!achado) return null;
  const data = new Date(Date.UTC(Number(achado[1]), Number(achado[2]) - 1, Number(achado[3]), 12));
  return Number.isNaN(data.getTime()) ? null : data;
};

/** `AAAA-MM-DD` → `DD/MM/AAAA`. Devolve a entrada intacta se não reconhecer. */
export const formatarDataIsoParaBr = (valor: string | null | undefined): string => {
  const texto = String(valor ?? '').trim();
  const achado = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return achado ? `${achado[3]}/${achado[2]}/${achado[1]}` : texto;
};

/** Dias inteiros entre uma data ISO e hoje. Nunca negativo. */
export const diasDesde = (dataIso: string): number | null => {
  const data = analisarDataIso(dataIso);
  if (!data) return null;
  const agora = new Date();
  const hoje = Date.UTC(agora.getFullYear(), agora.getMonth(), agora.getDate(), 12);
  return Math.max(0, Math.round((hoje - data.getTime()) / 86_400_000));
};

const NOMES_MES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];

/** Competência `AAAAMM` → `MMM/AA`, ex.: `202207` → `JUL/22`. */
export const formatarCompetencia = (mes: string): string => {
  const texto = String(mes ?? '').trim();
  if (!/^\d{6}$/.test(texto)) return texto;
  return `${NOMES_MES[Number(texto.slice(4)) - 1]}/${texto.slice(2, 4)}`;
};

/** Competência `AAAAMM` → `MMM/AAAA` por extenso, para tooltip e texto corrido. */
export const formatarCompetenciaLonga = (mes: string): string => {
  const texto = String(mes ?? '').trim();
  if (!/^\d{6}$/.test(texto)) return texto;
  return `${NOMES_MES[Number(texto.slice(4)) - 1]}/${texto.slice(0, 4)}`;
};

/** Distância em meses entre duas competências `AAAAMM`. */
export const distanciaEmMeses = (de: string, ate: string): number => {
  const anos = Number(ate.slice(0, 4)) - Number(de.slice(0, 4));
  const meses = Number(ate.slice(4)) - Number(de.slice(4));
  return anos * 12 + meses;
};

/**
 * Todas as competências de `de` até `ate`, inclusive.
 *
 * O gráfico precisa dos meses sem nenhuma saída também: sem eles, o eixo pularia
 * de fev para abr e o desenho sugeriria uma continuidade que não existe.
 */
export const listarCompetencias = (de: string, ate: string): string[] => {
  const total = distanciaEmMeses(de, ate);
  if (!/^\d{6}$/.test(de) || !/^\d{6}$/.test(ate) || total < 0) return [];

  const competencias: string[] = [];
  let ano = Number(de.slice(0, 4));
  let mes = Number(de.slice(4));
  for (let i = 0; i <= total; i += 1) {
    competencias.push(`${String(ano).padStart(4, '0')}${String(mes).padStart(2, '0')}`);
    mes += 1;
    if (mes === 13) {
      ano += 1;
      mes = 1;
    }
  }
  return competencias;
};

/**
 * Caminhos em que um arquivo de `evasao/data/` pode estar.
 *
 * A lista existe porque o mesmo bundle roda em três lugares: no `vite dev`
 * (base `/evasao/`, arquivo servido da raiz do projeto), no Pages
 * (`/evasao/data/...`, copiado pelo deploy-pages.yml) e em qualquer preview
 * estático servido de dentro da pasta. Uma lista só, aqui — antes eram quatro,
 * com até dez candidatos cada.
 */
const caminhosPossiveis = (arquivo: string): string[] => {
  const base = (import.meta as any).env?.BASE_URL ?? './';
  return [`${base}data/${arquivo}`, `data/${arquivo}`, `./data/${arquivo}`, `/evasao/data/${arquivo}`, `/data/${arquivo}`];
};

/** Caminhos de um arquivo de `evasao/public/`, que o Vite copia para a raiz do build. */
const caminhosPublicos = (arquivo: string): string[] => {
  const base = (import.meta as any).env?.BASE_URL ?? './';
  return [`${base}${arquivo}`, arquivo, `./${arquivo}`, `/evasao/${arquivo}`, `/${arquivo}`];
};

const semCache = (url: string) => `${url}${url.includes('?') ? '&' : '?'}v=${Date.now()}`;

const buscarTexto = async (caminhos: string[], arquivo: string): Promise<string> => {
  for (const caminho of caminhos) {
    try {
      const resposta = await fetch(semCache(caminho), {
        cache: 'no-store',
        headers: { 'cache-control': 'no-cache' },
      });
      if (!resposta.ok) continue;
      const texto = await resposta.text();
      if (texto.trim() === '') continue;
      return texto;
    } catch {
      // caminho inválido neste ambiente; tenta o próximo
    }
  }
  throw new Error(`Não foi possível carregar ${arquivo}.`);
};

/** Carrega um CSV de `evasao/data/`. Lança se nenhum caminho responder. */
export const carregarCsv = async (arquivo: string): Promise<LinhaCsv[]> => {
  const linhas = analisarCsv(await buscarTexto(caminhosPossiveis(arquivo), arquivo));
  if (linhas.length === 0) throw new Error(`${arquivo} veio vazio.`);
  return linhas;
};

/** Carrega um JSON de `evasao/public/`. Lança se nenhum caminho responder. */
export const carregarJsonPublico = async <T>(arquivo: string): Promise<T> => {
  return JSON.parse(await buscarTexto(caminhosPublicos(arquivo), arquivo)) as T;
};

/** Prefixo para montar links para arquivos servidos junto do painel. */
export const baseDoSite = (): string => (import.meta as any).env?.BASE_URL ?? './';
