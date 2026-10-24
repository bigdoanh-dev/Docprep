import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5196, strictPort: true, fs: { allow: [fileURLToPath(new URL('..', import.meta.url))] } },
  build: { outDir: '../docs/design/approved-v6/preview', emptyOutDir: true },
});
