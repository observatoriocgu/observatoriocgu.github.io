import React from 'react';
import { createRoot } from 'react-dom/client';

import './estilos.css';

import HistoryPage from './components/HistoryPage';

const container = document.getElementById('root');
if (container) {
  const root = createRoot(container);
  root.render(<HistoryPage />);
}
