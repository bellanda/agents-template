import base64
import pathlib
import sys
from io import BytesIO

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent))

from llms.google import generate_image_imagen3


def generate_image(prompt: str, number_of_images: int) -> dict:
    """Generates an image based on the provided text prompt using Google's Imagen 3.

    Args:
        prompt (str): The text description of the image to generate (e.g., "A sunset over mountains", "A cat wearing a hat").
        number_of_images (int): Number of images to generate (1-4).

    Returns:
        dict: A dictionary containing the generated image information.
    """
    print("🎨 [TOOL] generate_image INICIANDO")
    print(f"🎨 [TOOL] Prompt recebido: '{prompt}'")
    print(f"🎨 [TOOL] Número de imagens: {number_of_images}")

    try:
        # Limit number of images to prevent abuse
        if number_of_images > 4:
            print(f"🎨 [TOOL] Limitando número de imagens de {number_of_images} para 4")
            number_of_images = 4
        elif number_of_images < 1:
            print(f"🎨 [TOOL] Ajustando número de imagens de {number_of_images} para 1")
            number_of_images = 1

        print("🎨 [TOOL] Chamando generate_image_imagen3...")
        # Generate image using Google's Imagen 3
        image = generate_image_imagen3(prompt, number_of_images)
        print(f"🎨 [TOOL] Imagem gerada com sucesso! Tipo: {type(image)}")

        print("🎨 [TOOL] Convertendo imagem para base64...")
        # Convert PIL Image to base64 for easy transmission
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        print(f"🎨 [TOOL] Base64 gerado! Tamanho: {len(image_base64)} caracteres")

        result = {
            "status": "success",
            "message": f"Successfully generated image for prompt: '{prompt}'",
            "image_data": f"data:image/png;base64,{image_base64}",
            "prompt": prompt,
            "number_of_images": number_of_images,
        }

        print(f"🎨 [TOOL] Resultado preparado! Status: {result['status']}")
        print(f"🎨 [TOOL] Message: {result['message']}")
        print("🎨 [TOOL] RETORNANDO resultado para o agente...")

        return result

    except Exception as e:
        print(f"❌ [TOOL] ERRO na geração de imagem: {e}")
        print(f"❌ [TOOL] Tipo do erro: {type(e)}")
        import traceback

        print("❌ [TOOL] Traceback completo:")
        traceback.print_exc()

        error_result = {"status": "error", "error_message": f"Failed to generate image: {str(e)}", "prompt": prompt}
        print(f"❌ [TOOL] RETORNANDO erro: {error_result}")
        return error_result
