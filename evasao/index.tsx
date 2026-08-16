import React from 'react';
import ReactDOM from 'react-dom/client';

// O CSS entra pelo módulo, e não por um `<link>` escrito à mão no HTML: assim
// quem resolve o caminho no site publicado é o Vite, com o `base` configurado.
import './estilos.css';

import App from './App';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);