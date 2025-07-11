import pytest
import sqlalchemy
import asyncio
import os
import tempfile
import shutil
from fastapi.testclient import TestClient
from app.main import create_app
from app.deps import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest_asyncio

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def db_engine():
    # Use a temporary SQLite DB for tests
    db_fd, db_path = tempfile.mkstemp()
    engine = create_engine(f"sqlite:///{db_path}")
    yield engine
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope="function")
def override_get_db(db_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    return _get_db
