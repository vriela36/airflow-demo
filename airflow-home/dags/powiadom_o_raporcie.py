"""Drugi DAG: uruchomienie po aktualizacji zasobu raportu sprzedaży."""

import logging

from airflow.sdk import Asset, dag, task


# To samo URI co w raport_sprzedazy.py oznacza ten sam zasób.
raport_asset = Asset(
    uri="x-demo://raport-sprzedazy",
    name="Raport sprzedaży",
)


@dag(
    dag_id="powiadom_o_raporcie",
    schedule=[raport_asset],
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    default_args={"owner": "Gabriela"},
    tags=["demo", "sprzedaz", "assets"],
    doc_md="""
    ## Reakcja na gotowy raport
    Ten DAG nie ma harmonogramu czasowego. Uruchamia go aktualizacja zasobu
    **Raport sprzedaży**, emitowana po sukcesie zadania `zapisz_raport`
    w DAG-u `raport_sprzedazy`.
    Zadanie tylko zapisuje komunikat w logach — nie wysyła wiadomości.
    Samo istnienie zasobu nie oznacza nowego zdarzenia aktualizacji.
    """,
)
def powiadom_o_raporcie():
    @task
    def pokaz_powiadomienie():
        logging.getLogger(__name__).info(
            "RAPORT GOTOWY: zasób Raport sprzedaży został zaktualizowany. "
            "Ten DAG uruchomił się w reakcji na gotowość danych, a nie o zadanej godzinie."
        )

    pokaz_powiadomienie()


powiadom_o_raporcie()
