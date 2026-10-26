"""
Garde-fou : la documentation du depot ne doit pas affirmer de garanties non mesurees.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = [
    "certifié à 100% sans hallucination",
    "certifiée à 100% sans hallucination",
    "Certifié 100% Faithfulness",
    "0.95 - 1.00",
    "0,95 à 1,00",
]


def test_tracked_docs_do_not_claim_unmeasured_faithfulness():
    files = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    for name in files:
        if name.startswith("eval/"):  # le rapport cite ces formulations pour les contester
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        for phrase in FORBIDDEN:
            assert phrase not in text, f"{name} contient : {phrase}"
