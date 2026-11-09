"""Syntaxe Python et liens Markdown locaux, sans installation ni cache."""
import ast
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
sources = sorted(path for folder in ("dotfilepilot", "tests", "scripts")
                 for path in (root / folder).rglob("*.py"))
for path in sources:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
links = 0
for path in [root / "README.md"] + list((root / "docs").rglob("*.md")):
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("#"):
            continue
        assert (path.parent / target.split("#", 1)[0]).exists(), (path, target)
        links += 1
print(str(len(sources)) + " fichiers Python et " + str(links) + " liens locaux vérifiés.")
