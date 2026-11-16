import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O front chama /api/...; em desenvolvimento, o Vite repassa para a API FastAPI na porta 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", rewrite: (p) => p.replace(/^\/api/, "") } },
  },
});
