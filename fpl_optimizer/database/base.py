"""Database engine and session lifecycle."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all ORM entities."""


class Database:
    """Own the SQLAlchemy engine and transactional session factory."""

    def __init__(self, url: str) -> None:
        self._ensure_sqlite_parent(url)
        self.engine = create_engine(url, future=True)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _ensure_sqlite_parent(url: str) -> None:
        prefix = "sqlite:///"
        if not url.startswith(prefix) or url == "sqlite:///:memory:":
            return
        Path(url[len(prefix) :]).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    def create_schema(self) -> None:
        """Create tables for a fresh local installation."""

        from fpl_optimizer.database import models  # noqa: F401

        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session and atomically commit or roll it back."""

        session = self._sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def dispose_engine(engine: Engine) -> None:
    """Dispose an engine; exposed for tests and process shutdown hooks."""

    engine.dispose()
