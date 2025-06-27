import base64
from typing import List, Optional, Union

from google import genai

from constants import api_keys

client = genai.Client(api_key=api_keys.GOOGLE_API_KEY)


class GoogleLLMs:
    gemini_2_5_pro = "gemini-2.5-pro"
    gemini_2_5_flash = "gemini-2.5-flash"
    gemini_2_5_flash_lite = "gemini-2.5-flash-lite-preview-06-17"


def call_google_llm(
    model: str,
    prompt: str,
    temperature: float = 1.00,
    top_p: float = 0.01,
    max_tokens: int = 1024,
    images: Optional[List[Union[str, bytes]]] = None,
) -> str:
    """
    Call Google Gemini API with support for text and images.

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
    # Prepare content
    content_parts = [prompt]

    # Add images if provided
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

    response = client.models.generate_content(
        model=model,
        contents=content_parts,
        config={
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_tokens,
        },
    )
    return response.text
