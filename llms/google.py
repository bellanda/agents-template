import base64
from typing import Union

from google import genai

from constants import api_keys

client = genai.Client(api_key=api_keys.GOOGLE_API_KEY)


class GoogleLLMs:
    gemini_2_5_pro = "gemini-2.5-pro"
    gemini_2_5_flash = "gemini-2.5-flash"
    gemini_2_5_flash_lite = "gemini-2.5-flash-lite-preview-06-17"


def call_google_llm(model: str, prompt: str, **kwargs) -> Union[str, object]:
    """
    Call Google Gemini API with support for text and images.
    Supports streaming responses and all Google parameters.

    Args:
        model: The model name to use
        prompt: The text prompt
        **kwargs: Additional parameters supported by Google API including:
            - temperature: Controls randomness (0.0 to 2.0)
            - top_p: Controls diversity via nucleus sampling
            - max_output_tokens: Maximum tokens to generate
            - images: Optional list of images (URLs, file paths, or base64 encoded data)
            - stream: Whether to stream the response
            - top_k: Top-k sampling parameter
            - candidate_count: Number of response candidates
            - stop_sequences: Stop sequences
            - safety_settings: Safety settings configuration

    Returns:
        The generated response text or streaming response object
    """
    # Prepare content
    content_parts = [prompt]

    # Extract images from kwargs if provided
    images = kwargs.pop("images", None)
    if images:
        for image in images:
            if isinstance(image, str):
                if image.startswith("http"):
                    # URL image
                    content_parts.append({"mime_type": "image/jpeg", "data": image})
                elif image.startswith("data:image"):
                    # Base64 data URL
                    content_parts.append({"mime_type": "image/jpeg", "data": image})
                else:
                    # File path
                    try:
                        with open(image, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode()
                        content_parts.append({"mime_type": "image/jpeg", "data": image_data})
                    except Exception as e:
                        print(f"Error reading image file {image}: {e}")
            elif isinstance(image, bytes):
                # Raw bytes
                image_data = base64.b64encode(image).decode()
                content_parts.append({"mime_type": "image/jpeg", "data": image_data})

    # Prepare config from kwargs
    config = {}
    if "temperature" in kwargs:
        config["temperature"] = kwargs.pop("temperature")
    if "top_p" in kwargs:
        config["top_p"] = kwargs.pop("top_p")
    if "max_output_tokens" in kwargs:
        config["max_output_tokens"] = kwargs.pop("max_output_tokens")

    # Add any remaining config parameters
    if kwargs:
        config.update(kwargs)

    response = client.models.generate_content(
        model=model,
        contents=content_parts,
        config=config,
    )

    # If streaming, return the response object directly
    if config.get("stream", False):
        return response

    return response.text
