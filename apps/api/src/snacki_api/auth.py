"""Connexion du staff avec Google (OAuth 2.0 + OpenID Connect, PKCE) et sessions signées (J6).

Le navigateur ne parle jamais à l'API (elle est privée) : le serveur web relaie. L'API garde
les secrets (secret du client OAuth, clé des sessions) et prend toutes les décisions :

1. `start` : l'API tire `state`, `nonce` et le vérificateur PKCE, les signe dans un « jeton de
   parcours » valable 10 minutes (stocké par le web dans un cookie HttpOnly), et renvoie
   l'adresse de Google.
2. `finish` : l'API vérifie que `state` correspond, échange le code chez Google avec le
   vérificateur PKCE et le secret du client, puis vérifie le jeton d'identité (signature,
   audience, émetteur, expiration, nonce, e-mail vérifié).
3. La session est un JWT signé par l'API (HS256) : identifiant du staff et version de session.
   Le rôle n'y figure pas : il est relu en base à chaque requête (T12).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # noqa: S105  # adresse, pas un secret  # nosec B105
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

FLOW_AUDIENCE = "snacki:oauth-flow"
SESSION_AUDIENCE = "snacki:staff"
FLOW_MINUTES = 10


class AuthError(Exception):
    """Connexion refusée. Le motif reste dans les journaux, jamais dans la réponse."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def pkce_pair() -> tuple[str, str]:
    """Vérificateur PKCE (43 caractères, 256 bits) et son défi S256 (RFC 7636)."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    name: str | None


class GoogleOIDC:
    """Client OpenID Connect pour Google. `http` et `signing_key` sont remplaçables en test."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http: httpx.Client | None = None,
        signing_key: Callable[[str], Any] | None = None,
    ) -> None:
        self.client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._http = http or httpx.Client(timeout=5.0)
        self._signing_key = signing_key or _google_signing_key

    def authorization_url(self, state: str, nonce: str, challenge: str) -> str:
        query = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE}?{urlencode(query)}"

    def exchange_code(self, code: str, verifier: str) -> str:
        """Échange le code d'autorisation contre un jeton d'identité (canal serveur à serveur)."""
        response = self._http.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        if response.status_code != 200:
            raise AuthError(f"échange du code refusé par Google ({response.status_code})")
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise AuthError("réponse de Google sans jeton d'identité")
        return id_token

    def verify_id_token(self, id_token: str, nonce: str) -> GoogleIdentity:
        try:
            claims = jwt.decode(
                id_token,
                self._signing_key(id_token),
                algorithms=["RS256"],  # jamais « none » ni HS256 : l'algorithme est imposé
                audience=self.client_id,
                issuer=GOOGLE_ISSUERS,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]},
                leeway=30,
            )
        except jwt.PyJWTError as exc:
            raise AuthError(f"jeton d'identité invalide : {type(exc).__name__}") from None
        if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
            raise AuthError("nonce différent : jeton rejoué ou d'une autre connexion")
        if claims.get("email_verified") is not True:
            raise AuthError("adresse e-mail non vérifiée par Google")
        name = claims.get("name")
        return GoogleIdentity(
            email=str(claims["email"]).strip().lower(),
            name=str(name)[:80] if name else None,
        )


_jwks_client: jwt.PyJWKClient | None = None


def _google_signing_key(token: str) -> Any:
    """Clé publique de Google pour ce jeton (clés mises en cache, renouvelées par Google)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(GOOGLE_JWKS, cache_keys=True, lifespan=3600)
    return _jwks_client.get_signing_key_from_jwt(token).key


# --- Jeton de parcours (le temps d'aller chez Google et d'en revenir) ---------------------


def new_flow(secret: str) -> tuple[str, dict[str, str]]:
    """Renvoie le jeton de parcours signé et les valeurs à envoyer à Google."""
    verifier, challenge = pkce_pair()
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": FLOW_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=FLOW_MINUTES),
            "state": state,
            "nonce": nonce,
            "verifier": verifier,
        },
        secret,
        algorithm="HS256",
    )
    return token, {"state": state, "nonce": nonce, "challenge": challenge}


def read_flow(secret: str, flow: str, state: str) -> dict[str, str]:
    try:
        claims = jwt.decode(flow, secret, algorithms=["HS256"], audience=FLOW_AUDIENCE)
    except jwt.PyJWTError as exc:
        raise AuthError(f"parcours de connexion invalide : {type(exc).__name__}") from None
    # `state` lie le retour de Google à CE navigateur : protège contre le CSRF de connexion.
    if not hmac.compare_digest(str(claims.get("state", "")), state):
        raise AuthError("state différent")
    return claims


# --- Session du staff ---------------------------------------------------------------------


def new_session(secret: str, staff_id: int, version: int, hours: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "aud": SESSION_AUDIENCE,
            "sub": str(staff_id),
            "ver": version,
            "iat": now,
            "exp": now + timedelta(hours=hours),
        },
        secret,
        algorithm="HS256",
    )


def read_session(secret: str, token: str) -> tuple[int, int]:
    """Renvoie (identifiant du staff, version de session) ou lève AuthError."""
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=SESSION_AUDIENCE,
            options={"require": ["exp", "sub", "ver"]},
        )
        return int(claims["sub"]), int(claims["ver"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise AuthError("session invalide ou expirée") from None
