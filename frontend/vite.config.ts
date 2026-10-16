import { tanstackRouter } from "@tanstack/router-plugin/vite";
import viteReact from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "url";
import { defineConfig, type Plugin } from "vite";
import viteTsConfigPaths from "vite-tsconfig-paths";

import tailwindcss from "@tailwindcss/vite";

// Build id da atualização forçada pós-deploy (decisão do usuário 2026-10-16, ver src/lib/app-version).
// BUILD_ID do ambiente (ex.: SHA do commit) ou, sem ele, o instante da build: cada build tem
// id único, então todo deploy é detectado mesmo sem mudar o commit.
const BUILD_ID = process.env.BUILD_ID || new Date().toISOString();

// Emite dist/version.json ({"buildId"}) — o nginx serve no-cache e o watcher compara com o
// __APP_BUILD_ID__ embutido no bundle. Só no build de produção; `bun dev` não tem version.json.
function emitVersionJson(): Plugin {
  return {
    name: "emit-version-json",
    apply: "build",
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "version.json",
        source: JSON.stringify({ buildId: BUILD_ID }),
      });
    },
  };
}

const config = defineConfig({
  define: { __APP_BUILD_ID__: JSON.stringify(BUILD_ID) },
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
    emitVersionJson(),
  ],
});

export default config;
