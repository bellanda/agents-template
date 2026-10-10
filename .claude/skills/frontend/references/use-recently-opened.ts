import { useCallback, useState } from "react";

const RECENT_STORAGE_PREFIX = "recent-opened:";
/** Cinco: uma linha de cards mínimos no desktop. Mais que isso vira uma segunda lista. */
const MAX_RECENT_ENTRIES = 5;

/** O que a faixa de recentes precisa para desenhar um card — gravado no clique, sem fetch. */
export interface RecentEntry {
  id: string;
  title: string;
  subtitle?: string;
  imageUrl?: string | null;
}

function isRecentEntry(value: unknown): value is RecentEntry {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as RecentEntry).id === "string" &&
    typeof (value as RecentEntry).title === "string"
  );
}

function readRecentEntries(storageKey: string): RecentEntry[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isRecentEntry).slice(0, MAX_RECENT_ENTRIES) : [];
  } catch {
    return [];
  }
}

function writeRecentEntries(storageKey: string, entries: RecentEntry[]) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(entries));
  } catch {
    // Storage indisponível (aba privada, cota): a faixa vale só enquanto a tela está montada.
  }
}

/**
 * Últimos itens abertos a partir de uma tela de lista (pedido do usuário, 2026-10-09):
 * buscou uma placa, abriu um carro lá do fim, voltou — a faixa "Abertos recentemente" põe
 * ele a um clique, sem lembrar qual era nem refazer a busca.
 *
 * `markOpened` vai no handler que navega pro detalhe, com o que o card precisa mostrar (o
 * item já está na mão — nada de fetch por recente). Por navegador, em `localStorage`, com
 * chave por tela + org: é atalho pessoal de quem está naquela máquina, não dado da loja.
 */
export function useRecentlyOpened(screenKey: string) {
  const storageKey = RECENT_STORAGE_PREFIX + screenKey;
  const [entries, setEntries] = useState(() => readRecentEntries(storageKey));

  const markOpened = useCallback(
    (entry: RecentEntry) => {
      setEntries((current) => {
        const next = [entry, ...current.filter((item) => item.id !== entry.id)].slice(
          0,
          MAX_RECENT_ENTRIES
        );
        writeRecentEntries(storageKey, next);
        return next;
      });
    },
    [storageKey]
  );

  const clearRecents = useCallback(() => {
    setEntries([]);
    writeRecentEntries(storageKey, []);
  }, [storageKey]);

  return { recentEntries: entries, markOpened, clearRecents };
}
