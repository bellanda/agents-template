from typing import Dict

from google.adk.sessions import InMemorySessionService
from google.genai import types


async def execute_google_agent(
    agent_info: Dict, query: str, user_id: str, session_id: str, session_service: InMemorySessionService
) -> str:
    """Execute Google agent and return response."""
    print(f"🤖 [GOOGLE] Executando agente: {agent_info.get('name')}")
    print(f"🤖 [GOOGLE] Query: {query}")

    runner = agent_info["runner"]
    app_name = f"{agent_info['agent_dir']}_app"

    # Create session if needed
    try:
        session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        print(f"🤖 [GOOGLE] Sessão criada: {session_id}")
    except Exception as e:
        print(f"🤖 [GOOGLE] Sessão já existe: {e}")
        pass  # Session might already exist

    content = types.Content(role="user", parts=[types.Part(text=query)])

    try:
        print("🤖 [GOOGLE] Iniciando runner.run_async...")
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            print(f"🤖 [GOOGLE] Evento recebido: {type(event)}")
            if event.is_final_response() and event.content and event.content.parts:
                response = event.content.parts[0].text
                print(f"🤖 [GOOGLE] Resposta final: {response[:100]}...")
                return response
    except Exception as e:
        print(f"❌ [GOOGLE] Erro na execução: {e}")
        if "Session not found" in str(e):
            # Retry with simplified session ID
            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
            session_service.create_session(app_name=app_name, user_id=user_id, session_id=simple_session_id)
            async for event in runner.run_async(user_id=user_id, session_id=simple_session_id, new_message=content):
                if event.is_final_response() and event.content and event.content.parts:
                    return event.content.parts[0].text
        raise Exception(f"Google agent execution failed: {e}")

    return "No response from agent"


async def execute_langchain_agent(agent_info: Dict, query: str, user_id: str, session_id: str) -> str:
    """Execute LangChain agent and return response (AgentExecutor padrão)."""
    agent = agent_info["agent"]  # Deve ser sempre AgentExecutor
    try:
        response = await agent.ainvoke({"input": query})
        return str(response)
    except Exception as e:
        print(f"❌ LangChain execution error: {e}")
        return f"❌ Desculpe, ocorreu um erro inesperado: {str(e)}"


async def call_agent_async(
    query: str, user_id: str, session_id: str, model_id: str, agents_registry: Dict, session_service: InMemorySessionService
) -> str:
    """Execute agent and return response."""
    if model_id not in agents_registry:
        available = list(agents_registry.keys())
        raise Exception(f"Model '{model_id}' not found. Available: {available}")

    agent_info = agents_registry[model_id]
    agent_type = agent_info.get("type")

    print("\n🤖 === AGENT EXECUTION ===")
    print(f"📋 Agent: {model_id} ({agent_type})")
    print(f"💬 User Query: {query}")

    if agent_type == "google":
        response = await execute_google_agent(agent_info, query, user_id, session_id, session_service)
    elif agent_type == "langchain":
        response = await execute_langchain_agent(agent_info, query, user_id, session_id)
    else:
        raise Exception(f"Unknown agent type: {agent_type}")

    print(f"✅ Final Response: {response[:150]}{'...' if len(response) > 150 else ''}")
    return response
