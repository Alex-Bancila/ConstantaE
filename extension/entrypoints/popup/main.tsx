import React from 'react';
import ReactDOM from 'react-dom/client';
import { getUiLanguage } from '@/lib/i18n';
import App from './App.tsx';
import './style.css';

document.documentElement.lang = getUiLanguage();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
