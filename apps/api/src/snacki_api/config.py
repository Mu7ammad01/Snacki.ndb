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
        # Une valeur refusée n'est jamais recopiée dans le message d'erreur : c'est souvent
        # un secret mal collé (mot de passe seul, URL incomplète) qui finirait dans le terminal
        # ou dans les journaux.
        hide_input_in_errors=True,
    )

    environment: Environment = "dev"
    # SecretStr : la valeur n'apparaît ni dans repr() ni dans les journaux ; hide_input_in_errors
    # couvre les messages d'erreur de validation.
    database_url: SecretStr
    cors_origins: list[str] = Field(default_factory=list)
    db_pool_size: int = Field(default=5, ge=1, le=20)
    # Adresse du client prise dans X-Forwarded-For (posé par le serveur web) pour la limite de
    # débit. À n'activer que si l'API n'est joignable que par le serveur web (IAM Cloud Run, J5) :
    # sinon n'importe qui pourrait choisir son adresse et contourner la limite.
    trust_forwarded_for: bool = False

    # --- Connexion du staff (J6, ADR 0008) ---
    # Client OAuth Google de l'environnement (un client par environnement, T22).
    oauth_client_id: str = ""
    oauth_client_secret: SecretStr | None = None
    # Adresse de retour enregistrée chez Google : https://<web>/auth/callback (jamais déduite
    # de la requête, pour qu'un en-tête Host forgé ne puisse pas la détourner).
    oauth_redirect_uri: str = ""
    # Clé de signature des sessions du staff (32 octets aléatoires au moins), dans Secret Manager.
    session_secret: SecretStr | None = None
    session_hours: int = Field(default=8, ge=1, le=12)
    # Premier compte administrateur, créé par la migration s'il n'existe encore aucun admin.
    bootstrap_admin_email: str = ""

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
            secret = self.session_secret.get_secret_value() if self.session_secret else ""
            if len(secret) < 32:
                raise ValueError("SNACKI_SESSION_SECRET obligatoire en staging et en production")
            if not (self.oauth_client_id and self.oauth_client_secret):
                raise ValueError("En staging et en production, le client OAuth est obligatoire")
            if not self.oauth_redirect_uri.startswith("https://"):
                raise ValueError("SNACKI_OAUTH_REDIRECT_URI doit être une adresse HTTPS")
            for origin in self.cors_origins:
                if not origin.startswith("https://"):
                    raise ValueError(f"Origine CORS non HTTPS refusée : {origin}")
        return self

    @property
    def auth_enabled(self) -> bool:
        """La connexion du staff n'est possible que si le client OAuth et la clé existent."""
        return bool(self.oauth_client_id and self.oauth_client_secret and self.session_secret)

    @property
    def docs_enabled(self) -> bool:
        """La documentation interactive (/docs) n'est servie qu'en développement et en test."""
        return self.environment in ("dev", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # valeurs lues dans l'environnement
