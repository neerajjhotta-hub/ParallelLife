from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_api_endpoint: str = os.getenv("GEMINI_API_ENDPOINT", "")
    gemini_response_mime_type: str = os.getenv("GEMINI_RESPONSE_MIME_TYPE", "application/json")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./parallel_life.db")
    worldtime_base_url: str = os.getenv("WORLDTIME_BASE_URL", "https://worldtimeapi.org/api")
    weather_geocode_base_url: str = os.getenv("WEATHER_GEOCODE_BASE_URL", "https://geocoding-api.open-meteo.com/v1")
    weather_base_url: str = os.getenv("WEATHER_BASE_URL", "https://api.open-meteo.com/v1")


settings = Settings()
