import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, API calls go to the FastAPI server on port 8000.
export default defineConfig({
  plugins: [react()],
  // one small app bundle (map library included); no need to split it
  build: { chunkSizeWarningLimit: 800 },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    },
  },
})
