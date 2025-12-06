import base64
import time
from typing import Union

from groq import Groq

from environment import api_keys

client = Groq(api_key=api_keys.GROQ_API_KEY)


class GroqLLMs:
    # OpenAI models
    gpt_oss_120b = "openai/gpt-oss-120b"
    gpt_oss_20b = "openai/gpt-oss-20b"
    # Llama 4
    llama_4_maverick_17b_128e_instruct = "meta-llama/llama-4-maverick-17b-128e-instruct"
    llama_4_scout_17b_16e_instruct = "meta-llama/llama-4-scout-17b-16e-instruct"
    llama_4_guard_12b = "meta-llama/llama-guard-4-12b"
    # Llama 3
    llama_3_3_70b_versatile = "llama-3.3-70b-versatile"
    llama_3_1_8b_instant = "llama-3.1-8b-instant"
    # Whisper
    whisper_large_v3 = "whisper-large-v3"
    whisper_large_v3_turbo = "whisper-large-v3-turbo"
    distil_whisper_large_v3_en = "distil-whisper-large-v3-en"


def call_groq_llm(model: str, prompt: str, **kwargs) -> Union[str, object]:
    """
    Call Groq LLM API with support for text and images.
    Supports streaming responses and all Groq parameters.

    Args:
        model: The model name to use
        prompt: The text prompt
        **kwargs: Additional parameters supported by Groq API including:
            - temperature: Controls randomness (0.0 to 2.0)
            - max_completion_tokens: Maximum tokens to generate
            - top_p: Controls diversity via nucleus sampling
            - stop: Stop sequences
            - images: Optional list of images (URLs, file paths, or base64 encoded data)
            - stream: Whether to stream the response
            - frequency_penalty: Frequency penalty (-2.0 to 2.0)
            - presence_penalty: Presence penalty (-2.0 to 2.0)
            - logit_bias: Logit bias for specific tokens
            - user: User identifier for tracking
            - include_reasoning: Whether to include reasoning
            - reasoning_format: Format for reasoning output
            - reasoning_effort: Reasoning effort level for reasoning models ("low", "medium", "high")
            - response_format: Response format configuration
            - seed: Seed for deterministic sampling
            - service_tier: Service tier selection

    Returns:
        The generated response text or streaming response object
    """
    # Measure time
    start_time = time.time()

    # Prepare message content
    message_content = [{"type": "text", "text": prompt}]

    # Extract images from kwargs if provided
    images = kwargs.pop("images", None)
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
        model=model, messages=[{"role": "user", "content": message_content}], **kwargs
    )

    # If streaming, return the response object directly
    if kwargs.get("stream", False):
        return completion

    # Measure time
    end_time = time.time()
    print(f"⚡ Time taken to call GROQ LLM ({model}): {end_time - start_time} seconds")

    return completion.choices[0].message.content
