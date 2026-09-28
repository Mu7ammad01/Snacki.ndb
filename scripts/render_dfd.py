#!/usr/bin/env python3
"""Génère docs/security/dfd.png à partir du modèle de menaces as code (pytm + Graphviz).

python3 scripts/render_dfd.py            # régénère le PNG
python3 scripts/render_dfd.py --check    # échoue si le PNG n'est plus à jour (utile en CI)
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess  # nosec B404 - appels à des binaires fixes, sans shell
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "docs/security/threat_model.py"
PNG = ROOT / "docs/security/dfd.png"
DOT_HASH = ROOT / "docs/security/dfd.dot.sha256"


def dot_source() -> str:
    out = subprocess.run(  # noqa: S603  # nosec B603 - arguments fixes, pas de shell
        [sys.executable, str(MODEL), "--dfd"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    # pytm coupe les longs noms de frontières avec un « \n » littéral : on le remplace.
    return out.replace("\\\\n", " ").replace("\\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="vérifie que le PNG est à jour")
    args = parser.parse_args()

    src = dot_source()
    digest = hashlib.sha256(src.encode()).hexdigest()

    if args.check:
        if not DOT_HASH.exists() or DOT_HASH.read_text().strip() != digest:
            print("DFD obsolète : lancez `python3 scripts/render_dfd.py` et commitez le PNG.")
            return 1
        print("DFD à jour.")
        return 0

    dot = shutil.which("dot")
    if dot is None:
        print("Graphviz (dot) est requis : apt install graphviz / brew install graphviz")
        return 2
    subprocess.run(  # noqa: S603  # nosec B603 - binaire résolu, arguments fixes
        [dot, "-Tpng", "-Gdpi=110", "-o", str(PNG)], input=src, text=True, check=True
    )
    DOT_HASH.write_text(digest + "\n")
    print(f"Écrit : {PNG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
