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
    """Execute LangChain agent and return response with robust error handling."""
    agent = agent_info["agent"]

    try:
        print("🔧 Executing LangChain agent...")

        # LangGraph agents
        if "CompiledStateGraph" in str(type(agent)):
            print("🚀 Using LangGraph interface")
            config = {"configurable": {"thread_id": f"thread_{user_id}_{session_id}"}}

            try:
                if hasattr(agent, "ainvoke"):
                    response = await agent.ainvoke({"messages": [("user", query)]}, config=config)
                else:
                    response = agent.invoke({"messages": [("user", query)]}, config=config)
            except Exception as e:
                error_msg = str(e)
                print(f"❌ LangGraph execution error: {error_msg}")

                # Check if it's the tool call history error
                if "tool_calls that do not have a corresponding ToolMessage" in error_msg:
                    print("🔄 Detected tool call history error, retrying with fresh session...")

                    # Try with a fresh session (new thread_id)
                    import time

                    fresh_config = {"configurable": {"thread_id": f"fresh_{user_id}_{session_id}_{int(time.time())}"}}

                    try:
                        if hasattr(agent, "ainvoke"):
                            response = await agent.ainvoke({"messages": [("user", query)]}, config=fresh_config)
                        else:
                            response = agent.invoke({"messages": [("user", query)]}, config=fresh_config)
                        print("✅ Successfully recovered from tool call history error")
                    except Exception as retry_error:
                        print(f"❌ Fresh session retry also failed: {retry_error}")
                        # Try without config (stateless)
                        try:
                            if hasattr(agent, "ainvoke"):
                                response = await agent.ainvoke({"messages": [("user", query)]})
                            else:
                                response = agent.invoke({"messages": [("user", query)]})
                            print("✅ Successfully executed without session config")
                        except Exception as stateless_error:
                            print(f"❌ Stateless execution also failed: {stateless_error}")
                            return "❌ Desculpe, ocorreu um erro técnico. Tente novamente em alguns instantes."
                else:
                    # For other errors, try without config
                    print("🔄 Retrying without session config...")
                    try:
                        if hasattr(agent, "ainvoke"):
                            response = await agent.ainvoke({"messages": [("user", query)]})
                        else:
                            response = agent.invoke({"messages": [("user", query)]})
                        print("✅ Successfully executed without session config")
                    except Exception as stateless_error:
                        print(f"❌ Stateless execution also failed: {stateless_error}")
                        return f"❌ Desculpe, ocorreu um erro técnico: {str(stateless_error)}"

        # Traditional LangChain agents
        elif hasattr(agent, "ainvoke"):
            print("🚀 Using ainvoke method")
            response = await agent.ainvoke({"input": query})
        elif hasattr(agent, "invoke"):
            print("🚀 Using invoke method")
            response = agent.invoke({"input": query})
        else:
            raise Exception("Agent has no compatible invoke method")

        print(f"📤 Raw response type: {type(response)}")

        # Extract response content
        if isinstance(response, dict):
            if "messages" in response and response["messages"]:
                print(f"📨 Found {len(response['messages'])} messages in response")
                last_message = response["messages"][-1]
                final_content = last_message.content if hasattr(last_message, "content") else str(last_message)
                print("📝 Extracted content from last message")
                return final_content
            else:
                final_content = response.get("output", response.get("result", str(response)))
                print("📝 Extracted from dict keys")
                return final_content
        else:
            print("📝 Using direct string conversion")
            return str(response)

    except Exception as e:
        print(f"❌ LangChain execution error: {e}")
        # Always return something, never let it fail completely
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
