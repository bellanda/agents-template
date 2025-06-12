from api.utils.tools import generate_error_message, generate_result_message, generate_step_message


def get_weather(city: str) -> str:
    """Get current weather information for a city."""

    start_msg = generate_step_message(1, f"Consultando clima para: {city}")
    print(f"Tool: {start_msg}")

    try:
        # Using a free weather API (OpenWeatherMap requires API key)
        # For demo purposes, returning mock data
        weather_data = {"city": city, "temperature": "22°C", "condition": "Ensolarado", "humidity": "65%", "wind": "10 km/h"}

        success_msg = generate_result_message("success", f"Dados meteorológicos obtidos para {city}")
        print(f"Tool: {success_msg}")

        return f"Clima em {city}: {weather_data['temperature']}, {weather_data['condition']}, Umidade: {weather_data['humidity']}, Vento: {weather_data['wind']}"

    except Exception as e:
        error_msg = generate_error_message(f"Erro ao consultar clima: {str(e)}")
        print(f"Tool: {error_msg}")
        return f"Não foi possível obter informações do clima para {city}. Erro: {str(e)}"
