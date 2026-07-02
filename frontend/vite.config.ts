import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 600_000,          // 10 min — policy upload with AI parse can be slow
        proxyTimeout: 600_000,     // 10 min
      },
    },
  },
})
