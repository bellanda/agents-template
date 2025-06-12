from io import BytesIO

from google import genai
from google.genai import types
from PIL import Image

from constants import api_keys

client = genai.Client(api_key=api_keys.GOOGLE_API_KEY)


def call_google_llm(
    model: str,
    prompt: str,
    temperature: float = 1.00,
    top_p: float = 0.01,
    max_tokens: int = 1024,
) -> str:
    response = client.models.generate_content(model=model, contents=[prompt])
    return response.text


def generate_image_imagen3(prompt: str, number_of_images: int) -> Image.Image:
    print("🖼️ [IMAGEN3] Iniciando geração de imagem...")
    print(f"🖼️ [IMAGEN3] Prompt: '{prompt}'")
    print(f"🖼️ [IMAGEN3] Número de imagens: {number_of_images}")

    try:
        print("🖼️ [IMAGEN3] Criando cliente Google GenAI...")
        client = genai.Client(api_key=api_keys.GOOGLE_API_KEY)
        print("🖼️ [IMAGEN3] Cliente criado com sucesso!")

        print("🖼️ [IMAGEN3] Configurando geração de imagem...")
        config = types.GenerateImagesConfig(number_of_images=number_of_images)
        print(f"🖼️ [IMAGEN3] Config criada: {config}")

        print("🖼️ [IMAGEN3] Chamando API do Google para gerar imagem...")
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=config,
        )
        print(f"🖼️ [IMAGEN3] Resposta recebida! Tipo: {type(response)}")
        print(
            f"🖼️ [IMAGEN3] Número de imagens geradas: {len(response.generated_images) if hasattr(response, 'generated_images') else 'N/A'}"
        )

        print("🖼️ [IMAGEN3] Processando imagens geradas...")
        for i, generated_image in enumerate(response.generated_images):
            print(f"🖼️ [IMAGEN3] Processando imagem {i + 1}...")
            print(f"🖼️ [IMAGEN3] Tipo da imagem: {type(generated_image)}")
            print(
                f"🖼️ [IMAGEN3] Tamanho dos bytes: {len(generated_image.image.image_bytes) if hasattr(generated_image, 'image') else 'N/A'}"
            )

            image = Image.open(BytesIO(generated_image.image.image_bytes))
            print(f"🖼️ [IMAGEN3] PIL Image criada! Tamanho: {image.size}")
            print(f"🖼️ [IMAGEN3] Modo da imagem: {image.mode}")

        print("🖼️ [IMAGEN3] SUCESSO! Retornando imagem...")
        return image

    except Exception as e:
        print(f"❌ [IMAGEN3] ERRO na API do Google: {e}")
        print(f"❌ [IMAGEN3] Tipo do erro: {type(e)}")
        import traceback

        print("❌ [IMAGEN3] Traceback completo:")
        traceback.print_exc()
        raise e
