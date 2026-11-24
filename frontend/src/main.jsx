import '@fontsource/atkinson-hyperlegible/400.css';
import '@fontsource/atkinson-hyperlegible/700.css';
import '@fontsource/noto-sans-telugu/400.css';
import '@fontsource/noto-sans-telugu/600.css';
import '@fontsource/noto-sans-telugu/700.css';
import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import { MetaProvider } from './hooks/useMeta.jsx';
import { I18nProvider } from './i18n/index.jsx';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <I18nProvider>
      <MetaProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </MetaProvider>
    </I18nProvider>
  </React.StrictMode>,
);
