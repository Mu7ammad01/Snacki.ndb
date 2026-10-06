"""Point d'entrée de l'API Snacki.

Lancement local, depuis apps/api avec SNACKI_DATABASE_URL :
    uvicorn snacki_api.main:app --reload
"""

import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from snacki_api import assistant, auth, caisse, loyalty, orders, pilotage, repository, staff
from snacki_api.config import Settings, get_settings
from snacki_api.db import get_session
from snacki_api.models import Category, StaffRole, StaffUser
from snacki_api.ratelimit import DEFAULT_RULES, RateLimiter
from snacki_api.schemas import (
    AcceptIn,
    AdvanceIn,
    AssistantIn,
    AssistantOut,
    AuthCallbackIn,
    AuthSessionOut,
    AuthStartOut,
    CaisseDayOut,
    CaisseOrderOut,
    CounterOrderIn,
    Health,
    LoyaltyBlockIn,
    LoyaltyCodeIn,
    LoyaltyOut,
    LoyaltyPhoneIn,
    LoyaltyPublicOut,
    LoyaltyTransferIn,
    MenuOut,
    OrderCreatedOut,
    OrderIn,
    OrderTrackOut,
    PayIn,
    PilotageOut,
    ProductOut,
    ReasonIn,
    StaffCreateIn,
    StaffMeOut,
    StaffOut,
    StaffUpdateIn,
)

log = logging.getLogger("snacki.api")

SessionDep = Annotated[Session, Depends(get_session)]
# Identifiant de produit : lettres minuscules et tirets, comme en base (liste blanche, ASVS V2.2.1).
ProductId = Annotated[str, Path(pattern=r"^[a-z][a-z-]{0,39}$")]

# Réponses avec jeton, données de commande ou chiffres de vente : jamais en cache.
NO_STORE = ("/v1/orders", "/v1/auth", "/v1/staff", "/v1/caisse", "/v1/pilotage", "/v1/loyalty")

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
SESSION_HEADER = "X-Staff-Session"  # posé par le serveur web à partir du cookie HttpOnly
LOGIN_REFUSED = "Connexion refusée"
ALL_STAFF = (StaffRole.CAISSIER, StaffRole.GERANTE, StaffRole.ADMIN)
NOT_FOUND = "Commande introuvable ou lien expiré"


class Utf8JSONResponse(JSONResponse):
    """Type de contenu avec le jeu de caractères explicite (ASVS V4.1.1)."""

    media_type = "application/json; charset=utf-8"


