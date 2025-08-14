from llms.fireworks import FireworksLLMs, call_fireworks_llm

with open("./temp.txt", "r", encoding="utf-8") as file:
    prompt = file.read()

# Call LLM with streaming
result = call_fireworks_llm(FireworksLLMs.qwen3_coder_480b_a35b_instruct, prompt, max_tokens=8000, stream=True)

# Collect complete content from stream
complete_content = ""
for chunk in result:
    if chunk.choices[0].delta.content is not None:
        content = chunk.choices[0].delta.content
        complete_content += content
        print(content, end="", flush=True)  # Print in real-time

# Save complete content to file
with open("result.txt", "w", encoding="utf-8") as file:
    file.write(complete_content)

print(f"\n\n✅ Conteúdo completo salvo em 'result.txt' ({len(complete_content)} caracteres)")
