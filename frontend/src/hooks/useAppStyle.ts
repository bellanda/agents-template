import { useUserId } from "@/hooks/useUserId";
import { fetchAccountMe, patchAppStyle } from "@/lib/api/accounts";
import {
  applyAppStyle,
  getActiveAppStyle,
  isAppStyleChoicePending,
  markAppStyleChosen,
  setAccount,
  subscribeAppStyle,
} from "@/lib/appearance/app-style-store";
import { findAppStyle, type AppStyleId, type AppStyleMode } from "@/lib/appearance/app-styles";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useSyncExternalStore } from "react";

/**
 * Estilo ativo + a escolha explícita da pessoa (seletor do header ou link `/estilo/<id>`).
 *
 * Só a escolha grava na conta: o boot nunca envia o que achou no cache, senão num PC
 * compartilhado o estilo de uma pessoa iria parar na conta da outra.
 */
export function useAppStyle() {
  const [userId] = useUserId();
  const style = useSyncExternalStore(subscribeAppStyle, getActiveAppStyle);

  const chooseStyle = useCallback(
    (id: AppStyleId) => {
      applyAppStyle(id);
      markAppStyleChosen(userId);
      // Falhar em gravar a preferência não é algo que a pessoa resolva, e o cache já segura
      // este aparelho.
      void patchAppStyle(userId, id).catch(() => {});
    },
    [userId]
  );

  return { style, mode: findAppStyle(style).mode, chooseStyle, previewStyle: applyAppStyle };
}

/** Monta UMA vez na casca: busca `/accounts/me` e alimenta o store (segue a conta). */
export function useAppStyleAccountSync(): void {
  const [userId] = useUserId();
  const { data } = useQuery({
    queryKey: ["accounts", "me", userId],
    queryFn: () => fetchAccountMe(userId),
    meta: { silentError: true },
  });
  useEffect(() => {
    if (data) setAccount({ userId: data.id, appStyle: data.uiPreferences.appStyle });
  }, [data]);
}

/**
 * `true` na primeira entrada de quem nunca escolheu um estilo: o dialog de boas-vindas abre
 * sozinho. Só a casca de trabalho monta isto — nunca tela operacional/kiosk/pública.
 */
export function useAppStyleChoicePending(): boolean {
  return useSyncExternalStore(subscribeAppStyle, isAppStyleChoicePending);
}

/** Só o modo (claro/escuro) do estilo ativo — para quem lê e não troca o estilo. */
export function useAppStyleMode(): AppStyleMode {
  const style = useSyncExternalStore(subscribeAppStyle, getActiveAppStyle);
  return findAppStyle(style).mode;
}
