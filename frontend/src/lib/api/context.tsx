import { ApiClient } from "@/lib/api/api-client";
import { fastApiAdapter } from "@/lib/api/adapters";
import { CrudService } from "@/lib/api/services/crud";
import type { BackendAdapter } from "@/lib/api/types";
import type React from "react";
import { createContext, useCallback, useContext, useState } from "react";

/**
 * Hands the `ApiClient` and CRUD services to hooks (`useCrud`). Template version of the fleet's
 * DataProvider: no user/session state here, because the template ships no login. An app that adds
 * auth keeps this provider and layers its auth store/service on top (see `lib/auth/auth-store.ts`).
 */
interface DataProviderContextType {
  client: ApiClient;
  createCrudService: <T = unknown>(endpoint: string) => CrudService<T>;
}

const DataProviderContext = createContext<DataProviderContextType | null>(null);

interface DataProviderProps {
  children: React.ReactNode;
  adapter?: BackendAdapter;
  /** Open-identity stub (local/test only): sent as the bearer while there is no session token. */
  fallbackToken?: () => string | null | undefined;
}

export function DataProvider({
  children,
  adapter = fastApiAdapter,
  fallbackToken,
}: DataProviderProps) {
  const [client] = useState(() => new ApiClient(adapter, { fallbackToken }));
  const createCrudService = useCallback(
    <T,>(endpoint: string) => new CrudService<T>(client, endpoint),
    [client]
  );
  return (
    <DataProviderContext.Provider value={{ client, createCrudService }}>
      {children}
    </DataProviderContext.Provider>
  );
}

export function useDataProvider(): DataProviderContextType {
  const context = useContext(DataProviderContext);
  if (!context) throw new Error("useDataProvider must be used inside <DataProvider>");
  return context;
}
