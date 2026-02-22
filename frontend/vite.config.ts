import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Separar vendor chunks para melhor caching no navegador
    rollupOptions: {
      output: {
        manualChunks: {
          // Leaflet e dependências de mapa (~200KB) - carregado apenas nas páginas de mapa
          leaflet: ['leaflet', 'react-leaflet', 'react-leaflet-cluster'],
          // React core (~140KB) - raramente muda entre deploys
          react: ['react', 'react-dom', 'react-router-dom'],
          // State & data fetching (~50KB)
          data: ['@tanstack/react-query', 'zustand', 'axios'],
          // UI libraries (~30KB)
          ui: ['react-hot-toast', 'react-hook-form', 'clsx', 'tailwind-merge'],
        },
      },
    },
    // Aumentar limite de aviso (leaflet é grande mas necessário)
    chunkSizeWarningLimit: 600,
  },
})
