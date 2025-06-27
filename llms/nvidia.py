import base64
import time
from typing import List, Optional, Union

from openai import OpenAI

from constants import api_keys

client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_keys.NVIDIA_API_KEY)


class NvidiaLLMs:
    # DeepSeek
    deepseek_r1_0528 = "deepseek-ai/deepseek-r1-0528"
    # Nemotron
    llama_3_1_nemotron_nano_vl_8b_v1 = "nvidia/llama-3.1-nemotron-nano-vl-8b-v1"
    llama_3_1_nemotron_ultra_253b_v1 = "nvidia/llama-3.1-nemotron-ultra-253b-v1"
    # Meta
    llama_4_maverick_17b_128e_instruct = "meta/llama-4-maverick-17b-128e-instruct"
    llama_4_scout_17b_16e_instruct = "meta/llama-4-scout-17b-16e-instruct"
    # Alibaba Qwen
    qwen_3_235b_a22b = "qwen/qwen3-235b-a22b"


def call_nvidia_llm(
    model: str,
    prompt: str,
    temperature: float = 1.00,
    top_p: float = 0.01,
    max_tokens: int = 1024,
    images: Optional[List[Union[str, bytes]]] = None,
) -> str:
    """
    Call NVIDIA LLM API with support for text and images.

    Args:
        model: The model name to use
        prompt: The text prompt
        temperature: Controls randomness
        top_p: Controls diversity via nucleus sampling
        max_tokens: Maximum tokens to generate
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
    print("CHEGUEI AQUI")
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message_content}],
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
