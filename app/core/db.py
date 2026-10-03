"""Silnik bazy danych i fabryka sesji SQLAlchemy."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)


class Base(DeclarativeBase):
    """Wspólna klasa bazowa dla wszystkich modeli ORM we wszystkich modułach."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency dostarczająca sesję bazodanową na czas jednego żądania."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
