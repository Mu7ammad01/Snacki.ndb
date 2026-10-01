#!/usr/bin/env python3
"""Vérifie que les réglages de sécurité du dépôt GitHub sont bien en place.

Les réglages sont appliqués par infra/github/setup-repo.sh ; ce script prouve qu'ils le
sont encore (un réglage peut être désactivé par erreur dans l'interface GitHub).

    GH_TOKEN=$(gh auth token) python3 scripts/verify_repo_security.py --repo OWNER/snacki

Le jeton doit pouvoir lire l'administration du dépôt (c'est le cas du jeton de `gh auth login`
pour le propriétaire). Code de sortie 1 si un contrôle échoue.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 - seulement `gh auth token`, sans shell
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

API = "https://api.github.com"
REQUIRED_CHECKS = ("secrets", "quality", "tests", "api", "web")

# fetch(chemin) -> (code HTTP, corps JSON ou None)
Fetch = Callable[[str], tuple[int, dict | None]]


@dataclass(frozen=True)
class Result:
    id: str
    label: str
    ok: bool
    detail: str = ""


def github_fetch(token: str) -> Fetch:
    def fetch(path: str) -> tuple[int, dict | None]:
        req = urllib.request.Request(  # noqa: S310 - URL fixe en https
            f"{API}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "snacki-verify-repo-security",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310  # nosec B310
                body = resp.read()
                return resp.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as err:
            body = err.read()
            try:
                return err.code, json.loads(body) if body else None
            except json.JSONDecodeError:
                return err.code, None

    return fetch


def _enabled(block: dict | None) -> bool:
    return bool(block) and block.get("status") == "enabled"


def run_checks(fetch: Fetch, repo: str, branch: str = "main") -> list[Result]:
    results: list[Result] = []
    status, info = fetch(f"/repos/{repo}")
    if status != 200 or info is None:
        return [Result("R0", "Dépôt accessible", False, f"HTTP {status}")]

    sa = info.get("security_and_analysis") or {}
    results.append(
        Result("R1", "Analyse des secrets", _enabled(sa.get("secret_scanning")), "secret_scanning")
    )
    results.append(
        Result(
            "R2",
            "Protection des pushs contre les secrets",
            _enabled(sa.get("secret_scanning_push_protection")),
            "secret_scanning_push_protection",
        )
    )

    status, _ = fetch(f"/repos/{repo}/vulnerability-alerts")
    results.append(Result("R3", "Alertes Dependabot", status == 204, f"HTTP {status}"))

    status, body = fetch(f"/repos/{repo}/automated-security-fixes")
    results.append(
        Result(
            "R4",
            "Correctifs de sécurité Dependabot",
            status == 200 and bool(body and body.get("enabled")),
            f"HTTP {status}",
        )
    )

    status, body = fetch(f"/repos/{repo}/private-vulnerability-reporting")
    results.append(
        Result(
            "R5",
            "Signalement privé des failles",
            status == 200 and bool(body and body.get("enabled")),
            f"HTTP {status}",
        )
    )

    status, body = fetch(f"/repos/{repo}/actions/permissions/workflow")
    perm = (body or {}).get("default_workflow_permissions")
    results.append(
        Result("R6", "Jeton CI en lecture seule par défaut", perm == "read", f"valeur : {perm}")
    )

    merge_ok = (
        info.get("allow_merge_commit") is False and info.get("delete_branch_on_merge") is True
    )
    results.append(
        Result(
            "R7",
            "Fusion par squash, branches supprimées après fusion",
            merge_ok,
            f"merge_commit={info.get('allow_merge_commit')}, "
            f"delete_branch={info.get('delete_branch_on_merge')}",
        )
    )

    status, prot = fetch(f"/repos/{repo}/branches/{branch}/protection")
    if status != 200 or prot is None:
        results.append(Result("R8", f"Branche {branch} protégée", False, f"HTTP {status}"))
        return results

    results.append(
        Result(
            "R8",
            f"Pull request obligatoire sur {branch}",
            prot.get("required_pull_request_reviews") is not None,
        )
    )
    checks = prot.get("required_status_checks") or {}
    contexts = {c.get("context") for c in checks.get("checks", [])} | set(
        checks.get("contexts", [])
    )
    missing = [c for c in REQUIRED_CHECKS if c not in contexts]
    results.append(
        Result(
            "R9",
            "Portes CI obligatoires avant fusion",
            not missing and bool(checks.get("strict")),
            "manquantes : " + ", ".join(missing) if missing else ", ".join(REQUIRED_CHECKS),
        )
    )
    results.append(
        Result(
            "R10",
            "Règles appliquées aussi aux administrateurs",
            bool((prot.get("enforce_admins") or {}).get("enabled")),
        )
    )
    no_force = not (prot.get("allow_force_pushes") or {}).get("enabled", False)
    no_delete = not (prot.get("allow_deletions") or {}).get("enabled", False)
    results.append(
        Result("R11", "Ni force-push ni suppression de la branche", no_force and no_delete)
    )
    results.append(
        Result(
            "R12",
            "Historique linéaire",
            bool((prot.get("required_linear_history") or {}).get("enabled")),
        )
    )
    return results


def resolve_token() -> str | None:
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    gh = shutil.which("gh")
    if gh:
        out = subprocess.run(  # noqa: S603  # nosec B603 - binaire résolu, arguments fixes
            [gh, "auth", "token"], capture_output=True, text=True, check=False
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="OWNER/NOM, par exemple mike/snacki")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--json", action="store_true", help="sortie JSON (pour la CI)")
    args = parser.parse_args(argv)

    token = resolve_token()
    if not token:
        print("Aucun jeton : lancez `gh auth login` ou définissez GH_TOKEN.", file=sys.stderr)
        return 2

    results = run_checks(github_fetch(token), args.repo, args.branch)
    if args.json:
        print(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "OK " if r.ok else "ÉCHEC"
            print(f"[{mark}] {r.id:<4} {r.label}" + (f"  ({r.detail})" if r.detail else ""))
        failed = sum(not r.ok for r in results)
        print(f"\n{len(results) - failed}/{len(results)} contrôles réussis.")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
