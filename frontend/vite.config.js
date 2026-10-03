import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api/* do lokalnego backendu FastAPI (uvicorn na porcie 8000),
// żeby w dev nie trzeba było konfigurować CORS ani pełnych URL-i w fetch().
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
