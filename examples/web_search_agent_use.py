import asyncio

from agents.web_search_agent.agent import root_agent


async def main():
    # Use astream_events para receber todos os eventos do agente
    async for event in root_agent.astream_events(
        {"messages": [{"role": "user", "content": "Quem é Gustavo Bellanda?"}]},
        version="v1",
        config={"configurable": {"thread_id": "1"}},
    ):
        if event.get("event") == "on_chat_model_stream":
            print(event["data"]["chunk"].content, end="", flush=True)


asyncio.run(main())
