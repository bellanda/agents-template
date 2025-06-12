import time

from openai import OpenAI

from constants import api_keys

client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_keys.NVIDIA_API_KEY)


def call_nvidia_llm(
    model: str,
    prompt: str,
    temperature: float = 1.00,
    top_p: float = 0.01,
    max_tokens: int = 1024,
) -> str:
    # Measure time
    start_time = time.time()

    # Call LLM
    print("CHEGUEI AQUI")
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        stream=False,
    )
    print("COMPLETED")

    # Measure time
    end_time = time.time()
    print(f"👽 Time taken to call NVIDIA LLM ({model}): {end_time - start_time} seconds")

    return completion.choices[0].message.content
