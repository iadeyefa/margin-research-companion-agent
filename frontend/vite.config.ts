import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        configure: (proxy) => {
          // Rewrite Location headers on redirects so the browser follows them
          // through the proxy instead of directly to the backend port.
          proxy.on('proxyRes', (proxyRes) => {
            const location = proxyRes.headers['location']
            if (location) {
              proxyRes.headers['location'] = location.replace(
                /^http:\/\/(localhost|127\.0\.0\.1):3000/,
                '',
              )
            }
          })
        },
      },
    },
  },
})