def create_app(settings: Settings | None = None, oidc: auth.GoogleOIDC | None = None) -> FastAPI:
    settings = settings or get_settings()
    if oidc is None and settings.auth_enabled:
        oidc = auth.GoogleOIDC(
            settings.oauth_client_id,
            settings.oauth_client_secret.get_secret_value(),  # type: ignore[union-attr]
            settings.oauth_redirect_uri,
        )
    app = FastAPI(
        title="Snacki API",
        version="0.7.0",
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
        if request.url.path.startswith(NO_STORE):
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

    # --- Connexion du staff (J6) ------------------------------------------------------------

    def session_secret() -> str:
        if not (settings.auth_enabled and oidc):
            raise HTTPException(status_code=503, detail="Connexion du staff non configurée")
        return settings.session_secret.get_secret_value()  # type: ignore[union-attr]

    def require_role(*roles: StaffRole):
        """Dépendance de contrôle d'accès : session valide, compte actif, rôle autorisé.

        Le rôle est relu en base à chaque requête : un changement ou une désactivation
        s'applique tout de suite (T12). Un refus de rôle est inscrit au journal (T09).
        """

        def dependency(
            request: Request,
            session: SessionDep,
            token: Annotated[str | None, Header(alias=SESSION_HEADER)] = None,
        ) -> StaffUser:
            secret = session_secret()
            try:
                staff_id, version = auth.read_session(secret, token or "")
            except auth.AuthError:
                raise HTTPException(status_code=401, detail="Session absente ou expirée") from None
            user = session.get(StaffUser, staff_id)
            if user is None or not user.active or user.session_version != version:
                raise HTTPException(status_code=401, detail="Session absente ou expirée")
            if user.role not in roles:
                staff.audit(session, "access_denied", user, f"{request.method} {request.url.path}")
                session.commit()
                raise HTTPException(status_code=403, detail="Accès réservé")
            return user

        dependency.snacki_roles = roles  # type: ignore[attr-defined]  # lu par le test des routes
        return dependency

    StaffDep = Annotated[StaffUser, Depends(require_role(*ALL_STAFF))]
    AdminDep = Annotated[StaffUser, Depends(require_role(StaffRole.ADMIN))]

    @app.post("/v1/auth/start", response_model=AuthStartOut, tags=["connexion"])
    def auth_start(request: Request) -> AuthStartOut:
        """Prépare la connexion Google : state, nonce et PKCE, signés dans un jeton de parcours."""
        rate_limit("auth", request)
        secret = session_secret()
        flow, values = auth.new_flow(secret)
        url = oidc.authorization_url(values["state"], values["nonce"], values["challenge"])  # type: ignore[union-attr]
        return AuthStartOut(authorization_url=url, flow=flow)

    @app.post("/v1/auth/callback", response_model=AuthSessionOut, tags=["connexion"])
    def auth_callback(
        data: AuthCallbackIn, request: Request, session: SessionDep
    ) -> AuthSessionOut:
        """Retour de Google. Toute erreur donne la même réponse ; le motif va au journal."""
        rate_limit("auth", request)
        secret = session_secret()
        email = None
        try:
            flow = auth.read_flow(secret, data.flow, data.state)
            id_token = oidc.exchange_code(data.code, flow["verifier"])  # type: ignore[union-attr]
            identity = oidc.verify_id_token(id_token, flow["nonce"])  # type: ignore[union-attr]
            email = identity.email
            user = staff.by_email(session, email)
            if user is None or not user.active:
                raise auth.AuthError("adresse absente de l'équipe ou compte désactivé")
        except auth.AuthError as exc:
            log.warning("Connexion refusée : %s", exc)
            staff.audit(session, "login_refused", None, email, {"motif": str(exc)[:200]})
            session.commit()
            raise HTTPException(status_code=401, detail=LOGIN_REFUSED) from None
        staff.record_login(session, user, identity.name)
        session.commit()
        token = auth.new_session(secret, user.id, user.session_version, settings.session_hours)
        return AuthSessionOut(session=token, staff=StaffMeOut.model_validate(user))

    @app.post("/v1/auth/logout", status_code=204, tags=["connexion"])
    def auth_logout(user: StaffDep, session: SessionDep) -> None:
        """Déconnexion : toutes les sessions de ce compte deviennent invalides."""
        staff.logout(session, user)
        session.commit()

    @app.get("/v1/staff/me", response_model=StaffMeOut, tags=["équipe"])
    def staff_me(user: StaffDep) -> StaffMeOut:
        return StaffMeOut.model_validate(user)

    @app.get("/v1/staff", response_model=list[StaffOut], tags=["équipe"])
    def staff_list(_admin: AdminDep, session: SessionDep) -> list[StaffOut]:
        return [StaffOut.model_validate(u) for u in staff.list_staff(session)]

    @app.post("/v1/staff", response_model=StaffOut, status_code=201, tags=["équipe"])
    def staff_add(data: StaffCreateIn, admin: AdminDep, session: SessionDep) -> StaffOut:
        try:
            user = staff.add(session, admin, data.email, data.role)
        except staff.StaffError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        session.commit()
        return StaffOut.model_validate(user)

    @app.patch("/v1/staff/{staff_id}", response_model=StaffOut, tags=["équipe"])
    def staff_update(
        staff_id: Annotated[int, Path(ge=1)],
        data: StaffUpdateIn,
        admin: AdminDep,
        session: SessionDep,
    ) -> StaffOut:
        user = session.get(StaffUser, staff_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        try:
            staff.update(session, admin, user, data.role, data.active)
        except staff.StaffError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from None
        session.commit()
        return StaffOut.model_validate(user)

    # --- Caisse (J7) -----------------------------------------------------------------------

    ManagerDep = Annotated[StaffUser, Depends(require_role(*caisse.MANAGERS))]
    OrderId = Annotated[int, Path(ge=1)]

    def act(session: Session, order_id: int, action) -> CaisseOrderOut:
        """Verrouille la commande, applique l'action, valide ; 404 / 409 sinon."""
        order = caisse.locked(session, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Commande introuvable")
        try:
            action(order)
        except caisse.CaisseError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from None
        session.commit()
        return CaisseOrderOut.model_validate(order)

    @app.get("/v1/caisse/orders", response_model=CaisseDayOut, tags=["caisse"])
    def caisse_orders(_user: StaffDep, session: SessionDep) -> CaisseDayOut:
        """Commandes du jour, les plus récentes d'abord (interrogé toutes les 5 s par la caisse)."""
        return CaisseDayOut(
            server_time=datetime.now(UTC),
            orders=[CaisseOrderOut.model_validate(o) for o in caisse.today_orders(session)],
        )

    @app.post("/v1/caisse/orders", response_model=CaisseOrderOut, status_code=201, tags=["caisse"])
    def caisse_counter(data: CounterOrderIn, user: StaffDep, session: SessionDep) -> CaisseOrderOut:
        try:
            order = caisse.counter_sale(session, user, data)
        except orders.ProduitIndisponible as exc:
            raise HTTPException(status_code=422, detail=f"Produit indisponible : {exc}") from None
        return CaisseOrderOut.model_validate(order)

    @app.post("/v1/caisse/assistant", response_model=AssistantOut, tags=["caisse"])
    def caisse_assistant(
        request: Request, data: AssistantIn, user: StaffDep, session: SessionDep
    ) -> AssistantOut:
        """J9 : message WhatsApp → proposition de vente, à vérifier ; rien n'est créé (T13, T14)."""
        rate_limit("assistant", request)
        cfg = settings
        key = cfg.gemini_api_key.get_secret_value() if cfg.gemini_api_key else ""
        result = assistant.analyse(data.text, repository.list_menu(session), key, cfg.gemini_model)
        # Le message n'est jamais enregistré : seulement sa longueur et le résultat.
        staff.audit(
            session,
            "assistant",
            user,
            None,
            {"moteur": result["engine"], "lignes": len(result["lines"]), "car": len(data.text)},
        )
        session.commit()
        return AssistantOut.model_validate(result)

    @app.post("/v1/caisse/orders/{order_id}/accept", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_accept(
        order_id: OrderId, data: AcceptIn, user: StaffDep, session: SessionDep
    ) -> CaisseOrderOut:
        return act(
            session,
            order_id,
            lambda o: caisse.accept(session, user, o, data.ready_in_min, data.delivery_fee_mru),
        )

    @app.post("/v1/caisse/orders/{order_id}/status", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_advance(
        order_id: OrderId, data: AdvanceIn, user: StaffDep, session: SessionDep
    ) -> CaisseOrderOut:
        return act(session, order_id, lambda o: caisse.advance(session, user, o, data.status))

    @app.post("/v1/caisse/orders/{order_id}/called", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_called(order_id: OrderId, user: StaffDep, session: SessionDep) -> CaisseOrderOut:
        return act(session, order_id, lambda o: caisse.mark_called(session, user, o))

    @app.post("/v1/caisse/orders/{order_id}/pay", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_pay(
        order_id: OrderId, data: PayIn, user: StaffDep, session: SessionDep
    ) -> CaisseOrderOut:
        return act(session, order_id, lambda o: caisse.pay(session, user, o, data.method))

    @app.post("/v1/caisse/orders/{order_id}/refuse", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_refuse(
        order_id: OrderId, data: ReasonIn, user: ManagerDep, session: SessionDep
    ) -> CaisseOrderOut:
        return act(
            session,
            order_id,
            lambda o: caisse.close(session, user, o, caisse.S.REFUSEE, data.reason),
        )

    @app.post("/v1/caisse/orders/{order_id}/cancel", response_model=CaisseOrderOut, tags=["caisse"])
    def caisse_cancel(
        order_id: OrderId, data: ReasonIn, user: ManagerDep, session: SessionDep
    ) -> CaisseOrderOut:
        return act(
            session,
            order_id,
            lambda o: caisse.close(session, user, o, caisse.S.ANNULEE, data.reason),
        )

    # --- Pilotage (J8) ----------------------------------------------------------------------

    @app.get("/v1/pilotage", response_model=PilotageOut, tags=["pilotage"])
    def pilotage_summary(
        _user: ManagerDep,
        session: SessionDep,
        start: Annotated[date | None, Query()] = None,
        end: Annotated[date | None, Query()] = None,
    ) -> PilotageOut:
        """Chiffre d'affaires, top produits, paiements : gérante et admin seulement (T26)."""
        default_start, default_end = pilotage.default_period()
        start, end = start or default_start, end or default_end
        if start > end or (end - start).days >= pilotage.MAX_DAYS:
            raise HTTPException(status_code=422, detail="Période invalide (366 jours au plus)")
        return PilotageOut.model_validate(pilotage.summary(session, start, end))

    # --- Fidélité (J8 bis) ------------------------------------------------------------------

    def loyalty_act(session: Session, order_id: int, action) -> CaisseOrderOut:
        """Comme act(), mais une carte inconnue ou refusée renvoie aussi 409 avec son motif."""

        def run(order):
            try:
                action(order)
            except loyalty.LoyaltyError as exc:
                raise caisse.CaisseError(str(exc)) from None

        return act(session, order_id, run)

    @app.post(
        "/v1/caisse/orders/{order_id}/loyalty", response_model=CaisseOrderOut, tags=["fidélité"]
    )
    def caisse_stamp(
        order_id: OrderId, data: LoyaltyCodeIn, user: StaffDep, session: SessionDep
    ) -> CaisseOrderOut:
        """Tampon : la commande encaissée est liée à la carte (une fois)."""
        return loyalty_act(
            session, order_id, lambda o: loyalty.stamp(session, user, o, data.code, data.phone)
        )

    @app.post(
        "/v1/caisse/orders/{order_id}/reward", response_model=CaisseOrderOut, tags=["fidélité"]
    )
    def caisse_reward(
        order_id: OrderId, data: LoyaltyCodeIn, user: StaffDep, session: SessionDep
    ) -> CaisseOrderOut:
        """Cadeau : 100 MRU au plus retirés d'une commande pas encore encaissée."""
        return loyalty_act(session, order_id, lambda o: loyalty.redeem(session, user, o, data.code))

    def card_or_error(session: Session, text: str):
        try:
            return loyalty.find(session, text)
        except loyalty.LoyaltyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None

    @app.post("/v1/caisse/loyalty", response_model=LoyaltyOut, tags=["fidélité"])
    def caisse_card(
        request: Request, data: LoyaltyCodeIn, _user: StaffDep, session: SessionDep
    ) -> LoyaltyOut:
        """État d'une carte pour la caisse (numéro dans le corps, jamais dans l'URL)."""
        rate_limit("loyalty", request)
        return LoyaltyOut(**loyalty.summary(card_or_error(session, data.code)))

    @app.post("/v1/loyalty/status", response_model=LoyaltyPublicOut, tags=["fidélité"])
    def card_public(request: Request, data: LoyaltyCodeIn, session: SessionDep) -> LoyaltyPublicOut:
        """Le client suit sa carte (QR) : progression seulement, limite de débit (T28)."""
        rate_limit("loyalty", request)
        info = loyalty.summary(card_or_error(session, data.code))
        return LoyaltyPublicOut(**{k: info[k] for k in LoyaltyPublicOut.model_fields})

    def manager_card(session: Session, action) -> LoyaltyOut:
        try:
            card = action()
        except loyalty.LoyaltyError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from None
        session.commit()
        return LoyaltyOut(**loyalty.summary(card))

    @app.post("/v1/loyalty/block", response_model=LoyaltyOut, tags=["fidélité"])
    def card_block(data: LoyaltyBlockIn, user: ManagerDep, session: SessionDep) -> LoyaltyOut:
        """Carte perdue, volée ou suspecte : plus de tampon ni de cadeau (gérante, admin)."""
        return manager_card(session, lambda: loyalty.block(session, user, data.code, data.reason))

    @app.post("/v1/loyalty/transfer", response_model=LoyaltyOut, tags=["fidélité"])
    def card_transfer(data: LoyaltyTransferIn, user: ManagerDep, session: SessionDep) -> LoyaltyOut:
        """Carte perdue : tampons reportés sur une carte neuve (gérante, admin)."""
        return manager_card(
            session, lambda: loyalty.transfer(session, user, data.old_code, data.new_code)
        )

    @app.post("/v1/loyalty/search", response_model=list[LoyaltyOut], tags=["fidélité"])
    def card_search(
        data: LoyaltyPhoneIn, _user: ManagerDep, session: SessionDep
    ) -> list[LoyaltyOut]:
        """Retrouver la carte d'un client par son téléphone (gérante, admin)."""
        return [LoyaltyOut(**loyalty.summary(c)) for c in loyalty.search_phone(session, data.phone)]

    return app


def __getattr__(name: str):
    # `uvicorn snacki_api.main:app` : l'application n'est construite qu'à l'import de `app`,
    # pour que les tests puissent fournir leur propre configuration.
    if name == "app":
        return create_app()
    raise AttributeError(name)
