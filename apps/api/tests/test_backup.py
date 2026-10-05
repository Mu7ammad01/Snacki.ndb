"""Sauvegarde nocturne (ADR 0013) : sans réseau ni pg_dump, tout ce qui peut se vérifier ici."""

from datetime import UTC, datetime

import httpx
import pytest

from snacki_api import backup

URL = "postgresql://snacki:s3cret@ep-x.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def test_variables_libpq_sans_mot_de_passe_en_argument():
    env = backup.pg_env(URL)
    assert env["PGHOST"] == "ep-x.eu-central-1.aws.neon.tech"
    assert env["PGUSER"] == "snacki" and env["PGPASSWORD"] == "s3cret"
    assert env["PGDATABASE"] == "neondb" and env["PGPORT"] == "5432"
    assert env["PGSSLMODE"] == "require" and env["PGCHANNELBINDING"] == "require"
    psycopg_url = URL.replace("postgresql://", "postgresql+psycopg://")
    assert backup.pg_env(psycopg_url)["PGUSER"] == "snacki"


@pytest.mark.parametrize("url", ["", "mysql://a@b/c", "postgresql://u:p@h/db?sslmode=disable"])
def test_url_refusee_sans_la_recopier(url):
    with pytest.raises(backup.BackupError) as err:
        backup.pg_env(url)
    assert "p@h" not in str(err.value)


def test_nom_des_sauvegardes_chronologique():
    now = datetime(2026, 10, 5, 3, 0, 7, tzinfo=UTC)
    assert backup.object_name("prod", now) == "prod/2026/10/05/snacki-prod-20261005T030007Z.dump"


def test_version_de_pg_dump():
    backup.check_versions("pg_dump (PostgreSQL) 17.6 (Debian 17.6-1)", 170004)
    backup.check_versions("pg_dump (PostgreSQL) 17.6", 160009)
    with pytest.raises(backup.BackupError, match="trop ancien"):
        backup.check_versions("pg_dump (PostgreSQL) 15.14", 170004)


def test_envoi_sans_ecrasement(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={})

    f = tmp_path / "x.dump"
    f.write_bytes(b"x" * 2048)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backup.upload(client, "snacki-ndb-2026-backups", "prod/a.dump", f, "jeton")
    assert "ifGenerationMatch=0" in seen["url"] and "uploadType=media" in seen["url"]
    assert "/b/snacki-ndb-2026-backups/o" in seen["url"]
    assert seen["auth"] == "Bearer jeton"


def test_envoi_refuse(tmp_path):
    f = tmp_path / "x.dump"
    f.write_bytes(b"x")
    refused = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(412)))
    with refused as client, pytest.raises(backup.BackupError, match="412"):
        backup.upload(client, "b-ok", "prod/a.dump", f, "jeton")


def test_configuration_obligatoire(monkeypatch):
    monkeypatch.setenv("SNACKI_DATABASE_URL", URL)
    monkeypatch.delenv("SNACKI_BACKUP_BUCKET", raising=False)
    with pytest.raises(backup.BackupError, match="BUCKET"):
        backup.run()
    monkeypatch.setenv("SNACKI_BACKUP_BUCKET", "../evil")
    with pytest.raises(backup.BackupError, match="BUCKET"):
        backup.run()
