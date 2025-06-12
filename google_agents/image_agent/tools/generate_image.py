import base64
import io
import traceback

from api.utils.tools import (
    generate_error_message,
    generate_result_message,
    generate_status_message,
    generate_step_message,
    generate_thinking_message,
)
from llms.google import generate_image_imagen3


def generate_image(prompt: str, number_of_images: int = 1) -> str:
    """
    Gera imagens usando o modelo Imagen3 do Google.

    Args:
        prompt: Descrição da imagem a ser gerada
        number_of_images: Número de imagens a gerar (padrão: 1, máximo: 4)

    Returns:
        String JSON com status, mensagem e dados da imagem em base64
    """
    try:
        start_msg = generate_step_message(1, "Iniciando geração de imagem...")
        print(f"🎨 [TOOL] {start_msg}")

        prompt_msg = generate_status_message("processing", f"Prompt recebido: '{prompt}'")
        print(f"🎨 [TOOL] {prompt_msg}")

        count_msg = generate_status_message("processing", f"Número de imagens: {number_of_images}")
        print(f"🎨 [TOOL] {count_msg}")

        # Validar número de imagens
        if number_of_images > 4:
            limit_msg = generate_status_message("warning", f"Limitando número de imagens de {number_of_images} para 4")
            print(f"🎨 [TOOL] {limit_msg}")
            number_of_images = 4
        elif number_of_images < 1:
            adjust_msg = generate_status_message("warning", f"Ajustando número de imagens de {number_of_images} para 1")
            print(f"🎨 [TOOL] {adjust_msg}")
            number_of_images = 1

        thinking_msg = generate_thinking_message("Preparando chamada para o modelo Imagen3...")
        print(f"🎨 [TOOL] {thinking_msg}")

        # Gerar a imagem usando o modelo Imagen3
        image = generate_image_imagen3(prompt, number_of_images)

        success_msg = generate_result_message("success", f"Imagem gerada com sucesso! Tipo: {type(image)}")
        print(f"🎨 [TOOL] {success_msg}")

        convert_msg = generate_step_message(2, "Convertendo imagem para base64...")
        print(f"🎨 [TOOL] {convert_msg}")

        # Converter PIL Image para base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        b64_msg = generate_result_message("success", f"Base64 gerado! Tamanho: {len(image_base64)} caracteres")
        print(f"🎨 [TOOL] {b64_msg}")

        # Preparar resultado
        result = {
            "status": "success",
            "message": "Imagem gerada com sucesso!",
            "data": {"image_base64": image_base64, "format": "PNG", "prompt": prompt, "count": number_of_images},
        }

        final_msg = generate_result_message("success", f"Resultado preparado! Status: {result['status']}")
        print(f"🎨 [TOOL] {final_msg}")
        print(f"🎨 [TOOL] Message: {result['message']}")

        return_msg = generate_step_message(3, "Retornando resultado para o agente...")
        print(f"🎨 [TOOL] {return_msg}")

        return str(result)

    except Exception as e:
        error_msg = generate_error_message(f"Erro na geração de imagem: {e}")
        print(f"❌ [TOOL] {error_msg}")
        print(f"❌ [TOOL] Tipo do erro: {type(e)}")

        # Traceback completo
        print("❌ [TOOL] Traceback completo:")
        traceback.print_exc()

        error_result = {"status": "error", "message": f"Erro ao gerar imagem: {str(e)}", "data": None}

        error_return_msg = generate_error_message(f"Retornando erro: {error_result}")
        print(f"❌ [TOOL] {error_return_msg}")

        return str(error_result)
