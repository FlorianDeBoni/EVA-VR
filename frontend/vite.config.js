import { fileURLToPath } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

const page = (name) => fileURLToPath(new URL(name, import.meta.url));

// Settings live in .env.frontend (loaded because the scripts run vite with `--mode frontend`).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [vue()],
    // Two pages: the app, and the full-screen view of the final picture ("Go to VR").
    build: { rollupOptions: { input: { main: page("index.html"), vr: page("vr.html") } } },
    server: {
      port: Number(env.FRONTEND_PORT),
      // The backend only accepts the origins listed in its CORS_ORIGINS: never move to another port.
      strictPort: true,
    },
  };
});
