import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/spooky-db/',
  // Copy large static data files to build output
  publicDir: 'public',
  build: {
    rollupOptions: {
      // Optimize chunk sizes
    },
    // Increase asset size limit if needed for large JSON
    assetsInlineLimit: 0, // Don't inline large JSON
  },
})
