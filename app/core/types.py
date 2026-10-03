"""
Typy kolumn niezależne od silnika bazy danych.

Specyfikacja (sekcja 3.8) zakłada natywne typy PostgreSQL: UUID,
TEXT[] oraz ENUM. Żeby ten sam kod modeli dało się uruchomić lokalnie
na SQLite (szybki development, testy) i docelowo na PostgreSQL
(produkcja, zgodnie z dokumentem), poniższe typy renderują się inaczej
w zależności od dialektu połączenia.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CHAR, JSON, DateTime, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class GUID(TypeDecorator):
    """UUID natywny na PostgreSQL, CHAR(36) na innych silnikach (np. SQLite)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class AwareDateTime(TypeDecorator):
    """
    DateTime zawsze "aware" (z tzinfo=UTC) po odczycie z bazy, niezależnie
    od silnika. PostgreSQL (TIMESTAMPTZ) zwraca już aware datetimes, ale
    SQLite nie przechowuje tzinfo wcale - zwraca naive datetimes, co psuje
    porównania w rodzaju `expires_at < datetime.now(timezone.utc)`
    (TypeError: can't compare offset-naive and offset-aware datetimes).
    Ten typ naprawia to w jednym miejscu zamiast przy każdym porównaniu.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class StringArray(TypeDecorator):
    """PostgreSQL TEXT[] natywnie, lista JSON na innych silnikach (np. SQLite)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy import Text

            return dialect.type_descriptor(PG_ARRAY(Text()))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return []
        return list(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return list(value)
