"""SQLAlchemy engine / session for ProcureIQ."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_db(retries: int = 30, delay: float = 1.0) -> None:
    import time

    last: Exception | None = None
    for _ in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"Database not reachable: {last}")
