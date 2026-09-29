"""Connexion à PostgreSQL (SQLAlchemy 2)."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from snacki_api.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        # Neon met la base en veille après 5 min : on vérifie la connexion avant de la réutiliser.
        pool_pre_ping=True,
        pool_recycle=300,
        # Coupe les requêtes trop longues (10 s) : protège la base contre un abus coûteux.
        connect_args={"options": "-c statement_timeout=10000"},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, toujours refermée."""
    with get_sessionmaker()() as session:
        yield session
