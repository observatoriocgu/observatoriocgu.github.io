import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    return {
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
            historico_alteracoes: path.resolve(__dirname, 'historico_alteracoes.html'),
            relatorio_impressao: path.resolve(__dirname, 'relatorio_impressao.html')
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
    };
});
