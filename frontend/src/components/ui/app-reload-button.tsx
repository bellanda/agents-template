import { Button } from "@/components/ui/button";
import { useIsStandalone } from "@/hooks/useIsStandalone";
import { useQueryClient } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";
import { useState } from "react";

/**
 * Recarga manual para o app instalado no celular: lá não existe F5 nem barra de endereço, e o
 * iOS ignora o `display: minimal-ui` do manifest (abre standalone, sem afordância de reload).
 * No navegador o botão some — F5 já resolve e um segundo caminho só polui o header.
 *
 * Recarrega os DADOS (`invalidateQueries`), não a página: `location.reload()` descartaria o
 * bundle e o access token em memória, forçando um bootstrap inteiro (contrato `pwa-mobile.md`).
 */
export function AppReloadButton() {
  const isStandalone = useIsStandalone();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleReload = async () => {
    setIsRefreshing(true);
    try {
      await queryClient.invalidateQueries();
    } finally {
      setIsRefreshing(false);
    }
  };

  if (!isStandalone) return null;

  return (
    <Button
      variant="outline"
      size="icon"
      className="border-input bg-background hover:bg-accent max-sm:border-transparent max-sm:bg-transparent dark:max-sm:bg-transparent"
      onClick={handleReload}
      disabled={isRefreshing}
    >
      <RotateCw className={`h-5 w-5 ${isRefreshing ? "animate-spin" : ""}`} />
      <span className="sr-only">Recarregar</span>
    </Button>
  );
}
