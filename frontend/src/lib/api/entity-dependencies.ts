import { defineEntityMap } from "./entity-graph";

/**
 * Tabela de dependência entre entidades DESTE app (auditoria 2026-11-13, core-spa-02).
 * Cada app é dono do seu arquivo; o motor (`entity-graph.ts`) e a API (`invalidation.ts`) são
 * iguais na frota. Ver `invalidation.ts` para o uso.
 *
 * Como manter: query nova com chave de um recurso que já existe aqui não precisa de nada (a
 * chave já casa). Recurso novo: crie a entidade com `orgPaths`/`keys` e liste em `dependents`
 * de OUTRA entidade quando ela deriva dali (ex.: o painel depende de quase tudo que se grava).
 *
 * Template: sem domínio de negócio. O exemplo abaixo mostra a forma.
 */
export const ENTITY_DEPENDENCIES = defineEntityMap({
  // Exemplo (apague ao criar o app): gravar uma conta renova o painel que a soma.
  account: { keys: ["accounts"], dependents: ["dashboard"] },
  dashboard: { orgPaths: ["dashboard"], keys: ["dashboard"] },
  // Instruções do agente (`components/agent-config/use-agent-config.ts`): config ativa + versões.
  agentConfig: { keys: ["agent-config"] },
  // Lista de conversas da sidebar do chat (`components/chat/use-threads-query.ts`).
  chatThreads: { keys: ["threads"] },
});
