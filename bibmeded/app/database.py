from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal = None
_ReadOnlySessionLocal = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        from app.config import settings
        url = settings.database_url
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session_factory():
    get_engine()  # ensure engine and session factory are initialised
    return _SessionLocal


def get_read_only_session_factory():
    global _ReadOnlySessionLocal
    if _ReadOnlySessionLocal is None:
        from app.config import settings
        from app.read_only import create_read_only_engine

        _ReadOnlySessionLocal = sessionmaker(bind=create_read_only_engine(settings.database_url))
    return _ReadOnlySessionLocal


def get_read_only_engine() -> Engine:
    return get_read_only_session_factory().kw["bind"]


# Module-level alias used by legacy code that does `from app.database import engine`
# This is a property-like approach: access triggers lazy init.
# For simple compatibility we expose a callable.
def get_db() -> Generator[Session, None, None]:
    from app.config import settings
    from app.read_only import guard_session

    if settings.read_only:
        db = guard_session(get_read_only_session_factory()())
    else:
        db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


# Provide a module-level `engine` attribute that lazily initialises.
# Many places do `from app.database import engine` so we need this to work.
# We use a module __getattr__ to handle lazy access.
def __getattr__(name: str):
    if name == "engine":
        return get_engine()
    if name == "SessionLocal":
        return get_session_factory()
    raise AttributeError(f"module 'app.database' has no attribute {name!r}")
