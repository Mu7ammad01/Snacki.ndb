"""Les tests tournent sur un vrai PostgreSQL (comme Neon), jamais sur SQLite.

Base de test : SNACKI_TEST_DATABASE_URL (par défaut, la base locale de apps/api/README.md).
Chaque session de tests repart d'un schéma vide et rejoue toutes les migrations Alembic.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

API_DIR = Path(__file__).resolve().parents[1]
TEST_DB = os.environ.get(
    "SNACKI_TEST_DATABASE_URL", "postgresql://snacki:devpass@localhost:5433/snacki_test"
)
os.environ["SNACKI_DATABASE_URL"] = TEST_DB
os.environ["SNACKI_ENVIRONMENT"] = "test"

from snacki_api.config import Settings, get_settings  # noqa: E402
from snacki_api.db import get_engine, get_sessionmaker  # noqa: E402
from snacki_api.main import create_app  # noqa: E402


def _alembic() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def database():
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    cfg = _alembic()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings))
