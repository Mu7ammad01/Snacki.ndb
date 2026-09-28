"""Tests de la liste ASVS : chaque exigence de niveau 1 doit avoir une décision justifiée."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import asvs_checklist as a  # noqa: E402


def load():
    return a.load_level1(), json.loads(a.MAPPING.read_text(encoding="utf-8"))


def test_asvs_5_niveau_1_compte_70_exigences():
    level1, _ = load()
    assert len(level1) == 70


def test_mapping_complet_et_valide():
    level1, mapping = load()
    assert a.validate(level1, mapping) == []


def test_exigence_oubliee_detectee():
    level1, mapping = load()
    del mapping["V8.2.2"]
    assert any("V8.2.2" in e for e in a.validate(level1, mapping))


def test_na_sans_raison_refuse():
    level1, mapping = load()
    mapping["V4.4.1"] = {"statut": "N/A"}
    assert "V4.4.1 : N/A sans raison" in a.validate(level1, mapping)


def test_fait_sans_preuve_refuse():
    level1, mapping = load()
    mapping["V15.1.1"].pop("preuve")
    assert "V15.1.1 : « fait » sans preuve" in a.validate(level1, mapping)


def test_identifiant_inconnu_refuse():
    level1, mapping = load()
    mapping["V99.1.1"] = {"statut": "N/A", "raison": "test"}
    assert any("V99.1.1" in e for e in a.validate(level1, mapping))


def test_tableau_genere_a_jour():
    level1, mapping = load()
    assert a.OUTPUT.read_text(encoding="utf-8") == a.render(level1, mapping)
