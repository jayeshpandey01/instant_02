import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    assetsDir: 'assets'
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8899',
        changeOrigin: true,
        secure: false
      }
    }
  }
});
