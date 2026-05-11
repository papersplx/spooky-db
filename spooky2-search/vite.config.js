import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/spooky-db/',
  publicDir: 'public',
  server: {
    port: 5173,
    proxy: {
      // Proxy API requests to avoid CORS issues during local development
      '/api': {
        target: 'https://spooky-db.onrender.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    rollupOptions: {
    },
    assetsInlineLimit: 0,
  },
})
