import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { installClientErrorCapture } from "./lib/observability/client-logger";
import { router } from "./router";

import "./styles.css";

// Erro não tratado + buffer offline → log do backend (`lib/observability/client-logger.ts`).
installClientErrorCapture();

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

if (!rootElement.innerHTML) {
  createRoot(rootElement).render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>
  );
}
