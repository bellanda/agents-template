import { useCallback, useEffect, useRef } from "react";

/**
 * Formulário que parte de um dado do servidor (query) e deixa a pessoa editar um rascunho local.
 *
 * Por que existe (auditoria 2026-11-13, core-spa-11): a frota refaz query ativa ao voltar o foco
 * (`createAppQueryClient`). O padrão antigo `useEffect(() => setForm(query.data), [query.data])`
 * reescrevia o rascunho no meio da digitação assim que o dado remoto mudava. Este hook decide:
 *
 * - primeira carga, ou troca de entidade (`entityKey` mudou): aplica o dado do servidor;
 * - o dado remoto mudou e o rascunho está LIMPO (igual ao que foi aplicado por último): aplica
 *   em silêncio, a tela se renova sozinha;
 * - o dado remoto mudou e o rascunho está SUJO: mantém o que a pessoa digitou (nunca apaga).
 *
 * Contrato: o chamador guarda o rascunho (`useState`) e passa `draft`/`setDraft`; para rascunho
 * em vários `useState`, `draft` é um objeto montado a cada render e `setDraft` distribui.
 * Depois de SALVAR, chame `markSaved()`: o rascunho vira a nova linha de base e o próximo
 * dado do servidor (ex.: com valores normalizados) volta a ser aplicado.
 */
export interface UseSyncedDraftOptions<S, D> {
  /** Dado do servidor (`query.data`); `undefined` enquanto carrega. */
  server: S | undefined;
  /** Converte o dado do servidor no formato do rascunho. */
  toDraft: (server: S) => D;
  /** Rascunho atual (lido só quando o `server` muda). */
  draft: D;
  setDraft: (draft: D) => void;
  /** Identidade da entidade editada (id): trocar de entidade sempre reaplica. */
  entityKey?: unknown;
  /** Comparação rascunho × linha de base. Padrão: JSON (suficiente para formulários). */
  isEqual?: (a: D, b: D) => boolean;
}

function jsonEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function useSyncedDraft<S, D>({
  server,
  toDraft,
  draft,
  setDraft,
  entityKey,
  isEqual = jsonEqual,
}: UseSyncedDraftOptions<S, D>): { markSaved: () => void } {
  const baseline = useRef<{ key: unknown; draft: D } | null>(null);
  const latest = useRef({ toDraft, draft, setDraft, isEqual, entityKey });

  // Antes do efeito de sincronia (efeitos rodam na ordem de declaração).
  useEffect(() => {
    latest.current = { toDraft, draft, setDraft, isEqual, entityKey };
  });

  useEffect(() => {
    if (server === undefined) return;
    const { toDraft: convert, draft: current, setDraft: apply, isEqual: same } = latest.current;
    const next = convert(server);
    const base = baseline.current;
    if (base !== null && Object.is(base.key, entityKey) && !same(current, base.draft)) {
      // Rascunho sujo: preserva. Se o servidor já reflete o rascunho (acabou de salvar),
      // avança a linha de base para a próxima mudança remota não ser tratada como edição.
      if (same(current, next)) baseline.current = { key: entityKey, draft: next };
      return;
    }
    baseline.current = { key: entityKey, draft: next };
    apply(next);
  }, [server, entityKey]);

  const markSaved = useCallback(() => {
    baseline.current = { key: latest.current.entityKey, draft: latest.current.draft };
  }, []);

  return { markSaved };
}
