from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, Optional, Union

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, sessionmaker

from app.models.schemas import HistoryItem, LifeSimResponse

Base = declarative_base()


class SimulationHistory(Base):
    __tablename__ = "simulation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sim_slug: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class HistoryStore:
    def __init__(self, database_url: str) -> None:
        self.enabled = False
        self.init_error: Optional[str] = None
        self._session_factory: Optional[sessionmaker[Session]] = None

        try:
            normalized_url = self._normalize_db_url(database_url)
            engine = create_engine(normalized_url, future=True, pool_pre_ping=True)
            Base.metadata.create_all(engine)
            self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            self.enabled = True
            self.init_error = None
        except Exception as exc:
            self.enabled = False
            self.init_error = str(exc)

    def save(self, title: str, response: LifeSimResponse) -> tuple[bool, Optional[str], Optional[str]]:
        if not self.enabled or self._session_factory is None:
            return False, self.init_error or "History store is disabled.", None

        slug = self.slugify(title)
        payload = json.dumps(response.model_dump(mode="json"))

        try:
            with self._session_factory() as session:
                row = SimulationHistory(sim_slug=slug, title=title, payload_json=payload)
                session.add(row)
                session.commit()
            return True, None, slug
        except Exception as exc:
            return False, str(exc), None

    def list_recent(self, limit: int = 20) -> list[HistoryItem]:
        if not self.enabled or self._session_factory is None:
            return []

        with self._session_factory() as session:
            stmt = select(SimulationHistory).order_by(SimulationHistory.created_at.desc()).limit(limit)
            rows = session.execute(stmt).scalars().all()

        return [
            HistoryItem(
                title=row.title,
                slug=row.sim_slug,
                url=f"/{row.sim_slug}",
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ]

    def get_latest(self, slug: str) -> Optional[LifeSimResponse]:
        if not self.enabled or self._session_factory is None:
            return None

        with self._session_factory() as session:
            stmt = (
                select(SimulationHistory)
                .where(SimulationHistory.sim_slug == slug)
                .order_by(SimulationHistory.created_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()

        if row is None:
            return None

        data = json.loads(row.payload_json)
        return LifeSimResponse.model_validate(data)

    def status(self) -> Dict[str, Union[Optional[str], bool]]:
        return {
            "enabled": self.enabled,
            "error": self.init_error,
        }

    @staticmethod
    def slugify(title: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", (title or "").strip().lower())
        compact = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
        timestamp = datetime.utcnow().strftime("%y%m%d%H%M%S")
        base = compact or "timeline"
        return f"{base}-{timestamp}"

    @staticmethod
    def _normalize_db_url(url: str) -> str:
        value = (url or "").strip().strip('"').strip("'")
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://") and "+" not in value.split("://", 1)[0]:
            return "postgresql+psycopg2://" + value[len("postgresql://") :]
        return value
