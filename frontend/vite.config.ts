import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Прокси /api на бэкенд FastAPI в dev-режиме — без CORS-настроек.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
