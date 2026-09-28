"""Le schéma de flux commité doit correspondre au modèle de menaces as code."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import render_dfd as r  # noqa: E402


def test_dfd_a_jour():
    digest = hashlib.sha256(r.dot_source().encode()).hexdigest()
    assert r.DOT_HASH.read_text().strip() == digest, "lancez scripts/render_dfd.py"


def test_dfd_couvre_les_frontieres_et_services():
    src = r.dot_source()
    for element in (
        "Internet",
        "Google Cloud Run",
        "Services tiers",
        "API Gemini",
        "Secret Manager",
    ):
        assert element in src
