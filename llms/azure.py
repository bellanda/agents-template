import base64
from typing import Union

from openai import AzureOpenAI, OpenAI

from constants import api_keys


class AzureLLMs:
    o4_mini = "o4-mini"
    gpt_4_1 = "gpt-4.1"
    gpt_4_1_mini = "gpt-4.1-mini"
    gpt_4_1_nano = "gpt-4.1-nano"
    deepseek_v3_0324 = "DeepSeek-V3-0324"
    deepseek_r1_0528 = "DeepSeek-R1-0528"


AZURE_MODELS_VERSIONS = {
    "o4-mini": "2025-01-01-preview",
    "gpt-4.1": "2025-01-01-preview",
    "gpt-4.1-mini": "2025-01-01-preview",
    "gpt-4.1-nano": "2025-01-01-preview",
    "DeepSeek-V3-0324": "2024-05-01-preview",
    "DeepSeek-R1-0528": "2024-05-01-preview",
}

OPENAI_MODELS = ["o4-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]
REASONING_MODELS = ["o4-mini", "o3", "o3-mini", "o1", "o1-mini"]  # Models that support reasoning
OPENAI_URI = "https://ai-foundry-hpe-resource.openai.azure.com"
DEEPSEEK_URI = "https://ai-foundry-hpe-resource.services.ai.azure.com/models"


def call_azure_llm(model: str, prompt: str, **kwargs) -> Union[str, object]:
    """
    Call Azure OpenAI API using the correct chat completions endpoint.
    Supports both OpenAI models and DeepSeek models with different endpoints.
    Supports multimodal inputs with images and streaming.

    Args:
        model: The deployment name in Azure OpenAI or model name for DeepSeek
        prompt: The user prompt/message
        **kwargs: Additional parameters supported by Azure API including:
            - temperature: Controls randomness (0.0 to 2.0)
            - top_p: Controls diversity via nucleus sampling
            - reasoning_effort: Reasoning effort level for reasoning models ("low", "medium", "high")
            - images: Optional list of images (URLs, file paths, or base64 encoded data)
            - stream: Whether to stream the response
            - max_tokens: Maximum tokens to generate
            - frequency_penalty: Frequency penalty (-2.0 to 2.0)
            - presence_penalty: Presence penalty (-2.0 to 2.0)
            - logit_bias: Logit bias for specific tokens
            - user: User identifier for tracking
            - response_format: Response format configuration
            - seed: Seed for deterministic sampling

    Returns:
        The generated response text or streaming response object
    """
    # Is it a DeepSeek model? (or another company model)
    if model not in OPENAI_MODELS:
        # For DeepSeek models, use the services endpoint
        client = OpenAI(
            api_key=api_keys.AZURE_API_KEY,
            base_url=DEEPSEEK_URI,
            default_query={
                "api-version": AZURE_MODELS_VERSIONS.get(model, "2024-05-01-preview"),
            },
        )
    else:
        # For OpenAI models, use the standard Azure OpenAI client
        client = AzureOpenAI(
            api_key=api_keys.AZURE_API_KEY,
            api_version=AZURE_MODELS_VERSIONS.get(model, "2025-01-01-preview"),
            azure_endpoint=OPENAI_URI,
        )

    try:
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

        # Add reasoning_effort parameter for reasoning models (only for OpenAI models)
        if model in REASONING_MODELS and model in OPENAI_MODELS:
            if "reasoning_effort" not in request_params:
                request_params["reasoning_effort"] = "medium"

        # Use the correct chat completions API
        print(request_params)
        response = client.chat.completions.create(**request_params)

        # If streaming, return the response object directly
        if request_params.get("stream", False):
            return response

        # Extract the response content for non-streaming
        content = response.choices[0].message.content

        # For reasoning models, the reasoning tokens are automatically included in usage stats
        # but not visible in the response content (this is expected behavior)
        if hasattr(response, "usage") and hasattr(response.usage, "completion_tokens_details"):
            details = response.usage.completion_tokens_details
            if hasattr(details, "reasoning_tokens") and details.reasoning_tokens > 0:
                print(f"Reasoning tokens used: {details.reasoning_tokens}")

        return content

    except Exception as e:
        print(f"Error calling Azure API for model {model}: {e}")
        raise e
