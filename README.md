# Apache Airflow — raport sprzedaży

Projekt demonstracyjny do prezentacji o organizowaniu zadań w Apache Airflow. Pokazuje pobieranie danych z lokalnej usługi HTTP, walidację, rozgałęzienia, ponowienia po błędach i zapis raportów. Działa lokalnie w trybie **standalone**, przeznaczonym do nauki i rozwoju DAG-ów.

## Wymagania i instalacja

Python 3.12, `uv` oraz macOS lub Linux (na Windows: WSL2). Docker nie jest potrzebny.

Po sklonowaniu repozytorium przejdź do jego katalogu:

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.4.0/constraints-3.12.txt"
```

Constraints przypinają wersje zależności przetestowane z Airflow 3.4.0 i Pythonem 3.12. Provider PostgreSQL służy do pokazania konfiguracji połączenia w UI; nie instaluje serwera PostgreSQL i nie jest potrzebny do samego raportu.

## Uruchomienie

Terminal 1 — Airflow:

```bash
bash scripts/start_airflow.sh
```

Terminal 2 — lokalny serwis danych:

```bash
bash scripts/start_service.sh
```

Oba terminale pozostaw otwarte. Otwórz http://localhost:8080. Nazwa użytkownika to `admin`, a hasło jest generowane przy pierwszym uruchomieniu. Można je odczytać lokalnie:

```bash
cat airflow-home/simple_auth_manager_passwords.json.generated
```

Skrypt startowy ustawia `AIRFLOW_HOME` na katalog `airflow-home` w projekcie. Uruchomienie samego `airflow standalone` bez tej zmiennej może użyć innego środowiska w `~/airflow`.

W interfejsie wybierz DAG `raport_sprzedazy`, uruchom go ręcznie i wybierz parametr `scenariusz`. Jeśli DAG jest wstrzymany, wznów go. Serwis musi działać także dla scenariusza `poprawne`.

| Scenariusz | Zachowanie |
| --- | --- |
| `poprawne` | Pobranie danych, walidacja, obliczenia i raport: 1990.00 PLN |
| `awaria_uslugi` | Pierwsze żądanie przebiegu zwraca HTTP 503; Airflow ponawia zadanie |
| `bledna_cena` | Walidacja odrzuca ujemną cenę; `AirflowFailException` wyłącza ponowienia |
| `brak_kolumny` | Brak wymaganej kolumny; dalsze przetwarzanie zostaje zablokowane |
| `brak_zamowien` | Poprawny pusty zbiór; wykonywana jest alternatywna ścieżka |

Przykładowe dane są syntetyczne. Jeden wiersz oznacza jedno zamówienie.

## Zasoby (Assets)

Po sukcesie `zapisz_raport` aktualizuje zasób `Raport sprzedaży` (`x-demo://raport-sprzedazy`). Aktualizacja uruchamia DAG `powiadom_o_raporcie`, który zapisuje komunikat w logach; nie wysyła wiadomości. Ten DAG jest domyślnie aktywny. W zakładce Assets można zobaczyć producenta, odbiorcę i zdarzenia aktualizacji. Samo istnienie zasobu nie wyzwala nowych przebiegów.

## Struktura i pliki wejścia/wyjścia

```text
airflow-home/dags/       definicje DAG-ów
sales_demo/logic.py      walidacja, obliczenia i zapis
scripts/                serwis HTTP i skrypty uruchamiające
data/input/             poprawne dane wejściowe CSV
data/scenarios/         błędne oraz puste dane CSV
data/example-output/    przykładowy raport CSV i JSON
tests/                  testy logiki i usługi HTTP
demo-komendy.md         szczegółowy scenariusz pokazu
```

`pierwszy_dag` pokazuje zależności i harmonogram co 5 minut, `drugi_dag` jest prostym przykładem ręcznym. Pozostaw je wstrzymane, jeśli pokazujesz tylko raport sprzedaży.

Wyniki uruchomień trafiają do `data/output/<scenariusz>/<skrót-run_id>/`. Zobaczysz tam `validation.json`, a dla poprawnego raportu także `summary.json` i `sales_summary.csv`. Ścieżka jest wypisywana w logach `zapisz_raport`. Można też użyć:

```bash
.venv/bin/python scripts/pokaz_wynik.py poprawne
```

Ponowny zapis w tym samym przebiegu zastępuje pliki, a nowy przebieg dostaje osobny katalog. W tym niewielkim demo CSV jest przekazywany przez XCom; dla dużych danych należy użyć zewnętrznego magazynu i przekazywać lokalizację.

## Testy

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Repozytorium nie zawiera środowiska `.venv`, haseł, lokalnej konfiguracji, bazy metadanych ani historii logów. Są tworzone lokalnie podczas uruchamiania. Przykład jest przeznaczony do demonstracji, a nie jako gotowe wdrożenie produkcyjne.
