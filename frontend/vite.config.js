import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

// Settings live in .env.frontend (loaded because the scripts run vite with `--mode frontend`).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [vue()],
    server: {
      port: Number(env.FRONTEND_PORT),
      // The backend only accepts the origins listed in its CORS_ORIGINS: never move to another port.
      strictPort: true,
    },
  };
});
