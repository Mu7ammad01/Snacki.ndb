"""Point d'entrée de l'API Snacki.

Lancement local, depuis apps/api avec SNACKI_DATABASE_URL :
    uvicorn snacki_api.main:app --reload
"""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from snacki_api import repository
from snacki_api.config import Settings, get_settings
from snacki_api.db import get_session
from snacki_api.models import Category
from snacki_api.schemas import Health, MenuOut, ProductOut

log = logging.getLogger("snacki.api")

SessionDep = Annotated[Session, Depends(get_session)]
# Identifiant de produit : lettres minuscules et tirets, comme en base (liste blanche, ASVS V2.2.1).
ProductId = Annotated[str, Path(pattern=r"^[a-z][a-z-]{0,39}$")]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # L'API ne sert que du JSON : aucune ressource ne doit être chargée si une réponse est ouverte
    # dans un navigateur (ASVS V3.2.1).
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-site",
}


class Utf8JSONResponse(JSONResponse):
    """Type de contenu avec le jeu de caractères explicite (ASVS V4.1.1)."""

    media_type = "application/json; charset=utf-8"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Snacki API",
        version="0.2.0",
        default_response_class=Utf8JSONResponse,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    if settings.cors_origins:
        # Origines fixes, jamais recopiées depuis la requête (ASVS V3.4.2).
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Content-Type", "Authorization"],
            allow_credentials=False,
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> Utf8JSONResponse:
        # Le détail (requête, table, hôte) reste dans les journaux, jamais dans la réponse.
        log.error(
            "Erreur base de données sur %s %s", request.method, request.url.path, exc_info=exc
        )
        return Utf8JSONResponse({"detail": "Service momentanément indisponible"}, status_code=503)

    @app.get("/healthz", response_model=Health, tags=["exploitation"])
    def healthz() -> Health:
        """Vivacité : le processus répond (ne touche pas la base)."""
        return Health(status="ok")

    @app.get("/readyz", response_model=Health, tags=["exploitation"])
    def readyz(session: SessionDep) -> Health:
        """Disponibilité : la base répond."""
        session.execute(text("SELECT 1"))  # requête constante, sans donnée externe
        return Health(status="ok")

    @app.get("/v1/menu", response_model=MenuOut, tags=["menu"])
    def menu(
        session: SessionDep,
        category: Annotated[Category | None, Query(description="jus ou delices")] = None,
    ) -> MenuOut:
        products = repository.list_menu(session, category)
        return MenuOut(products=[ProductOut.model_validate(p) for p in products])

    @app.get("/v1/menu/{product_id}", response_model=ProductOut, tags=["menu"])
    def product(product_id: ProductId, session: SessionDep) -> ProductOut:
        found = repository.get_product(session, product_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Produit introuvable")
        return ProductOut.model_validate(found)

    return app


def __getattr__(name: str):
    # `uvicorn snacki_api.main:app` : l'application n'est construite qu'à l'import de `app`,
    # pour que les tests puissent fournir leur propre configuration.
    if name == "app":
        return create_app()
    raise AttributeError(name)
