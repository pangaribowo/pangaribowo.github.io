import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Situs Pages user (pangaribowo.github.io) diserve dari domain root -> base '/'
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          vendor: ['react', 'react-dom', 'framer-motion', 'lucide-react'],
        },
      },
    },
  },
})
