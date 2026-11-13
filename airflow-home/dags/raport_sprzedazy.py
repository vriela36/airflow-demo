"""Demo Airflow: raport sprzedaży i reakcje na różne przyczyny problemów."""

import logging
import sys
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from airflow.sdk.exceptions import AirflowFailException
from airflow.sdk import Asset, Param, dag, get_current_context, task

# Projekt działa lokalnie w standalone. Moduł nie wymaga instalacji jako pakiet.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sales_demo.logic import (
    SCENARIOS, DataError, calculate, read_csv, run_directory,
    validate, write_json, write_report,
)

logger = logging.getLogger(__name__)

raport_asset = Asset(
    uri="x-demo://raport-sprzedazy",
    name="Raport sprzedaży",
)


@dag(
    dag_id="raport_sprzedazy",
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "Gabriela"},
    tags=["demo", "sprzedaz"],
    params={
        "scenariusz": Param(
            "poprawne", type="string", enum=list(SCENARIOS),
            title="Scenariusz demonstracji",
            description="Wybierz wariant bez zmieniania kodu ani plików.",
        ),
    },
    doc_md="""
    ## Raport sprzedaży
    Uruchom lokalny serwis `scripts/serwis_danych.py`, następnie wybierz scenariusz.
    **poprawne**: raport 1990.00 PLN; **awaria_uslugi**: HTTP 503 i ponowienie;
    **bledna_cena / brak_kolumny**: błąd walidacji bez ponowień;
    **brak_zamowien**: alternatywna ścieżka i pominięcie obliczeń.
    Wyniki: `data/output/<scenariusz>/<identyfikator-przebiegu>/`.
    Szczegółowy scenariusz pokazu znajduje się w `demo-komendy.md`.
    """,
)
def raport_sprzedazy():

    @task(retries=2, retry_delay=timedelta(seconds=10))
    def wczytaj_zamowienia():
        """Błąd transportu może ustąpić: Airflow ponowi tylko ten etap."""
        context = get_current_context()
        scenario = context["params"]["scenariusz"]
        query = urlencode({"scenario": scenario, "run_id": context["run_id"]})
        url = f"http://127.0.0.1:8765/orders?{query}"
        logger.info("Scenariusz: %s. Pobieram dane z lokalnego serwisu.", scenario)
        try:
            with urlopen(url, timeout=5) as response:
                raw = response.read().decode("utf-8-sig")
        except HTTPError as error:
            if error.code in {429, 500, 502, 503, 504}:
                logger.warning("BŁĄD PRZEJŚCIOWY: HTTP %s. Airflow może ponowić zadanie.", error.code)
                raise RuntimeError(f"Serwis chwilowo niedostępny: HTTP {error.code}") from None
            raise AirflowFailException(f"Żądanie odrzucone: HTTP {error.code}. Sprawdź konfigurację.") from None
        except (URLError, TimeoutError) as error:
            logger.warning("BŁĄD POŁĄCZENIA: sprawdź, czy serwis na porcie 8765 działa.")
            raise RuntimeError(f"Nie udało się połączyć z serwisem: {error}") from None
        except UnicodeError:
            raise AirflowFailException("Odpowiedź serwisu nie jest tekstem UTF-8.") from None
        logger.info("Odebrano CSV (%s znaków).", len(raw))
        return raw

    @task(retries=2, retry_delay=timedelta(seconds=10))
    def sprawdz_dane(raw):
        """Nawet przy retries=2 błąd danych omija pozostałe próby."""
        context = get_current_context()
        directory = run_directory(context["run_id"], context["params"]["scenariusz"])
        try:
            rows = validate(read_csv(raw))
        except DataError as error:
            message = str(error)
            write_json(directory / "validation.json", {"status": "blad", "komunikat": message})
            logger.error("BŁĄD DANYCH: %s", message)
            raise AirflowFailException(message) from None
        write_json(directory / "validation.json", {"status": "poprawne", "liczba_zamowien": len(rows)})
        logger.info("Dane przeszły walidację. Liczba zamówień: %s.", len(rows))
        return rows

    @task.branch
    def wybierz_sciezke(rows):
        selected = "oblicz_sprzedaz" if rows else "brak_zamowien"
        logger.info("Wybrana ścieżka: %s", selected)
        return selected

    @task
    def oblicz_sprzedaz(rows):
        summary = calculate(rows)
        logger.info("ŁĄCZNA SPRZEDAŻ: %s PLN", summary["laczna_sprzedaz"])
        return summary

    @task(outlets=[raport_asset])
    def zapisz_raport(summary):
        context = get_current_context()
        directory = write_report(summary, context["run_id"], context["params"]["scenariusz"])
        logger.info("RAPORT GOTOWY: %s", directory)
        return directory

    @task
    def brak_zamowien():
        context = get_current_context()
        directory = run_directory(context["run_id"], context["params"]["scenariusz"])
        write_json(directory / "summary.json", {
            "status": "brak_zamowien", "run_id": context["run_id"],
            "komunikat": "Brak zamówień. To poprawny wynik, nie awaria.",
            "liczba_zamowien": 0, "laczna_sprzedaz": "0.00", "waluta": "PLN",
        })
        logger.info("BRAK ZAMÓWIEŃ: zapisano informację w %s", directory)

    @task(trigger_rule="none_failed_min_one_success")
    def zakoncz():
        logger.info("Proces zakończony. Jedna z dwóch ścieżek wykonała się poprawnie.")

    raw = wczytaj_zamowienia()
    rows = sprawdz_dane(raw)
    branch = wybierz_sciezke(rows)
    calculated = oblicz_sprzedaz(rows)
    report = zapisz_raport(calculated)
    empty = brak_zamowien()
    end = zakoncz()

    branch >> [calculated, empty]
    [report, empty] >> end


raport_sprzedazy()
