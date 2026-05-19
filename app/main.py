from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.models.schemas import HistoryItem, LifeSimRequest, LifeSimResponse, LifeSimProfile
from app.services.external_data import ExternalDataService
from app.services.gemini_life import GeminiLifeService
from app.services.history_store import HistoryStore

app = FastAPI(
    title="ParallelLife API",
    description="Backend service for simulating alternate life timelines.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

life_service = GeminiLifeService()
external_data = ExternalDataService()
history_store = HistoryStore(settings.database_url)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "env_loaded": "true" if settings.gemini_api_key else "false",
        "history_enabled": "true" if history_store.enabled else "false",
    }


@app.get("/", response_class=HTMLResponse)
def root(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api")
def api_info() -> dict[str, str]:
    return {
        "message": "ParallelLife API is running.",
        "swagger_ui": "/docs",
        "redoc": "/redoc",
        "openapi_schema": "/openapi.json",
    }


@app.get("/api/history/status")
def history_status() -> dict[str, str | bool | None]:
    return history_store.status()


@app.post("/simulate", response_model=LifeSimResponse)
def simulate_life(request: LifeSimRequest) -> LifeSimResponse:
    profile = LifeSimProfile(
        age=request.age,
        country=request.country,
        habits=request.habits,
        career=request.career,
        salary=request.salary,
        hobbies=request.hobbies,
    )
    world_time = external_data.get_world_time(profile.country)
    weather = external_data.get_weather(profile.country)
    response = life_service.generate_simulation(profile=profile, world_time=world_time, weather=weather)

    title = f"{profile.career} in {profile.country}"
    saved, save_error, slug = history_store.save(title=title, response=response)
    response.share_url = f"/{slug}" if slug else None
    response.history_saved = saved
    response.history_error = save_error
    return response


@app.get("/api/history", response_model=list[HistoryItem])
def get_history() -> list[HistoryItem]:
    return history_store.list_recent(limit=30)


@app.get("/api/history/{sim_slug}", response_model=LifeSimResponse)
def get_history_item(sim_slug: str) -> LifeSimResponse:
    item = history_store.get_latest(sim_slug)
    if item is None:
        raise HTTPException(status_code=404, detail="No saved simulation found for this slug.")
    item.share_url = f"/{sim_slug}"
    item.history_saved = True
    item.history_error = None
    return item


@app.get("/{sim_slug}", response_class=HTMLResponse)
def sim_page(request: Request, sim_slug: str) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})
