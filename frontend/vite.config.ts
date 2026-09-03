import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Necesario para que el hot-reload funcione con volumenes montados en Docker.
    watch: { usePolling: true, interval: 300 },
    // El frontend habla con el backend por el mismo origen: /api -> backend:8000.
    // Asi no hay CORS en desarrollo y la config es igual que en produccion.
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
