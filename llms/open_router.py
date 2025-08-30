import base64
import time
from typing import Union

from openai import OpenAI

from constants import api_keys

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_keys.OPENROUTER_API_KEY,
)


class OpenRouterLLMs:
    # DeepSeek models
    deepseek_v3_1_free = "deepseek/deepseek-chat-v3.1:free"

    # Meta models
    llama_4_scout_free = "meta-llama/llama-4-scout:free"
    llama_4_maverick_free = "meta-llama/llama-4-maverick:free"
    llama_3_1_8b_free = "meta-llama/llama-3.1-8b:free"
    llama_3_1_70b_free = "meta-llama/llama-3.1-70b:free"


def call_openrouter_llm(model: str, prompt: str, **kwargs) -> Union[str, object]:
    """
    Call OpenRouter LLM API with support for text and images.
    Supports streaming responses and all OpenRouter parameters.

    Args:
        model: The model name to use
        prompt: The text prompt
        **kwargs: Additional parameters supported by OpenRouter API including:
            - temperature: Controls randomness (0.0 to 2.0)
            - max_tokens: Maximum tokens to generate
            - top_p: Controls diversity via nucleus sampling
            - stop: Stop sequences
            - images: Optional list of images (URLs, file paths, or base64 encoded data)
            - stream: Whether to stream the response
            - include_reasoning: Whether to include reasoning
            - reasoning_format: Format for reasoning output
            - reasoning_effort: Reasoning effort level for reasoning models ("low", "medium", "high")
            - frequency_penalty: Frequency penalty (-2.0 to 2.0)
            - presence_penalty: Presence penalty (-2.0 to 2.0)
            - logit_bias: Logit bias for specific tokens
            - user: User identifier for tracking
            - extra_headers: Additional headers (HTTP-Referer, X-Title)
            - extra_body: Additional body parameters

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

    # Prepare the request parameters
    request_params = {"model": model, "messages": [{"role": "user", "content": message_content}], **kwargs}

    # Call LLM
    try:
        response = client.chat.completions.create(**request_params)

        # If streaming, return the response object directly
        if kwargs.get("stream", False):
            return response

        # Measure time
        end_time = time.time()
        print(f"🌐 Time taken to call OpenRouter LLM ({model}): {end_time - start_time} seconds")

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error calling OpenRouter LLM: {e}")
        raise e
