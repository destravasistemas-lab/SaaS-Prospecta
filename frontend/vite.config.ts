import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Permite acessar o dev server por um domínio externo (ex: túnel ngrok)
    // sem o bloqueio "Blocked request. This host is not allowed" do Vite.
    allowedHosts: ['ngoc-subumbellate-jayce.ngrok-free.dev', 'greedily-trunks-morally.ngrok-free.dev'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
