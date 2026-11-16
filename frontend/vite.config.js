import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O proxy evita problemas de CORS em desenvolvimento: /api -> FastAPI (porta 8000)
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
