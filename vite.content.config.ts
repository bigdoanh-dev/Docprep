import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5192,
    proxy: {
      "/api": {
        target: process.env.CONTENT_BACKEND_URL || "http://127.0.0.1:18882",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  build: { outDir: "dist-content", rolldownOptions: { input: "content.html" } },
});
