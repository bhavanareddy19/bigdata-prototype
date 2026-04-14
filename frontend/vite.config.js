import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/analyze-log': 'http://localhost:8000',
      '/analyze-airflow-task': 'http://localhost:8000',
      '/analyze-k8s-pod': 'http://localhost:8000',
      '/index': 'http://localhost:8000',
      '/lineage': 'http://localhost:8000',
    },
  },
})
