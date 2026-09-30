import { tanstackRouter } from "@tanstack/router-plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "url";
import { defineConfig } from "vite";
import viteTsConfigPaths from "vite-tsconfig-paths";

import tailwindcss from "@tailwindcss/vite";

const config = defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  optimizeDeps: {
    include: [
      "streamdown",
      "@streamdown/mermaid",
      "@streamdown/math",
      "@streamdown/cjk",
      "@streamdown/code",
      "shiki",
      "mermaid",
      "katex",
    ],
  },
  server: {
    proxy: {
      "/api": {
        // Dev-server proxy only. Same value as yaml `vite.backend_url` (host dev default);
        // the docker bundle uses same-origin /api through nginx, so this never ships.
        target: process.env.VITE_BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  plugins: [
    tanstackRouter({
      target: "react",
      autoCodeSplitting: true,
    }),
    viteTsConfigPaths({
      projects: ["./tsconfig.json"],
    }),
    tailwindcss(),
    viteReact(),
  ],
});

export default config;
