from typing import Literal

from google.adk.models.lite_llm import LiteLlm

ModelsKeys = Literal["qwen3:4b", "gemini-2.0-flash-lite"]

MODELS_MAPPING: dict[ModelsKeys, LiteLlm | ModelsKeys] = {
    "qwen3:4b": LiteLlm(
        model="ollama_chat/qwen3:4b",
        temperature=0.70,  # respostas determinísticas
        top_p=1.0,  # sem corte de núcleo
        top_k=50,  # considera os 50 tokens mais prováveis
        repetition_penalty=1.2,  # evita repetições
        seed=5,  # semente para reprodutibilidade
    ),
    "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
}
