"""SQLite database engine and session factory."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.db.url,
    connect_args={"check_same_thread": False},  # SQLite requires this
    echo=False,  # SQL logging — set True to debug queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
