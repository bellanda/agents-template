import base64
import time
from typing import Union

from openai import OpenAI

from environment import api_keys

# Initialize OpenAI client with Fireworks AI endpoint
client = OpenAI(
    api_key=api_keys.FIREWORKS_API_KEY,
    base_url="https://api.fireworks.ai/inference/v1",
)


class FireworksLLMs:
    # Qwen models
    qwen3_235b_a22b_instruct_2507 = "accounts/fireworks/models/qwen3-235b-a22b-instruct-2507"
    qwen3_235b_a22b_thinking_2507 = "accounts/fireworks/models/qwen3-235b-a22b-thinking-2507"
    qwen3_coder_480b_a35b_instruct = "accounts/fireworks/models/qwen3-coder-480b-a35b-instruct"

    # DeepSeek models
    deepseek_v3_0324 = "accounts/fireworks/models/deepseek-v3-0324"
    deepseek_r1_0528 = "accounts/fireworks/models/deepseek-r1-0528"

    # MoonshotAI Kimi K2
    kimi_k2_instruct = "accounts/fireworks/models/kimi-k2-instruct"


def call_fireworks_llm(model: str, prompt: str, **kwargs) -> Union[str, object]:
    """
    Call Fireworks AI LLM API with support for text and images using OpenAI client.
    Supports streaming responses and all Fireworks parameters.

    Args:
        model: The model name to use
        prompt: The text prompt
        **kwargs: Additional parameters supported by Fireworks API including:
            - temperature: Controls randomness (0.0 to 2.0)
            - max_tokens: Maximum tokens to generate
            - top_p: Controls diversity via nucleus sampling
            - stop: Stop sequences
            - images: Optional list of images (URLs, file paths, or base64 encoded data)
            - stream: Whether to stream the response
            - frequency_penalty: Frequency penalty (-2.0 to 2.0)
            - presence_penalty: Presence penalty (-2.0 to 2.0)
            - logit_bias: Logit bias for specific tokens
            - user: User identifier for tracking
            - response_format: Response format configuration
            - seed: Seed for deterministic sampling

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

    # Call LLM using OpenAI client with Fireworks endpoint
    try:
        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": message_content}], **kwargs
        )

        # If streaming, return the response object directly
        if kwargs.get("stream", False):
            return response

        # Measure time
        end_time = time.time()
        print(f"🎆 Time taken to call Fireworks LLM ({model}): {end_time - start_time} seconds")

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error calling Fireworks LLM: {e}")
        return f"Error: {str(e)}"
