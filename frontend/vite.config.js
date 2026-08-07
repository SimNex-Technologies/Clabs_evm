import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // During `npm run dev`, proxy API/symbol requests to the FastAPI backend
    // (run separately via `python3 main.py`) so the kiosk can be developed
    // with hot reload instead of rebuilding into dist/ every time.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/symbols': 'http://127.0.0.1:8000',
    },
  },
})
