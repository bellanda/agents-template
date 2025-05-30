import pprint
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import ollama

# Verifica os modelos disponíveis
pprint.pprint([model.model for model in ollama.list().models])


def generate_response(model: str, message: str):
    thread_id = threading.current_thread().ident
    start_time = time.perf_counter()
    print(f"Thread {thread_id} - Iniciando requisição...")

    # Chamada básica para gerar uma resposta
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": message}],
    )

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    print(f"Thread {thread_id} - Requisição concluída em {elapsed_time:.2f} segundos")

    return response["message"]["content"]


messages = [
    {
        "model": "qwen3:4b",
        "message": "Explique o que é inteligência artificial da maneira mais completa porém simples possível. /no_think",
    },
] * 1

print("\nIniciando simulação de 10 requisições concorrentes...\n")

with ThreadPoolExecutor(max_workers=10) as executor:
    overall_start = time.perf_counter()
    futures = [executor.submit(generate_response, **item) for item in messages]

    # Aguarda todas as threads terminarem
    for future in futures:
        future.result()  # Não imprimimos o conteúdo

    overall_time = time.perf_counter() - overall_start
    print(f"\nTempo total para todas as requisições: {overall_time:.2f} segundos")
