import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite serves the React app on :5173 and proxies /api/* to the FastAPI backend on :8765.
// Run:  uv run specguard serve --port 8765   in one terminal
//       npm run dev                          in another
// Then open http://127.0.0.1:5173/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
