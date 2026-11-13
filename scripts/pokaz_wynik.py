"""Pokaż najnowszy wynik wybranego scenariusza, bez szukania katalogu przebiegu."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("scenariusz")
args = parser.parse_args()
candidates = list((root / "data/output" / args.scenariusz).glob("*/validation.json"))
if not candidates:
    parser.exit(1, "Nie ma jeszcze wyniku walidacji tego scenariusza.\n")
folder = max(candidates, key=lambda p: p.stat().st_mtime).parent
print(f"Katalog: {folder}")
for name in ("validation.json", "summary.json", "sales_summary.csv"):
    file = folder / name
    if file.exists():
        print(f"\n{name}:\n{file.read_text(encoding='utf-8')}")
