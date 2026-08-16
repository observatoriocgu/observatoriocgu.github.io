import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// A configuração é um OBJETO, e não uma função de `({ mode })`. O formato de
// função existia para chamar `loadEnv` e injetar `process.env.GEMINI_API_KEY`,
// resto do scaffold do AI Studio: nunca houve uso de Gemini aqui. Sem o
// `define`, `mode` e `env` não tinham leitor — e um `loadEnv` pendurado sugere
// que o projeto lê variável de ambiente, o que não é verdade.
export default defineConfig({
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        dados_detalhados: path.resolve(__dirname, 'dados_detalhados.html'),
        historico_alteracoes: path.resolve(__dirname, 'historico_alteracoes.html')
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    }
  },
  // O site publicado fica em https://observatoriocgu.github.io/evasao/.
  // Quem monta essa estrutura é o workflow .github/workflows/deploy-pages.yml,
  // que copia o resultado do build (dist/) para _site/evasao/.
  base: '/evasao/'
});
