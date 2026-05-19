from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings


@dataclass
class WorldTimeInfo:
    timezone: Optional[str]
    datetime: Optional[str]
    utc_offset: Optional[str]


@dataclass
class WeatherInfo:
    temperature_c: Optional[float]
    apparent_temperature_c: Optional[float]
    weather_label: Optional[str]


TIMEZONE_MAP = {
    "japan": "Asia/Tokyo",
    "usa": "America/New_York",
    "united states": "America/New_York",
    "uk": "Europe/London",
    "united kingdom": "Europe/London",
    "india": "Asia/Kolkata",
    "germany": "Europe/Berlin",
    "france": "Europe/Paris",
    "canada": "America/Toronto",
    "brazil": "America/Sao_Paulo",
    "australia": "Australia/Sydney",
}

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate showers",
    82: "Violent showers",
    95: "Thunderstorm",
}


class ExternalDataService:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(12.0)

    def get_world_time(self, country: str) -> WorldTimeInfo:
        timezone = TIMEZONE_MAP.get((country or "").strip().lower())
        if timezone:
            return self._fetch_world_time(timezone)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{settings.worldtime_base_url}/ip")
                resp.raise_for_status()
                data = resp.json()
            return WorldTimeInfo(
                timezone=data.get("timezone"),
                datetime=data.get("datetime"),
                utc_offset=data.get("utc_offset"),
            )
        except Exception:
            return WorldTimeInfo(timezone=None, datetime=None, utc_offset=None)

    def _fetch_world_time(self, timezone: str) -> WorldTimeInfo:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{settings.worldtime_base_url}/timezone/{timezone}")
                resp.raise_for_status()
                data = resp.json()
            return WorldTimeInfo(
                timezone=data.get("timezone"),
                datetime=data.get("datetime"),
                utc_offset=data.get("utc_offset"),
            )
        except Exception:
            return WorldTimeInfo(timezone=timezone, datetime=None, utc_offset=None)

    def get_weather(self, country: str) -> WeatherInfo:
        query = (country or "").strip()
        if not query:
            return WeatherInfo(temperature_c=None, apparent_temperature_c=None, weather_label=None)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                geo = client.get(
                    f"{settings.weather_geocode_base_url}/search",
                    params={"name": query, "count": 1, "language": "en", "format": "json"},
                )
                geo.raise_for_status()
                geo_data = geo.json()
                results = geo_data.get("results") or []
                if not results:
                    return WeatherInfo(temperature_c=None, apparent_temperature_c=None, weather_label=None)
                top = results[0]
                lat = top.get("latitude")
                lon = top.get("longitude")
                if lat is None or lon is None:
                    return WeatherInfo(temperature_c=None, apparent_temperature_c=None, weather_label=None)

                weather = client.get(
                    f"{settings.weather_base_url}/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "temperature_2m,apparent_temperature,weather_code",
                        "timezone": "auto",
                    },
                )
                weather.raise_for_status()
                weather_data = weather.json()
                current = weather_data.get("current") or {}
                code = current.get("weather_code")
                label = WEATHER_CODES.get(code, "Unknown") if code is not None else None
                return WeatherInfo(
                    temperature_c=current.get("temperature_2m"),
                    apparent_temperature_c=current.get("apparent_temperature"),
                    weather_label=label,
                )
        except Exception:
            return WeatherInfo(temperature_c=None, apparent_temperature_c=None, weather_label=None)
