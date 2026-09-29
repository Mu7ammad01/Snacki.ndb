"""Configuration de l'API, lue uniquement dans les variables d'environnement.

Règle de J2 : aucun secret dans le code. `database_url` n'a pas de valeur par défaut :
si la variable manque, l'API refuse de démarrer au lieu de se connecter n'importe où.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "test", "staging", "prod"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SNACKI_",
        env_file=".env",  # confort local ; fichier ignoré par git et bloqué par pre-commit
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "dev"
    # SecretStr : la valeur n'apparaît ni dans repr(), ni dans les journaux, ni dans les erreurs.
    database_url: SecretStr
    cors_origins: list[str] = Field(default_factory=list)
    db_pool_size: int = Field(default=5, ge=1, le=20)

    @field_validator("database_url")
    @classmethod
    def _driver_psycopg(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value()
        # Neon fournit « postgresql://… » : on impose le pilote psycopg 3.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg://" + url[len(prefix) :]
        if not url.startswith("postgresql+psycopg://"):
            raise ValueError("SNACKI_DATABASE_URL doit être une URL PostgreSQL")
        return SecretStr(url)

    @model_validator(mode="after")
    def _regles_production(self) -> "Settings":
        if self.environment in ("staging", "prod"):
            query = parse_qs(urlsplit(self.database_url.get_secret_value()).query)
            if query.get("sslmode", [""])[0] not in ("require", "verify-full"):
                raise ValueError("En staging et en production, la base exige sslmode=require")
            for origin in self.cors_origins:
                if not origin.startswith("https://"):
                    raise ValueError(f"Origine CORS non HTTPS refusée : {origin}")
        return self

    @property
    def docs_enabled(self) -> bool:
        """La documentation interactive (/docs) n'est servie qu'en développement et en test."""
        return self.environment in ("dev", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # valeurs lues dans l'environnement
