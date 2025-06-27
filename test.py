from concurrent.futures import ThreadPoolExecutor

from llms.groq import GroqLLMs, call_groq_llm

with open("docs/extract_for_rag_prompt.md", "r") as file:
    prompt = file.read()


def process_image(i):
    result = call_groq_llm(
        GroqLLMs.llama_4_maverick_17b_128e_instruct,
        prompt,
        images=[""],
    )

    with open(f"docs/extract_for_rag_result_{i}.md", "w") as file:
        file.write(result)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(process_image, range(1))
