import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/spooky-db/',
  publicDir: 'public',
  build: {
    rollupOptions: {
    },
    assetsInlineLimit: 0,
  },
})
