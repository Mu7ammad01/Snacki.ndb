"""Sauvegarde quotidienne de la base (ADR 0013).

L'historique de Neon (offre gratuite) ne permet de revenir que 6 heures en arrière. Chaque nuit,
une tâche Cloud Run lance `python -m snacki_api.manage backup` :

1. pg_dump au format « custom » (compressé, restaurable table par table) dans /tmp ;
2. contrôles : version de pg_dump suffisante pour le serveur, fichier non vide ;
3. envoi dans un bucket Cloud Storage séparé de Neon, avec le compte de la tâche
   (jeton du serveur de métadonnées : aucune clé). Le compte a le droit de créer des objets,
   pas de les lire ni de les effacer ; le bucket les garde 30 jours (règle de conservation).

Seules SNACKI_DATABASE_URL et SNACKI_BACKUP_BUCKET sont lues : la tâche n'a pas accès aux
secrets OAuth ni à la clé des sessions (moindre privilège).
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess  # nosec B404 : pg_dump est lancé sans shell, avec des arguments fixes
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import httpx

# Adresse du serveur de métadonnées Google (pas un secret) : il délivre le jeton du compte.
METADATA_TOKEN = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"  # noqa: S105  # nosec B105
)
UPLOAD = "https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o"
BUCKET = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
MIN_SIZE = 1024  # octets : en dessous, le fichier ne peut pas contenir la base


class BackupError(Exception):
    """Sauvegarde impossible : le message ne contient jamais l'URL de la base."""


def pg_env(database_url: str) -> dict[str, str]:
    """Variables libpq (PGHOST, PGPASSWORD…) : le mot de passe n'apparaît pas sur la ligne de
    commande, donc ni dans la liste des processus ni dans un message d'erreur."""
    parts = urlsplit(database_url.replace("postgresql+psycopg://", "postgresql://", 1))
    if parts.scheme not in ("postgres", "postgresql") or not parts.hostname:
        raise BackupError("SNACKI_DATABASE_URL invalide")
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    env = {
        "PGHOST": parts.hostname,
        "PGPORT": str(parts.port or 5432),
        "PGUSER": parts.username or "",
        "PGPASSWORD": parts.password or "",
        "PGDATABASE": parts.path.lstrip("/"),
        "PGSSLMODE": query.get("sslmode", "require"),
    }
    if "channel_binding" in query:
        env["PGCHANNELBINDING"] = query["channel_binding"]
    if env["PGSSLMODE"] not in ("require", "verify-ca", "verify-full"):
        raise BackupError("La sauvegarde exige une connexion chiffrée (sslmode=require)")
    return env


def object_name(env_name: str, now: datetime) -> str:
    """prod/2026/10/05/snacki-prod-20261005T030000Z.dump : tri chronologique naturel."""
    return f"{env_name}/{now:%Y/%m/%d}/snacki-{env_name}-{now:%Y%m%dT%H%M%SZ}.dump"


def major(version_text: str) -> int:
    """« pg_dump (PostgreSQL) 17.6 (Debian 17.6-1) » → 17."""
    m = re.search(r"(\d+)(?:\.\d+)?", version_text)
    if not m:
        raise BackupError("Version de pg_dump illisible")
    return int(m.group(1))


def check_versions(client_text: str, server_version_num: int) -> None:
    """pg_dump refuse un serveur plus récent que lui : on le dit clairement."""
    server = server_version_num // 10000
    if major(client_text) < server:
        raise BackupError(f"pg_dump {major(client_text)} trop ancien pour PostgreSQL {server}")


def _run(args: list[str], env: dict[str, str]) -> str:
    done = subprocess.run(  # noqa: S603  # nosec B603 : arguments fixes, pas de shell
        args, env={**os.environ, **env}, capture_output=True, text=True, timeout=600, check=False
    )
    if done.returncode != 0:
        # stderr de pg_dump : messages techniques, sans le mot de passe (passé par variable).
        raise BackupError(f"{args[0]} a échoué : {done.stderr.strip()[-300:]}")
    return done.stdout


def _token(client: httpx.Client) -> str:
    r = client.get(METADATA_TOKEN, headers={"Metadata-Flavor": "Google"}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def upload(client: httpx.Client, bucket: str, name: str, path: Path, token: str) -> None:
    """Envoi simple ; ifGenerationMatch=0 : jamais d'écrasement d'une sauvegarde existante."""
    url = UPLOAD.format(bucket=quote(bucket, safe=""))
    with path.open("rb") as body:
        r = client.post(
            url,
            params={"uploadType": "media", "name": name, "ifGenerationMatch": "0"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            },
            content=body,
            timeout=300,
        )
    if r.status_code >= 300:
        raise BackupError(f"Envoi refusé par Cloud Storage ({r.status_code})")


def run(now: datetime | None = None, client: httpx.Client | None = None) -> str:
    database_url = os.environ.get("SNACKI_DATABASE_URL", "")
    bucket = os.environ.get("SNACKI_BACKUP_BUCKET", "")
    env_name = os.environ.get("SNACKI_ENVIRONMENT", "prod")
    if not database_url:
        raise BackupError("SNACKI_DATABASE_URL manquant")
    if not BUCKET.fullmatch(bucket):
        raise BackupError("SNACKI_BACKUP_BUCKET manquant ou invalide")
    env = pg_env(database_url)
    server = _run(["psql", "-XAtc", "SHOW server_version_num"], env).strip()
    check_versions(_run(["pg_dump", "--version"], {}), int(server))
    now = now or datetime.now(UTC)
    name = object_name(env_name, now)
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "snacki.dump"
        _run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={dump}"],
            env,
        )
        size = dump.stat().st_size
        if size < MIN_SIZE:
            raise BackupError(f"Sauvegarde trop petite ({size} octets)")
        digest = hashlib.sha256(dump.read_bytes()).hexdigest()
        own = client is None
        client = client or httpx.Client()
        try:
            upload(client, bucket, name, dump, _token(client))
        finally:
            if own:
                client.close()
    return f"Sauvegarde envoyée : gs://{bucket}/{name} ({size} octets, sha256 {digest[:16]})"
