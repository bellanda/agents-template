from openai import AzureOpenAI, OpenAI

from constants import api_keys

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


def call_azure_llm(
    model: str,
    prompt: str,
    temperature: float = 1.00,
    top_p: float = 0.01,
    reasoning_effort: str = "medium",
) -> str:
    """
    Call Azure OpenAI API using the correct chat completions endpoint.
    Supports both OpenAI models and DeepSeek models with different endpoints.

    Args:
        model: The deployment name in Azure OpenAI or model name for DeepSeek
        prompt: The user prompt/message
        temperature: Controls randomness (0.0 to 2.0)
        top_p: Controls diversity via nucleus sampling
        reasoning_effort: Reasoning effort level for reasoning models ("low", "medium", "high")

    Returns:
        The generated response text (reasoning tokens are included automatically in usage stats)
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
        # Prepare the request parameters
        request_params = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        # Add reasoning_effort parameter for reasoning models (only for OpenAI models)
        if model in REASONING_MODELS and model in OPENAI_MODELS:
            request_params["reasoning_effort"] = reasoning_effort

        # Use the correct chat completions API
        response = client.chat.completions.create(**request_params)

        # Extract the response content
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
