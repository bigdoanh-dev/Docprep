import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "BACKEND_");
  // `uv run yhdp serve`: its routes are /api/*, and the reviewer app (web-review) is at /review/.
  const target =
    process.env.BACKEND_URL || env.BACKEND_URL || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": { target, changeOrigin: true },
        "/review": { target, changeOrigin: true },
      },
    },
    build: {
      rolldownOptions: {
        output: {
          codeSplitting: {
            groups: [
              {
                name: "framework",
                test: /node_modules\/(react|react-dom|react-router|scheduler)/,
              },
              { name: "motion", test: /node_modules\/(motion|framer-motion)/ },
              {
                name: "reading",
                test: /node_modules\/(react-markdown|remark|rehype|micromark|mdast|hast|unified|vfile)/,
              },
              { name: "demo-data", test: /src\/lib\/demo\// },
            ],
          },
        },
      },
    },
  };
});
