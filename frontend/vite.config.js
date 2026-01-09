import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import vueDevTools from 'vite-plugin-vue-devtools'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig(({ mode }) => {
  const envDir = path.resolve(__dirname, '..')
  const env = loadEnv(mode, envDir, '')

  return {
    plugins: [vue(), vueDevTools()],
    server: {
      port: Number(env.VITE_FRONTEND_PORT) || 8020,
      host: true,
    },
    base: env.VITE_BASE_URL + '/' || '/eva-vr/',

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },

    // 🔑 THIS IS THE IMPORTANT PART
    define: {
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(env.VITE_BACKEND_URL),
      'import.meta.env.VITE_FRONTEND_PORT': JSON.stringify(env.VITE_FRONTEND_PORT),
      'import.meta.env.VITE_BACKEND_PORT': JSON.stringify(env.VITE_BACKEND_PORT),
      'import.meta.env.VITE_BASE_URL': JSON.stringify(env.VITE_BASE_URL),
    }
  }
})
