from __future__ import annotations

import json
from typing import Optional

import httpx

from app.config import settings
from app.models.schemas import LifeSimProfile, LifeSimResponse, LifeSimulation, Timeline, YearValue
from app.services.external_data import WeatherInfo, WorldTimeInfo


class GeminiLifeService:
    def __init__(self) -> None:
        self.timeout = httpx.Timeout(45.0)

    def generate_simulation(
        self,
        profile: LifeSimProfile,
        world_time: WorldTimeInfo,
        weather: WeatherInfo,
    ) -> LifeSimResponse:
        if not self._is_configured_value(settings.gemini_api_key):
            return self._fallback_response(profile, "GEMINI_API_KEY is not configured.")

        endpoint = self._build_endpoint()

        prompt = self._build_prompt(profile=profile, world_time=world_time, weather=weather)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": self._build_generation_config(temperature=0.4, max_tokens=2600),
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=body)
                resp.raise_for_status()

            data = resp.json()
            text = self._extract_text(data)
            parsed = self._extract_json_object(text)
            if parsed is None:
                parsed = self._normalize_to_json(raw_text=text, endpoint=endpoint)
            sanitized = self._sanitize_simulation_json(parsed)
            sanitized = self._finalize_non_empty(profile=profile, simulation=sanitized)
            simulation = LifeSimulation.model_validate(sanitized)
            return LifeSimResponse(profile=profile, simulation=simulation)
        except Exception as exc:  # noqa: BLE001
            return self._fallback_response(profile, f"Gemini response could not be parsed ({exc}).")

    def _build_prompt(self, profile: LifeSimProfile, world_time: WorldTimeInfo, weather: WeatherInfo) -> str:
        time_line = world_time.datetime or "unknown"
        tz_line = world_time.timezone or "unknown"
        weather_line = (
            f"{weather.temperature_c}C, feels {weather.apparent_temperature_c}C, {weather.weather_label}"
            if weather.temperature_c is not None
            else "unknown"
        )

        return f"""
You are ParallelLife. Generate alternate life timelines for a user profile. Return ONLY a JSON object.

User profile:
- age: {profile.age}
- country: {profile.country}
- habits: {profile.habits}
- career: {profile.career}
- salary: {profile.salary if profile.salary is not None else "unknown"}
- hobbies: {profile.hobbies}

Context signals:
- local_time: {time_line}
- timezone: {tz_line}
- current_weather: {weather_line}

Output requirements:
1) Provide 3-4 distinct timelines with realistic milestones.
2) Tie timelines to the user's habits, hobbies, and career pivot options.
3) Keep income projections in annual currency values for each year.
4) Provide a lifestyle score 0-100 per year in each timeline.
5) Regret probability is a percent 0-100 (higher means more regret).
6) Make outputs shareable and concise, avoid sensitive or harmful content.

Output format rules:
- Output ONLY valid JSON (no markdown, no prose outside JSON).
- Use this exact schema and keys.
- All numeric fields must be numbers, never null, never strings with units.

JSON schema:
{{
  "summary": string,
  "timelines": [
    {{
      "title": string,
      "premise": string,
      "milestones": [string],
      "income_projection": [{{"year": number, "value": number}}],
      "lifestyle_projection": [{{"year": number, "value": number}}],
      "regret_probability_pct": number
    }}
  ],
  "future_snapshots": [string],
  "income_projection_summary": string,
  "lifestyle_projection_summary": string,
  "regret_probability_pct": number,
  "sources": [string],
  "assumptions": [string]
}}
""".strip()

    def _extract_text(self, payload: dict) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            raise ValueError("No candidates in Gemini response")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "\n".join(str(part.get("text", "")).strip() for part in parts if part.get("text"))
        if not text.strip():
            raise ValueError("Gemini returned empty text")
        return text

    def _extract_json_object(self, raw_text: str) -> Optional[dict]:
        text = raw_text.strip()
        if not text:
            return None
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            return None

    def _normalize_to_json(self, raw_text: str, endpoint: str) -> dict:
        repair_prompt = (
            "Convert the following content into a valid JSON object matching the exact ParallelLife schema. "
            "Return JSON only, without markdown. Ensure all numeric fields are numbers (not null, not strings).\n\n"
            f"CONTENT:\n{raw_text}"
        )
        repair_body = {
            "contents": [{"parts": [{"text": repair_prompt}]}],
            "generationConfig": self._build_generation_config(temperature=0.1, max_tokens=2200),
        }
        with httpx.Client(timeout=self.timeout) as client:
            repair_resp = client.post(endpoint, json=repair_body)
            repair_resp.raise_for_status()
        repaired_text = self._extract_text(repair_resp.json())
        repaired = self._extract_json_object(repaired_text)
        if repaired is None:
            raise ValueError("No JSON object found")
        return repaired

    def _sanitize_simulation_json(self, raw: dict) -> dict:
        timelines_raw = raw.get("timelines", []) if isinstance(raw.get("timelines"), list) else []
        timelines = [self._sanitize_timeline(item) for item in timelines_raw if isinstance(item, dict)]

        return {
            "summary": str(raw.get("summary") or ""),
            "timelines": timelines,
            "future_snapshots": self._to_str_list(raw.get("future_snapshots")),
            "income_projection_summary": str(raw.get("income_projection_summary") or ""),
            "lifestyle_projection_summary": str(raw.get("lifestyle_projection_summary") or ""),
            "regret_probability_pct": self._to_float(raw.get("regret_probability_pct"), 0.0),
            "sources": self._to_str_list(raw.get("sources")),
            "assumptions": self._to_str_list(raw.get("assumptions")),
        }

    def _sanitize_timeline(self, raw: dict) -> dict:
        income = self._to_year_values(raw.get("income_projection"))
        lifestyle = self._to_year_values(raw.get("lifestyle_projection"))
        return {
            "title": str(raw.get("title") or ""),
            "premise": str(raw.get("premise") or ""),
            "milestones": self._to_str_list(raw.get("milestones")),
            "income_projection": income,
            "lifestyle_projection": lifestyle,
            "regret_probability_pct": self._to_float(raw.get("regret_probability_pct"), 0.0),
        }

    def _to_year_values(self, raw: object) -> list[dict]:
        if not isinstance(raw, list):
            return []
        cleaned: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            year = self._to_int(item.get("year"), 0)
            value = self._to_float(item.get("value"), 0.0)
            if year:
                cleaned.append({"year": year, "value": value})
        return cleaned

    def _to_float(self, value: object, default: float) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "")
            try:
                return float(cleaned)
            except Exception:
                return default
        return default

    def _to_int(self, value: object, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value.strip()))
            except Exception:
                return default
        return default

    def _to_str_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _finalize_non_empty(self, profile: LifeSimProfile, simulation: dict) -> dict:
        if not simulation.get("summary"):
            simulation["summary"] = (
                f"ParallelLife generated alternate futures for a {profile.age}-year-old in {profile.country} "
                f"considering new paths from {profile.career}."
            )

        if not simulation.get("future_snapshots"):
            simulation["future_snapshots"] = [
                "2027: A new routine forms around focused skill-building and a calmer schedule.",
                "2030: Career identity sharpens, with a clearer community and creative outlet.",
                "2034: Financial stability supports a more intentional lifestyle and travel cadence.",
            ]

        if not simulation.get("timelines"):
            base_year = self._base_year()
            simulation["timelines"] = [
                {
                    "title": "Reskill and Remote",
                    "premise": "Pivot into a flexible role while keeping habits steady.",
                    "milestones": [
                        f"{base_year}: Launch a focused learning sprint.",
                        f"{base_year + 1}: Land a remote role with steady growth.",
                        f"{base_year + 3}: Build a reputation in a niche skill area.",
                    ],
                    "income_projection": [
                        {"year": base_year, "value": 52000},
                        {"year": base_year + 2, "value": 70000},
                        {"year": base_year + 4, "value": 86000},
                    ],
                    "lifestyle_projection": [
                        {"year": base_year, "value": 62},
                        {"year": base_year + 2, "value": 71},
                        {"year": base_year + 4, "value": 76},
                    ],
                    "regret_probability_pct": 22.0,
                }
            ]

        if not simulation.get("income_projection_summary"):
            simulation["income_projection_summary"] = "Income rises steadily in most timelines with a mid-term plateau."

        if not simulation.get("lifestyle_projection_summary"):
            simulation["lifestyle_projection_summary"] = "Lifestyle improves as habits stabilize and community grows."

        if not simulation.get("sources"):
            simulation["sources"] = [
                "Gemini synthesis of labor market patterns and scenario modeling.",
            ]

        if not simulation.get("assumptions"):
            simulation["assumptions"] = [
                "Projections assume stable health and consistent skill-building.",
                "Currency values are approximate and depend on market conditions.",
                "Lifestyle scores are directional, not clinical measures.",
            ]

        if not simulation.get("regret_probability_pct"):
            simulation["regret_probability_pct"] = 24.0

        simulation["timelines"] = self._ensure_timeline_depth(simulation["timelines"])
        return simulation

    def _build_generation_config(self, temperature: float, max_tokens: int) -> dict:
        config = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        mime = (settings.gemini_response_mime_type or "").strip()
        if mime:
            config["responseMimeType"] = mime
        return config

    def _build_endpoint(self) -> str:
        endpoint = (settings.gemini_api_endpoint or "").strip()
        if endpoint:
            if "key=" in endpoint:
                return endpoint
            joiner = "&" if "?" in endpoint else "?"
            return f"{endpoint}{joiner}key={settings.gemini_api_key}"
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
            f"?key={settings.gemini_api_key}"
        )

    def _ensure_timeline_depth(self, timelines: list[dict]) -> list[dict]:
        if len(timelines) >= 3:
            return timelines
        base_year = self._base_year()
        seed = timelines[:]
        while len(seed) < 3:
            idx = len(seed) + 1
            seed.append(
                {
                    "title": f"Alternate Arc {idx}",
                    "premise": "A different pivot emphasizes creativity and community.",
                    "milestones": [
                        f"{base_year}: Set a new personal north star.",
                        f"{base_year + 1}: Transition into a more aligned role.",
                        f"{base_year + 3}: Establish a supportive network and rhythm.",
                    ],
                    "income_projection": [
                        {"year": base_year, "value": 48000 + idx * 3000},
                        {"year": base_year + 2, "value": 65000 + idx * 4000},
                        {"year": base_year + 4, "value": 82000 + idx * 5000},
                    ],
                    "lifestyle_projection": [
                        {"year": base_year, "value": 58 + idx * 3},
                        {"year": base_year + 2, "value": 68 + idx * 2},
                        {"year": base_year + 4, "value": 74 + idx * 2},
                    ],
                    "regret_probability_pct": 28.0 - idx * 2,
                }
            )
        return seed

    def _base_year(self) -> int:
        from datetime import datetime

        return datetime.utcnow().year

    def _fallback_response(self, profile: LifeSimProfile, reason: str) -> LifeSimResponse:
        simulation = LifeSimulation(
            summary=f"Unable to generate a full simulation. {reason}",
            timelines=[],
            future_snapshots=["Simulation unavailable."],
            income_projection_summary="",
            lifestyle_projection_summary="",
            regret_probability_pct=0.0,
            sources=[],
            assumptions=["Try again after configuring the Gemini API key."],
        )
        return LifeSimResponse(profile=profile, simulation=simulation)

    def _is_configured_value(self, value: str) -> bool:
        v = (value or "").strip()
        if not v:
            return False
        lower = v.lower()
        return not any(token in lower for token in ("your_", "placeholder", "changeme", "example"))
