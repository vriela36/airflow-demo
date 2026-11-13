"""Walidacja, dokładne obliczenia i zapis raportów dla niewielkiego CSV."""

import csv
import hashlib
import io
import json
import os
import tempfile
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("poprawne", "awaria_uslugi", "bledna_cena", "brak_kolumny", "brak_zamowien")


class DataError(ValueError):
    """Błąd wejścia, którego nie naprawi powtórzenie tej samej walidacji."""


def read_csv(text):
    reader = csv.DictReader(io.StringIO(text, newline=""))
    try:
        rows = list(reader)
    except csv.Error as error:
        raise DataError(f"Nie można odczytać CSV: {error}") from None
    return {"kolumny": reader.fieldnames or [], "zamowienia": rows}


def validate(data):
    required = {"order_id", "product", "quantity", "unit_price"}
    columns = data["kolumny"]
    missing = required - set(columns)
    if missing:
        raise DataError(f"Brak wymaganych kolumn: {', '.join(sorted(missing))}.")
    if len(columns) != len(set(columns)):
        raise DataError("Nagłówek CSV zawiera powtórzone kolumny.")
    seen = set()
    for number, row in enumerate(data["zamowienia"], start=2):
        if None in row or any(value is None for value in row.values()):
            raise DataError(f"Wiersz {number}: niewłaściwa liczba pól.")
        if not row["order_id"].strip() or not row["product"].strip():
            raise DataError(f"Wiersz {number}: pusty identyfikator lub produkt.")
        order_id = row["order_id"].strip()
        if order_id in seen:
            raise DataError(f"Wiersz {number}: powtórzony order_id {order_id}.")
        seen.add(order_id)
        try:
            quantity = int(row["quantity"])
            price = Decimal(row["unit_price"])
        except (ValueError, TypeError, InvalidOperation):
            raise DataError(f"Wiersz {number}: niepoprawna ilość lub cena.") from None
        if quantity <= 0:
            raise DataError(f"Wiersz {number}: ilość musi być dodatnia.")
        if not price.is_finite() or price <= 0:
            raise DataError(f"Wiersz {number}: cena musi być dodatnią, skończoną liczbą.")
        if price != price.quantize(Decimal("0.01")):
            raise DataError(f"Wiersz {number}: cena może mieć najwyżej dwa miejsca po przecinku.")
    return data["zamowienia"]


def calculate(rows):
    total = Decimal("0.00")
    products = defaultdict(lambda: {"quantity": 0, "sales": Decimal("0.00")})
    for row in rows:
        value = int(row["quantity"]) * Decimal(row["unit_price"])
        total += value
        product = products[row["product"]]
        product["quantity"] += int(row["quantity"])
        product["sales"] += value
    return {
        "liczba_zamowien": len(rows),
        "laczna_sprzedaz": f"{total:.2f}",
        "waluta": "PLN",
        "produkty": [
            {"product": name, "quantity": value["quantity"], "sales": f"{value['sales']:.2f}"}
            for name, value in sorted(products.items())
        ],
    }


def run_directory(run_id, scenario, root=ROOT):
    if scenario not in SCENARIOS:
        raise ValueError("Nieznany scenariusz")
    # Ten sam przebieg zapisuje zawsze w tym samym katalogu. Nazwa nie jest ścieżką od użytkownika.
    digest = hashlib.sha256(run_id.encode()).hexdigest()[:16]
    target = Path(root) / "data/output" / scenario / digest
    target.mkdir(parents=True, exist_ok=True)
    return target


def atomic_write(path, text):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = file.name
        file.write(text)
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_report(summary, run_id, scenario, root=ROOT):
    target = run_directory(run_id, scenario, root)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["product", "quantity", "sales"])
    writer.writeheader()
    writer.writerows(summary["produkty"])
    atomic_write(target / "sales_summary.csv", buffer.getvalue())
    # JSON publikujemy ostatni: odbiorca ma wówczas również gotowy CSV.
    write_json(target / "summary.json", {"status": "gotowy", "run_id": run_id, "scenariusz": scenario, **summary})
    return str(target)
