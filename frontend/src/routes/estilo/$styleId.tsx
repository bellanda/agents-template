import { useAppStyle } from "@/hooks/useAppStyle";
import { isAppStyleId } from "@/lib/appearance/app-styles";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

/**
 * Link que aplica um estilo e segue para a tela inicial: `/estilo/nitido`.
 *
 * Para mandar à equipe com o estilo já escolhido — quem abre só vê a tela inicial.
 */
export const Route = createFileRoute("/estilo/$styleId")({
  component: AppStyleLinkPage,
});

function AppStyleLinkPage() {
  const { styleId } = Route.useParams();
  const { chooseStyle } = useAppStyle();
  const navigate = useNavigate();

  // No efeito e não no `beforeLoad`: o preload por hover (`defaultPreload: "intent"`) roda o
  // `beforeLoad`, e passar o mouse num link destes trocaria o estilo da conta.
  useEffect(() => {
    if (isAppStyleId(styleId)) chooseStyle(styleId);
    // `replace`: o link some do histórico e o "voltar" não reaplica nada.
    void navigate({ to: "/", replace: true });
  }, [styleId, chooseStyle, navigate]);

  return null;
}
