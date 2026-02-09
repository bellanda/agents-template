from enum import Enum
from typing import Literal

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field


class CityEnum(str, Enum):
    """Cidades disponíveis para consulta do clima."""

    SAO_PAULO = "São Paulo"
    RIO_DE_JANEIRO = "Rio de Janeiro"
    BELO_HORIZONTE = "Belo Horizonte"
    BRASILIA = "Brasília"
    SALVADOR = "Salvador"
    FORTALEZA = "Fortaleza"
    RECIFE = "Recife"
    PORTO_ALEGRE = "Porto Alegre"
    CURITIBA = "Curitiba"
    MANAUS = "Manaus"


class GetWeatherInput(BaseModel):
    """Input para obter informações do clima."""

    city: Literal[
        "São Paulo",
        "Rio de Janeiro",
        "Belo Horizonte",
        "Brasília",
        "Salvador",
        "Fortaleza",
        "Recife",
        "Porto Alegre",
        "Curitiba",
        "Manaus",
    ] = Field(
        description="Cidade para obter o clima. Escolha uma das opções: São Paulo, Rio de Janeiro, Belo Horizonte, Brasília, Salvador, Fortaleza, Recife, Porto Alegre, Curitiba, Manaus"
    )


@tool("get_weather", args_schema=GetWeatherInput, return_direct=False)
def get_weather(city: str) -> str:
    """Obtém informações do clima para uma cidade específica no Brasil.

    Use esta ferramenta quando o usuário perguntar sobre o clima de uma cidade.
    Cidades disponíveis: São Paulo, Rio de Janeiro, Belo Horizonte, Brasília,
    Salvador, Fortaleza, Recife, Porto Alegre, Curitiba, Manaus.

    Args:
        city: Nome da cidade para consultar o clima

    Returns:
        String formatada com informações completas do clima
    """
    # Mapeamento de cidades para coordenadas (lat, lon)
    city_coordinates = {
        "São Paulo": (-23.5505, -46.6333),
        "Rio de Janeiro": (-22.9068, -43.1729),
        "Belo Horizonte": (-19.9167, -43.9345),
        "Brasília": (-15.7939, -47.8828),
        "Salvador": (-12.9714, -38.5014),
        "Fortaleza": (-3.7319, -38.5267),
        "Recife": (-8.0476, -34.8770),
        "Porto Alegre": (-30.0346, -51.2177),
        "Curitiba": (-25.4284, -49.2733),
        "Manaus": (-3.1190, -60.0217),
    }

    if city not in city_coordinates:
        return f"Cidade '{city}' não encontrada. Cidades disponíveis: {', '.join(city_coordinates.keys())}"

    try:
        lat, lon = city_coordinates[city]

        # Usando a API gratuita do Open-Meteo (não requer chave de API)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "America/Sao_Paulo",
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        current = data["current"]

        # Mapeamento básico de códigos de clima
        weather_codes = {
            0: "Céu limpo",
            1: "Principalmente limpo",
            2: "Parcialmente nublado",
            3: "Nublado",
            45: "Neblina",
            48: "Neblina com geada",
            51: "Garoa leve",
            53: "Garoa moderada",
            55: "Garoa intensa",
            61: "Chuva leve",
            63: "Chuva moderada",
            65: "Chuva intensa",
            80: "Pancadas de chuva leves",
            81: "Pancadas de chuva moderadas",
            82: "Pancadas de chuva intensas",
        }

        weather_description = weather_codes.get(current["weather_code"], "Condição desconhecida")

        result = f"""🌤️ Clima em {city}:
📍 Temperatura: {current["temperature_2m"]}°C
💧 Umidade: {current["relative_humidity_2m"]}%
🌬️ Vento: {current["wind_speed_10m"]} km/h
☁️ Condição: {weather_description}
🕐 Atualizado em: {current["time"]}"""

        return result

    except requests.RequestException as e:
        return f"Erro ao obter dados do clima para {city}: {str(e)}"
    except Exception as e:
        return f"Erro inesperado ao consultar clima de {city}: {str(e)}"
