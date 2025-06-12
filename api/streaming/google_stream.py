import json
from typing import Dict

from google.adk.sessions import InMemorySessionService
from google.genai import types

from api.utils.tools import (
    generate_error_message,
    generate_result_message,
    generate_status_message,
    generate_thinking_message,
)


async def stream_google_agent(
    agent_info: Dict,
    query: str,
    user_id: str,
    session_id: str,
    completion_id: str,
    current_timestamp: int,
    requested_model: str,
    session_service: InMemorySessionService,
):
    """Stream Google agent responses with detailed debugging."""
    print("🌊 [STREAM] === INICIANDO GOOGLE STREAM ===")
    print(f"🌊 [STREAM] Model: {requested_model}")
    print(f"🌊 [STREAM] Query: {query}")
    print(f"🌊 [STREAM] User ID: {user_id}")
    print(f"🌊 [STREAM] Session ID: {session_id}")

    runner = agent_info["runner"]
    app_name = f"{agent_info['agent_dir']}_app"

    # Send initial status message
    initial_status = generate_status_message("processing", "Iniciando processamento da solicitação...")
    initial_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": current_timestamp,
        "model": requested_model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": f"\n{initial_status}\n"},
                "logprobs": None,
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(initial_chunk)}\n\n"

    try:
        session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        print(f"🌊 [STREAM] ✅ Sessão criada: {session_id}")

        # Send session created status
        session_status = generate_status_message("completed", "Sessão estabelecida com sucesso")
        session_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": current_timestamp,
            "model": requested_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": f"\n{session_status}\n"},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(session_chunk)}\n\n"

    except Exception as e:
        print(f"🌊 [STREAM] ⚠️ Sessão já existe ou erro: {e}")
        pass

    content = types.Content(role="user", parts=[types.Part(text=query)])
    print("🌊 [STREAM] ✅ Content criado para runner")

    # Send thinking message
    thinking_msg = generate_thinking_message("Analisando a solicitação e preparando resposta...")
    thinking_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": current_timestamp,
        "model": requested_model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": f"\n{thinking_msg}\n"},
                "logprobs": None,
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(thinking_chunk)}\n\n"

    try:
        print("🌊 [STREAM] 🚀 Iniciando runner.run_async...")
        event_count = 0

        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            event_count += 1
            print(f"🌊 [STREAM] 📨 Evento #{event_count} recebido")
            print(f"🌊 [STREAM] 📨 Tipo: {type(event)}")
            print(f"🌊 [STREAM] 📨 Atributos: {[attr for attr in dir(event) if not attr.startswith('_')]}")

            # Check if event has content
            if hasattr(event, "content"):
                print(f"🌊 [STREAM] 📄 Event.content existe: {event.content is not None}")

                if event.content:
                    print(f"🌊 [STREAM] 📄 Content type: {type(event.content)}")
                    print(
                        f"🌊 [STREAM] 📄 Content attributes: {[attr for attr in dir(event.content) if not attr.startswith('_')]}"
                    )

                    if hasattr(event.content, "parts"):
                        print(f"🌊 [STREAM] 📄 Parts exist: {len(event.content.parts) if event.content.parts else 0} parts")

                        if event.content.parts:
                            for i, part in enumerate(event.content.parts):
                                print(f"🌊 [STREAM] 📄 Part {i}: {type(part)}")
                                if hasattr(part, "text"):
                                    event_text = part.text
                                    print(f"🌊 [STREAM] 📄 Text length: {len(event_text) if event_text else 0}")
                                    print(
                                        f"🌊 [STREAM] 📄 Text preview: '{event_text[:200] if event_text else 'EMPTY'}{'...' if event_text and len(event_text) > 200 else ''}'"
                                    )

                                    if event_text:
                                        chunk_data = {
                                            "id": completion_id,
                                            "object": "chat.completion.chunk",
                                            "created": current_timestamp,
                                            "model": requested_model,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {"content": event_text},
                                                    "logprobs": None,
                                                    "finish_reason": None,
                                                }
                                            ],
                                        }
                                        print("🌊 [STREAM] 📤 Enviando chunk para cliente...")
                                        yield f"data: {json.dumps(chunk_data)}\n\n"
                                    else:
                                        print(f"🌊 [STREAM] ⚠️ Part {i} sem texto")
                                else:
                                    print(f"🌊 [STREAM] ⚠️ Part {i} sem atributo text")
                        else:
                            print("🌊 [STREAM] ⚠️ Content.parts está vazio")
                    else:
                        print("🌊 [STREAM] ⚠️ Content sem atributo parts")
                else:
                    print("🌊 [STREAM] ⚠️ Event.content é None")
            else:
                print("🌊 [STREAM] ⚠️ Evento sem atributo content")

            # Check if final response
            if hasattr(event, "is_final_response"):
                is_final = event.is_final_response()
                print(f"🌊 [STREAM] 🏁 is_final_response: {is_final}")
                if is_final:
                    print("🌊 [STREAM] 🏁 EVENTO FINAL DETECTADO!")

                    # Send completion status
                    completion_status = generate_result_message("success", "Resposta gerada com sucesso")
                    completion_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": current_timestamp,
                        "model": requested_model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\n{completion_status}\n"},
                                "logprobs": None,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(completion_chunk)}\n\n"
                    break
            else:
                print("🌊 [STREAM] ⚠️ Evento sem método is_final_response")

        print(f"🌊 [STREAM] ✅ Stream finalizado! Total de eventos: {event_count}")

    except Exception as e:
        print(f"❌ [STREAM] ERRO CRÍTICO no streaming: {e}")
        print(f"❌ [STREAM] Tipo do erro: {type(e)}")
        import traceback

        print("❌ [STREAM] Traceback completo:")
        traceback.print_exc()

        # Send error message using HPEAgents markup
        error_msg = generate_error_message(f"Erro na geração: {str(e)}")
        error_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": current_timestamp,
            "model": requested_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": f"\n{error_msg}\n"},
                    "logprobs": None,
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

        if "Session not found" in str(e):
            print("🌊 [STREAM] 🔄 Tentando com sessão simplificada...")

            # Send retry status
            retry_status = generate_status_message("processing", "Tentando reconectar com sessão simplificada...")
            retry_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": current_timestamp,
                "model": requested_model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": f"\n{retry_status}\n"},
                        "logprobs": None,
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(retry_chunk)}\n\n"

            # Retry with simplified session
            simple_session_id = f"session_{abs(hash(session_id)) % 10000}"
            session_service.create_session(app_name=app_name, user_id=user_id, session_id=simple_session_id)
            async for event in runner.run_async(user_id=user_id, session_id=simple_session_id, new_message=content):
                if hasattr(event, "content") and event.content and event.content.parts:
                    event_text = event.content.parts[0].text
                    if event_text:
                        chunk_data = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": current_timestamp,
                            "model": requested_model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": event_text},
                                    "logprobs": None,
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"

                if event.is_final_response():
                    break
