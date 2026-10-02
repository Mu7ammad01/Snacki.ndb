"""Point d'entrée de l'API Snacki.

Lancement local, depuis apps/api avec SNACKI_DATABASE_URL :
    uvicorn snacki_api.main:app --reload
"""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from snacki_api import orders, repository
from snacki_api.config import Settings, get_settings
from snacki_api.db import get_session
from snacki_api.models import Category
from snacki_api.ratelimit import DEFAULT_RULES, RateLimiter
from snacki_api.schemas import (
    Health,
    MenuOut,
    OrderCreatedOut,
    OrderIn,
    OrderTrackOut,
    ProductOut,
)

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
    # HTTPS obligatoire pendant un an (Cloud Run ne sert que du HTTPS ; ASVS V3.4.1).
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


TRACKING_HEADER = "X-Tracking-Token"
NOT_FOUND = "Commande introuvable ou lien expiré"


class Utf8JSONResponse(JSONResponse):
    """Type de contenu avec le jeu de caractères explicite (ASVS V4.1.1)."""

    media_type = "application/json; charset=utf-8"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Snacki API",
        version="0.4.0",
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
            allow_headers=["Content-Type", "Authorization", TRACKING_HEADER],
            allow_credentials=False,
        )

    limiter = RateLimiter(DEFAULT_RULES)
    app.state.limiter = limiter

    def client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if settings.trust_forwarded_for and forwarded:
            # Le serveur web n'envoie qu'une adresse : celle du client, vue par le dernier proxy.
            return forwarded.split(",")[0].strip()[:45]
        return request.client.host if request.client else "inconnu"

    def rate_limit(rule: str, request: Request) -> None:
        client = client_key(request)
        retry_after = limiter.hit(rule, client)
        if retry_after:
            raise HTTPException(
                status_code=429,
                detail="Trop de requêtes, réessayez dans un instant",
                headers={"Retry-After": str(retry_after)},
            )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.path.startswith("/v1/orders"):
            # Réponses avec jeton ou données de commande : jamais en cache.
            response.headers["Cache-Control"] = "no-store"
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

    @app.post("/v1/orders", response_model=OrderCreatedOut, status_code=201, tags=["commandes"])
    def create_order(data: OrderIn, request: Request, session: SessionDep) -> OrderCreatedOut:
        """Crée une commande. Le client envoie des produits et des quantités ; l'API lit les prix
        en base et calcule le total. Le jeton de suivi n'est renvoyé qu'une seule fois."""
        rate_limit("order_create", request)
        try:
            order, token = orders.create_order(session, data)
        except orders.ProduitIndisponible as exc:
            raise HTTPException(status_code=422, detail=f"Produit indisponible : {exc}") from None
        return OrderCreatedOut.model_validate(
            {
                **OrderTrackOut.model_validate(order).model_dump(),
                "tracking_token": token,
                "tracking_expires_at": order.tracking_expires_at,
            }
        )

    @app.get("/v1/orders/track", response_model=OrderTrackOut, tags=["commandes"])
    def track_order(
        request: Request,
        session: SessionDep,
        token: Annotated[str, Header(alias=TRACKING_HEADER)],
    ) -> OrderTrackOut:
        """Suivi d'une commande. Le jeton voyage dans un en-tête, jamais dans l'URL (T03) :
        il n'apparaît ni dans les journaux, ni dans l'historique, ni dans l'en-tête Referer."""
        rate_limit("order_track", request)
        order = orders.find_by_token(session, token)
        if order is None:
            # Même réponse pour « inconnu », « expiré » et « mal formé » : rien à deviner.
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return OrderTrackOut.model_validate(order)

    return app


def __getattr__(name: str):
    # `uvicorn snacki_api.main:app` : l'application n'est construite qu'à l'import de `app`,
    # pour que les tests puissent fournir leur propre configuration.
    if name == "app":
        return create_app()
    raise AttributeError(name)
