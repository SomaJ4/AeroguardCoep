import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['sol-packable-timorously.ngrok-free.dev'],
  },
  optimizeDeps: {
    entries: ['src/main.tsx'],
    include: ['maplibre-gl'],
  },
})
