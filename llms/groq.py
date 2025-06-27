import base64
import time
from typing import List, Optional, Union

from groq import Groq

from constants import api_keys

client = Groq(api_key=api_keys.GROQ_API_KEY)


class GroqLLMs:
    # Llama 4
    llama_4_maverick_17b_128e_instruct = "meta-llama/llama-4-maverick-17b-128e-instruct"
    llama_4_scout_17b_16e_instruct = "meta-llama/llama-4-scout-17b-16e-instruct"
    # Llama 3
    llama_3_3_70b_versatile = "llama-3.3-70b-versatile"
    llama_3_1_8b_instant = "llama-3.1-8b-instant"
    # Whisper
    whisper_large_v3 = "whisper-large-v3"
    whisper_large_v3_turbo = "whisper-large-v3-turbo"
    distil_whisper_large_v3_en = "distil-whisper-large-v3-en"
    # Alibaba Qwen
    qwen_3_32b = "qwen/qwen3-32b"
    qwen_qwq_32b = "qwen/qwen-qwq-32b"


def call_groq_llm(
    model: str,
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    top_p: float = 1,
    stop: str = None,
    images: Optional[List[Union[str, bytes]]] = None,
) -> str:
    """
    Call Groq LLM API with support for text and images.

    Args:
        model: The model name to use
        prompt: The text prompt
        temperature: Controls randomness
        max_tokens: Maximum tokens to generate
        top_p: Controls diversity via nucleus sampling
        stop: Stop sequence
        images: Optional list of images (URLs, file paths, or base64 encoded data)

    Returns:
        The generated response text
    """
    # Measure time
    start_time = time.time()

    # Prepare message content
    message_content = [{"type": "text", "text": prompt}]

    # Add images if provided
    if images:
        for image in images:
            if isinstance(image, str):
                if image.startswith("http"):
                    # URL image
                    message_content.append({"type": "image_url", "image_url": {"url": image}})
                elif image.startswith("data:image"):
                    # Base64 data URL
                    message_content.append({"type": "image_url", "image_url": {"url": image}})
                else:
                    # File path
                    try:
                        with open(image, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode()
                        # Detect image format
                        image_format = "jpeg"
                        if image.lower().endswith(".png"):
                            image_format = "png"
                        elif image.lower().endswith(".gif"):
                            image_format = "gif"
                        elif image.lower().endswith(".webp"):
                            image_format = "webp"

                        data_url = f"data:image/{image_format};base64,{image_data}"
                        message_content.append({"type": "image_url", "image_url": {"url": data_url}})
                    except Exception as e:
                        print(f"Error reading image file {image}: {e}")
            elif isinstance(image, bytes):
                # Raw bytes (assume JPEG)
                image_data = base64.b64encode(image).decode()
                data_url = f"data:image/jpeg;base64,{image_data}"
                message_content.append({"type": "image_url", "image_url": {"url": data_url}})

    # Call LLM
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message_content}],
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
