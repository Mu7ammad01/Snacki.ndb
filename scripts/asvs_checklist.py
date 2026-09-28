#!/usr/bin/env python3
"""Liste de contrôle OWASP ASVS 5.0 niveau 1 pour Snacki.

Croise le texte officiel de l'ASVS (docs/security/asvs/asvs-5.0.0-en.flat.json)
avec les décisions de Snacki (docs/security/asvs/mapping-l1.json) et écrit
docs/security/asvs-l1.md.

    python3 scripts/asvs_checklist.py           # régénère le tableau
    python3 scripts/asvs_checklist.py --check   # échoue si une exigence manque ou tableau périmé
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASVS = ROOT / "docs/security/asvs/asvs-5.0.0-en.flat.json"
MAPPING = ROOT / "docs/security/asvs/mapping-l1.json"
OUTPUT = ROOT / "docs/security/asvs-l1.md"

STATUTS = ("fait", "prévu", "à vérifier", "N/A")
JOURS = {f"J{i}" for i in range(1, 16)}


def load_level1(path: Path = ASVS) -> list[dict]:
    reqs = json.loads(path.read_text(encoding="utf-8"))["requirements"]
    return [r for r in reqs if str(r["L"]) == "1"]


def validate(level1: list[dict], mapping: dict) -> list[str]:
    """Retourne la liste des problèmes (vide si tout est correct)."""
    errors: list[str] = []
    ids = {r["req_id"] for r in level1}
    entries = {k: v for k, v in mapping.items() if not k.startswith("_")}

    for missing in sorted(ids - entries.keys(), key=_sort_key):
        errors.append(f"{missing} : exigence de niveau 1 sans décision")
    for extra in sorted(entries.keys() - ids, key=_sort_key):
        errors.append(f"{extra} : identifiant inconnu au niveau 1 de l'ASVS 5.0")

    for req_id, e in entries.items():
        statut = e.get("statut")
        if statut not in STATUTS:
            errors.append(f"{req_id} : statut « {statut} » invalide")
            continue
        if statut == "N/A":
            if not e.get("raison"):
                errors.append(f"{req_id} : N/A sans raison")
            continue
        if e.get("jour") not in JOURS:
            errors.append(f"{req_id} : jour manquant ou invalide")
        if not e.get("controle"):
            errors.append(f"{req_id} : contrôle manquant")
        if statut == "fait" and not e.get("preuve"):
            errors.append(f"{req_id} : « fait » sans preuve")
    return errors


def _sort_key(req_id: str) -> tuple[int, ...]:
    return tuple(int(p) for p in req_id.lstrip("V").split("."))


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + " …"


def render(level1: list[dict], mapping: dict) -> str:
    counts = Counter(mapping[r["req_id"]]["statut"] for r in level1)
    lines = [
        "# OWASP ASVS 5.0 niveau 1 : suivi pour Snacki",
        "",
        "Fichier généré par `scripts/asvs_checklist.py` à partir de "
        "`docs/security/asvs/mapping-l1.json` : ne pas modifier à la main.",
        "",
        f"**{len(level1)} exigences** : "
        + " · ".join(f"{counts.get(s, 0)} {s}" for s in STATUTS)
        + ".",
        "",
        "Texte des exigences : OWASP ASVS 5.0.0 (CC BY-SA 4.0), en anglais comme l'original.",
        "",
    ]
    chapter = None
    for r in sorted(level1, key=lambda r: _sort_key(r["req_id"])):
        if r["chapter_id"] != chapter:
            chapter = r["chapter_id"]
            lines += [
                "",
                f"## {chapter} · {r['chapter_name']}",
                "",
                "| ID | Exigence | Statut | Jour | Contrôle ou raison |",
                "| --- | --- | --- | --- | --- |",
            ]
        e = mapping[r["req_id"]]
        detail = e.get("raison") if e["statut"] == "N/A" else e["controle"]
        if e.get("preuve"):
            detail += f" Preuve : `{e['preuve']}`."
        detail = detail.replace("|", "\\|")
        lines.append(
            f"| {r['req_id']} | {_short(r['req_description'])} | {e['statut']} "
            f"| {e.get('jour', '')} | {detail} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    level1 = load_level1()
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    errors = validate(level1, mapping)
    if errors:
        print("Liste ASVS incomplète :")
        print("\n".join(f"  - {e}" for e in errors))
        return 1

    content = render(level1, mapping)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print(
                "docs/security/asvs-l1.md est périmé : lancez `python3 scripts/asvs_checklist.py`."
            )
            return 1
        print(f"ASVS niveau 1 : {len(level1)} exigences suivies, tableau à jour.")
        return 0

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Écrit : {OUTPUT.relative_to(ROOT)} ({len(level1)} exigences)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
