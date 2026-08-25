from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=Session,
)


def get_db_session() -> Session:
    return SessionLocal()