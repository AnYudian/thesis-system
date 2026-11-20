import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 监听所有网卡：老师和同学在同一局域网时，用本机 IPv4（如 http://172.20.10.3:5173）就能打开。
    // 只监听 localhost 的话，别人连进来会被直接拒绝。
    host: true,
    port: 5173,
    // 开发期把 /api 转发给本机后端：前端代码里永远写相对路径 /api/xxx，
    // 既不用处理跨域，也不用在打包时改域名（生产用 Nginx 反代到同源）。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
