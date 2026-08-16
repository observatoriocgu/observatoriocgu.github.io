import React from 'react';
import { createRoot } from 'react-dom/client';

import './estilos.css';

import DetailedTableApp from './components/DetailedTableApp';

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<DetailedTableApp />);
}