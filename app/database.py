"""
DolphinID — Database setup (SQLite + SQLModel).
"""
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

_engine = None


def get_engine():
    """Get or create the SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        settings.ensure_directories()
        url = settings.resolve_database_url()
        _engine = create_engine(url, echo=False, connect_args={"check_same_thread": False})
    return _engine


def init_db() -> None:
    """Create all tables if they don't exist."""
    # Import models so SQLModel registers them
    import app.models  # noqa: F401
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a database session (for FastAPI dependency injection)."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
