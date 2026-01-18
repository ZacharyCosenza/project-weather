import requests
from datetime import datetime
from typing import Dict, Any


def get_current_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch current weather conditions from weather.gov API.

    Args:
        lat: Latitude coordinate
        lon: Longitude coordinate

    Returns:
        Dictionary containing:
            - start_time: datetime object
            - temperature: float (in Fahrenheit)
            - temperature_unit: str
            - forecast_name: str
            - short_forecast: str

    Raises:
        requests.RequestException: If API call fails
        KeyError: If response format is unexpected
        ValueError: If temperature unit is not Fahrenheit
    """
    headers = {
        'User-Agent': '(Weather Platform Dashboard, contact@example.com)'
    }

    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_response = requests.get(points_url, headers=headers, timeout=10)
    points_response.raise_for_status()
    points_data = points_response.json()

    forecast_url = points_data["properties"]["forecast"]
    forecast_response = requests.get(forecast_url, headers=headers, timeout=10)
    forecast_response.raise_for_status()
    forecast_data = forecast_response.json()

    first_period = forecast_data["properties"]["periods"][0]

    start_time_str = first_period["startTime"]
    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

    temperature = float(first_period["temperature"])
    temperature_unit = first_period["temperatureUnit"]

    if temperature_unit != "F":
        if temperature_unit == "C":
            temperature = (temperature * 9/5) + 32
            temperature_unit = "F"
        else:
            raise ValueError(f"Unexpected temperature unit: {temperature_unit}")

    return {
        "start_time": start_time,
        "temperature": temperature,
        "temperature_unit": temperature_unit,
        "forecast_name": first_period.get("name", "Current"),
        "short_forecast": first_period.get("shortForecast", "N/A")
    }
