import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 开发代理:前端(5173)请求 /api/xxx 时,转发给后端(8000)
    // 解决跨域:浏览器只看到"同源"请求,实际由 Vite 转发
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
