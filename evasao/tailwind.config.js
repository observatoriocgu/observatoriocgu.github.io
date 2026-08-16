/**
 * Configuração do Tailwind.
 *
 * Até 16/08/2026 não havia arquivo nenhum: as três páginas carregavam
 * `https://cdn.tailwindcss.com`, o Play CDN, que compila as classes NO NAVEGADOR
 * a cada visita. Ele existe para prototipar — imprime no console o aviso de que
 * não deve ir a produção, custa ~120 KB de JavaScript bloqueante e desenha a
 * página sem estilo até terminar de rodar. Como o projeto já tinha build, o CSS
 * passou a sair dele.
 *
 * A VERSÃO É A 3, e é de propósito: é a mesma que o Play CDN servia. A 4 mudaria
 * padrões que a tela usa sem declarar (a cor da borda, a largura do `ring`, o
 * nome do `shadow-sm`), e a troca deixaria de ser invisível — que era a condição.
 *
 * `content` precisa alcançar TODO arquivo onde exista nome de classe escrito,
 * porque agora quem varre é o build, e classe não encontrada simplesmente não
 * existe no CSS. Aqui isso é seguro: nenhum nome é montado por interpolação
 * (`bg-${cor}-100` não aparece em lugar nenhum) — o que se interpola são strings
 * de classe inteiras, e o varredor lê o texto cru do arquivo, não o AST.
 */
export default {
  content: [
    './*.html',
    './*.tsx',
    './*.ts',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
