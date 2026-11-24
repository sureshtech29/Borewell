import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the API runs on :8000; in production nginx proxies /api (see nginx.conf.template).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
  build: { sourcemap: false, chunkSizeWarningLimit: 700 },
});
