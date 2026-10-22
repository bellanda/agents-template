import { useTheme } from "@/components/theme";
import { Toaster as Sonner, type ToasterProps } from "sonner";

/**
 * Toaster único do app. `richColors` (padrão da frota, 2026-10-22): erro vermelho, sucesso
 * verde, aviso amarelo, info azul. O tema vem do ThemeProvider (sempre "light"/"dark").
 */
const Toaster = ({ ...props }: ToasterProps) => {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={theme}
      richColors
      className="toaster group"
      position="top-right"
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      {...props}
    />
  );
};

export { Toaster };
