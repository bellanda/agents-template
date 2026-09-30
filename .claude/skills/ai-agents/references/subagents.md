# Subagentes (delegação)

> Reference do gate `ai-agents`. Canônico: `backend/src/api/core/agents/subagents.py` e
> `backend/agents/research_supervisor_agent/` (supervisor) + `…/tools/delegate_research.py`.

## Quando (e quando NÃO)

Delegue quando o especialista tem **prompt/tools próprios** ou um **loop longo** cujas mensagens
intermediárias inchariam o contexto do supervisor (pesquisa web, análise de documento, consulta a dados).
O supervisor só vê a resposta FINAL. Um agente com poucas tools e loop curto NÃO precisa de subagente;
passos fixos → pipeline de `complete*` (`one-shot-structured.md`).

## Padrão

```python
researcher = create_agent(                       # construído 1× no import
    model=init_model(Models.OpenRouter.GLM_5_3_FLASH, max_tokens=3000),
    tools=[web_search], system_prompt=RESEARCHER_PROMPT,
    checkpointer=False, name="researcher",       # stateless — OBRIGATÓRIO
)

@tool("delegate_research")
async def delegate_research(question: str, config: RunnableConfig) -> str:
    """Delega UMA pergunta autocontida a um pesquisador (ele não vê a conversa)."""
    return await run_subagent(researcher, question, name="researcher", parent_config=config)
```

O supervisor tem `tools=[delegate_research]` e segue o contrato normal de `agents-and-tools.md`.

## Invariantes (o módulo já encoda — não contorne)

1. **`checkpointer=False`** no especialista: dentro da tool, o subgrafo herdaria o checkpointer do
   supervisor e gravaria o loop interno sob o thread do chat.
2. **Não aparece no chat:** toda run leva `SUBAGENT_RUN_TAG` (`"nostream"`); `streaming.py` descarta
   esses eventos. O usuário vê a tool `delegate_*`, não os tokens do especialista.
3. **Continua cobrado:** callbacks + metadata propagam; `agent_id` ganha sufixo `:<name>`
   (`"research-supervisor-agent:researcher"`) → custo por especialista consultável.
4. O prompt do especialista fala com OUTRO AGENTE (relatório curto, factual), não com o usuário.
5. Uma pergunta autocontida por chamada; composta → várias chamadas (paralelizáveis pelo modelo).
6. Limite saída do especialista (`max_tokens`) e número de buscas/tools no prompt: é o controle de custo.
