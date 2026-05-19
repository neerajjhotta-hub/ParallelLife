from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class LifeSimProfile(BaseModel):
    age: int = Field(ge=0, le=120)
    country: str
    habits: str
    career: str
    salary: Optional[float] = None
    hobbies: str


class YearValue(BaseModel):
    year: int
    value: float


class Timeline(BaseModel):
    title: str
    premise: str
    milestones: List[str]
    income_projection: List[YearValue]
    lifestyle_projection: List[YearValue]
    regret_probability_pct: float


class LifeSimulation(BaseModel):
    summary: str
    timelines: List[Timeline]
    future_snapshots: List[str]
    income_projection_summary: str
    lifestyle_projection_summary: str
    regret_probability_pct: float
    sources: List[str]
    assumptions: List[str]


class LifeSimRequest(BaseModel):
    age: int
    country: str
    habits: str
    career: str
    salary: Optional[float] = None
    hobbies: str


class LifeSimResponse(BaseModel):
    profile: LifeSimProfile
    simulation: LifeSimulation
    share_url: Optional[str] = None
    history_saved: bool = False
    history_error: Optional[str] = None


class HistoryItem(BaseModel):
    title: str
    slug: str
    url: str
    created_at: str
