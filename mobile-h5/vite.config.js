import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://124.222.29.229:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://124.222.29.229:8000',
        changeOrigin: true,
      },
      '/logout': {
        target: 'http://124.222.29.229:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://124.222.29.229:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://124.222.29.229:8000',
        changeOrigin: true,
      },
    },
  },
})
