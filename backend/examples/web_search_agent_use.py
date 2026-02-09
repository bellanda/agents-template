import asyncio

from agents.web_search_agent.agent import create_root_agent


async def main():
    root_agent = create_root_agent()
    async for event in root_agent.astream_events(
        {"messages": [{"role": "user", "content": "Quem é Gustavo Bellanda?"}]},
        version="v1",
        config={"configurable": {"thread_id": "1"}},
    ):
        if event.get("event") == "on_chat_model_stream":
            chunk = event["data"]["chunk"]

            # 1. Tentar pegar o raciocínio (pensamento)
            reasoning = chunk.additional_kwargs.get("reasoning_content")
            if reasoning:
                # Imprime o pensamento (pode colocar uma cor diferente ou prefixo)
                print(f"\033[90m{reasoning}\033[0m", end="", flush=True)

            # 2. Pegar o conteúdo final
            if chunk.content:
                print(chunk.content, end="", flush=True)


asyncio.run(main())
