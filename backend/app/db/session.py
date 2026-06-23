from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global engine
    if engine is None:
        engine = create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True, future=True)
    return engine


def get_session_factory() -> sessionmaker[Session]:
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as db:
        yield db
