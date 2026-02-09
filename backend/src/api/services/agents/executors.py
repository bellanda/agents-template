from typing import Any


def _extract_message_content(agent_response: Any) -> str:
    """Best-effort extraction of the final assistant content from LangGraph output."""
    if isinstance(agent_response, str):
        return agent_response

    if isinstance(agent_response, dict):
        messages = agent_response.get("messages") or agent_response.get("output")
        if messages:
            last = messages[-1]
            content = getattr(last, "content", None) if not isinstance(last, dict) else last.get("content")
            if content:
                return content if isinstance(content, str) else str(content)
        return str(agent_response)

    return str(agent_response)


async def execute_agent(agent_info: dict, query: str, session_id: str) -> str:
    """Execute agent and return the final response."""
    agent = agent_info["agent"]
    agent_mode = agent_info.get("mode", "single-shot")

    config: dict = {"configurable": {"thread_id": session_id}}

    try:
        response = await agent.ainvoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
        )
        return _extract_message_content(response)
    except Exception as e:
        print(f"❌ Agent execution error: {e}")
        return f"❌ Desculpe, ocorreu um erro inesperado: {str(e)}"


async def call_agent_async(query: str, session_id: str, model_id: str, agents_registry: dict) -> str:
    """Execute agent and return response."""
    if model_id not in agents_registry:
        available = list(agents_registry.keys())
        raise Exception(f"Model '{model_id}' not found. Available: {available}")

    agent_info = agents_registry[model_id]

    print("\n🤖 === AGENT EXECUTION ===")
    print(f"📋 Agent: {model_id}")

    # Avoid printing massive base64 strings if query is a list (multimodal)
    if isinstance(query, list):
        print("💬 User Query: [Multimodal Content]")
    else:
        print(f"💬 User Query: {query}")

    response = await execute_agent(agent_info, query, session_id)

    print(f"✅ Final Response: {response[:150]}{'...' if len(response) > 150 else ''}")
    return response
