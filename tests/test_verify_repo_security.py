"""Tests du vérificateur de réglages GitHub, avec de fausses réponses de l'API."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify_repo_security as v  # noqa: E402

REPO = "mike/snacki"

GOOD = {
    f"/repos/{REPO}": (
        200,
        {
            "allow_merge_commit": False,
            "delete_branch_on_merge": True,
            "security_and_analysis": {
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "enabled"},
            },
        },
    ),
    f"/repos/{REPO}/vulnerability-alerts": (204, None),
    f"/repos/{REPO}/automated-security-fixes": (200, {"enabled": True, "paused": False}),
    f"/repos/{REPO}/private-vulnerability-reporting": (200, {"enabled": True}),
    f"/repos/{REPO}/actions/permissions/workflow": (
        200,
        {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False},
    ),
    f"/repos/{REPO}/branches/main/protection": (
        200,
        {
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_status_checks": {
                "strict": True,
                "checks": [{"context": "secrets"}, {"context": "quality"}, {"context": "tests"}],
            },
            "enforce_admins": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "required_linear_history": {"enabled": True},
        },
    ),
}


def fake(responses):
    def fetch(path):
        return responses.get(path, (404, {"message": "Not Found"}))

    return fetch


def by_id(results):
    return {r.id: r for r in results}


def test_tout_est_en_place():
    results = v.run_checks(fake(GOOD), REPO)
    assert len(results) == 12
    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_depot_inaccessible():
    results = v.run_checks(fake({}), REPO)
    assert [r.id for r in results] == ["R0"]
    assert not results[0].ok


def test_branche_non_protegee():
    responses = copy.deepcopy(GOOD)
    responses[f"/repos/{REPO}/branches/main/protection"] = (
        404,
        {"message": "Branch not protected"},
    )
    r = by_id(v.run_checks(fake(responses), REPO))
    assert not r["R8"].ok
    assert "R9" not in r


@pytest.mark.parametrize(
    ("chemin", "reponse", "controle"),
    [
        (f"/repos/{REPO}/vulnerability-alerts", (404, None), "R3"),
        (f"/repos/{REPO}/automated-security-fixes", (200, {"enabled": False}), "R4"),
        (f"/repos/{REPO}/private-vulnerability-reporting", (200, {"enabled": False}), "R5"),
        (
            f"/repos/{REPO}/actions/permissions/workflow",
            (200, {"default_workflow_permissions": "write"}),
            "R6",
        ),
    ],
)
def test_reglage_desactive(chemin, reponse, controle):
    responses = copy.deepcopy(GOOD)
    responses[chemin] = reponse
    r = by_id(v.run_checks(fake(responses), REPO))
    assert not r[controle].ok
    assert sum(not x.ok for x in r.values()) == 1


def test_push_protection_desactivee():
    responses = copy.deepcopy(GOOD)
    responses[f"/repos/{REPO}"][1]["security_and_analysis"]["secret_scanning_push_protection"] = {
        "status": "disabled"
    }
    r = by_id(v.run_checks(fake(responses), REPO))
    assert r["R1"].ok and not r["R2"].ok


def test_porte_ci_manquante_et_force_push():
    responses = copy.deepcopy(GOOD)
    prot = responses[f"/repos/{REPO}/branches/main/protection"][1]
    prot["required_status_checks"]["checks"] = [{"context": "secrets"}]
    prot["allow_force_pushes"] = {"enabled": True}
    r = by_id(v.run_checks(fake(responses), REPO))
    assert not r["R9"].ok and "quality" in r["R9"].detail and "tests" in r["R9"].detail
    assert not r["R11"].ok


def test_ancien_format_contexts_accepte():
    responses = copy.deepcopy(GOOD)
    prot = responses[f"/repos/{REPO}/branches/main/protection"][1]
    prot["required_status_checks"] = {"strict": True, "contexts": ["secrets", "quality", "tests"]}
    assert by_id(v.run_checks(fake(responses), REPO))["R9"].ok


def test_sans_jeton(monkeypatch, capsys):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(v.shutil, "which", lambda _: None)
    assert v.main(["--repo", REPO]) == 2
    assert "gh auth login" in capsys.readouterr().err
