import time

from groq import Groq

from constants import api_keys

client = Groq(api_key=api_keys.GROQ_API_KEY)


def call_groq_llm(
    model: str,
    prompt: str,
    temperature: float = 1,
    max_tokens: int = 1024,
    top_p: float = 1,
    stop: str = None,
) -> str:
    # Measure time
    start_time = time.time()

    # Call LLM
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_completion_tokens=max_tokens,
        top_p=top_p,
        stream=False,
        stop=stop,
    )

    # Measure time
    end_time = time.time()
    print(f"⚡ Time taken to call GROQ LLM ({model}): {end_time - start_time} seconds")

    return completion.choices[0].message.content
