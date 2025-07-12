import os
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///scoresight/database/scoresight.db")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()


# Database setup
def resolve_sqlite_path(db_url: str) -> str:
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        rel_path = db_url.replace("sqlite:///", "")
        abs_path = Path(__file__).parent.parent / rel_path
        abs_path = abs_path.resolve()
        return f"sqlite:///{abs_path}"
    return db_url

settings = get_settings()
db_url = resolve_sqlite_path(settings.DATABASE_URL)
engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        
        # Try a simple query to test connection
        try:
            db.execute(text("SELECT 1"))
            print("DB connection test: SUCCESS")
        except Exception as e:
            print(f"DB connection test: FAILED - {e}")
        yield db
    finally:
        db.close()
