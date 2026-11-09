import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { bootAppStyle } from "./lib/appearance/app-style-store";
import { bootFontSize } from "./lib/appearance/font-size";
import { installClientErrorCapture } from "./lib/observability/client-logger";
import { router } from "./router";

import "./styles.css";

// Erro não tratado + buffer offline → log do backend (`lib/observability/client-logger.ts`).
installClientErrorCapture();

// Pinta o estilo do cache (ou migra o tema antigo) antes do 1º render: sem flash de claro/escuro.
bootAppStyle();
bootFontSize();

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

if (!rootElement.innerHTML) {
  createRoot(rootElement).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>
  );
}
