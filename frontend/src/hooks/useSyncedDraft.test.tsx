// @vitest-environment jsdom (o template não define `test.environment` no vite.config)
import { act, renderHook } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { useSyncedDraft } from "./useSyncedDraft";

interface Server {
  id: number;
  name: string;
}

/** Formulário mínimo: rascunho local alimentado pela "query" (`server`). */
function useForm(initial: Server | undefined) {
  const [server, setServer] = useState<Server | undefined>(initial);
  const [name, setName] = useState("");
  const { markSaved } = useSyncedDraft({
    server,
    toDraft: (s) => ({ name: s.name }),
    draft: { name },
    setDraft: (d) => setName(d.name),
    entityKey: server?.id,
  });
  return { name, setName, setServer, markSaved };
}

describe("useSyncedDraft (core-spa-11)", () => {
  it("semeia o rascunho na primeira carga", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    expect(result.current.name).toBe("Ana");
  });

  it("rascunho limpo acompanha o refetch", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    act(() => result.current.setServer({ id: 1, name: "Ana Maria" }));
    expect(result.current.name).toBe("Ana Maria");
  });

  it("rascunho sujo NÃO é apagado quando o dado remoto muda", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    act(() => result.current.setName("Ana digitando"));
    act(() => result.current.setServer({ id: 1, name: "Outra pessoa salvou" }));
    expect(result.current.name).toBe("Ana digitando");
  });

  it("trocar de entidade sempre reaplica, mesmo com rascunho sujo", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    act(() => result.current.setName("sujo"));
    act(() => result.current.setServer({ id: 2, name: "Bia" }));
    expect(result.current.name).toBe("Bia");
  });

  it("depois de salvar (servidor igual ao rascunho) volta a acompanhar o servidor", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    act(() => result.current.setName("Ana B"));
    act(() => result.current.setServer({ id: 1, name: "Ana B" })); // refetch pós-save
    act(() => result.current.setServer({ id: 1, name: "Ana C" })); // outra pessoa edita
    expect(result.current.name).toBe("Ana C");
  });

  it("markSaved adota valor normalizado pelo servidor", () => {
    const { result } = renderHook(() => useForm({ id: 1, name: "Ana" }));
    act(() => result.current.setName("  ana  "));
    act(() => result.current.markSaved());
    act(() => result.current.setServer({ id: 1, name: "ana" }));
    expect(result.current.name).toBe("ana");
  });
});
