# Pokaz: raport sprzedaży w Apache Airflow

Demo działa w Airflow standalone 3.4.0, poza prezentacją. Nie potrzebuje Dockera ani Colimy.

## Uruchomienie (przed wystąpieniem)

Jeżeli Airflow już działa, nie uruchamiaj drugiej instancji. Możesz pozostawić obecne okno, jeżeli scheduler działa.

Terminal 1, przy kolejnym starcie środowiska:

```bash
cd ~/Documents/airflow-demo
bash scripts/start_airflow.sh
```

Ten skrypt ustawia AIRFLOW_HOME i wyłącza ładowanie przykładów. Zostaw terminal otwarty.

Terminal 2 — serwis danych:

```bash
cd ~/Documents/airflow-demo
bash scripts/start_service.sh
```

Powinien wypisać adres `http://127.0.0.1:8765/health`. Pozostaw go uruchomionego.
Jeśli port jest zajęty, sprawdź, czy już masz otwarte okno z tym serwisem. Nie uruchamiaj go dwukrotnie.

Terminal 3 — sprawdzenie usługi i wyświetlanie wyników:

```bash
cd ~/Documents/airflow-demo
curl http://127.0.0.1:8765/health
```

Oczekiwane: `{"status":"ok"}`. Strona Airflow: http://localhost:8080.
Przy problemie z queued sprawdź scheduler w aktywnym .venv i z poprawnym AIRFLOW_HOME:

```bash
source .venv/bin/activate
export AIRFLOW_HOME="$PWD/airflow-home"
airflow jobs check --job-type SchedulerJob
```

## Graf

```text
wczytaj_zamowienia (HTTP)
        |
sprawdz_dane
        |
wybierz_sciezke
        |-----------------------|
oblicz_sprzedaz            brak_zamowien
        |                       |
zapisz_raport                    |
        |-----------------------|
                    zakoncz
```

Walidacja przekazuje dane także do obliczeń. Graf w UI pokaże również tę zależność.
`max_active_runs=1` oznacza jeden aktywny przebieg. Twórz kolejny dopiero po zakończeniu poprzedniego.

## Wybór scenariusza

Otwórz DAG `raport_sprzedazy`, kliknij „Uruchom” i wybierz pole `scenariusz` w formularzu parametrów.
Jeśli interfejs pokazuje konfigurację JSON, użyj np. `{"scenariusz":"awaria_uslugi"}`.
Jeśli DAG jest wstrzymany, wybierz wznowienie. Poczekaj na odczytanie nowej wersji pliku przed pierwszym pokazem.

### A. Poprawny proces

Scenariusz: `poprawne`.

Pokaż odczyt, walidację, obliczenia i zapis. `brak_zamowien` będzie skipped — to celowe.
Wynik: 5 zamówień (w tym demo jeden wiersz oznacza jedno zamówienie), 9 sztuk, 1990.00 PLN.

```bash
.venv/bin/python scripts/pokaz_wynik.py poprawne
```

Pokaż `sales_summary.csv` oraz `summary.json`.

### B. Chwilowa awaria (około 2 minuty)

Scenariusz: `awaria_uslugi`.

Serwis celowo zwraca HTTP 503 przy pierwszym żądaniu każdego nowego przebiegu, a następne obsługuje poprawnie.
Pokaż log pobierania, stan `up_for_retry`, przerwę minimum 10 sekund i drugą próbę.
Scheduler może dołożyć kilka sekund oczekiwania. Zadanie ma dwa ponowienia, czyli do trzech prób łącznie.
Na końcu suma wynosi 1990.00 PLN.

```bash
.venv/bin/python scripts/pokaz_wynik.py awaria_uslugi
```

Nie trzeba resetować serwisu między nowymi przebiegami. Kluczem jest ich run_id.
Stan symulacji jest w pamięci: restart serwisu w trakcie ponowień uruchomi symulację ponownie.
Jeśli wyłączysz serwis całkowicie, próby także zakończą się błędem, aż wyczerpie się limit.

### C. Błąd danych (około 2 minuty)

Scenariusz `bledna_cena`: ostatni rekord ma ujemną cenę.
Alternatywnie `brak_kolumny`: nagłówek nie ma quantity.

Odczyt HTTP zakończy się sukcesem. Walidacja wypisze `BŁĄD DANYCH` i zakończy się jako failed.
Pomimo `retries=2` AirflowFailException nie pozwala na ponowienia tego błędu.
Pozostałe etapy nie utworzą raportu. Zobacz krótki, nietechniczny wynik:

```bash
.venv/bin/python scripts/pokaz_wynik.py bledna_cena
```

`validation.json` ma status blad i komunikat. Stos wyjątku nadal zostaje w logach Airflow.
Do powrotu na poprawne dane uruchom NOWY przebieg z parametrem poprawne. Nie trzeba edytować CSV w trakcie wystąpienia.

### D. Brak zamówień (około 1,5 minuty)

Scenariusz: `brak_zamowien`.

Plik zawiera poprawny nagłówek i zero rekordów. Walidacja się udaje. Branch wybiera brak_zamowien.
Obliczenia i raport CSV mają skipped. Zadanie zakoncz ma regułę none_failed_min_one_success,
więc dopuszczalne pominięcie jednej gałęzi nie blokuje końca, ale błąd wymaganej gałęzi go blokuje.

```bash
.venv/bin/python scripts/pokaz_wynik.py brak_zamowien
```

JSON wyraźnie mówi o braku zamówień. To przyjęta reguła biznesowa demo — w innym systemie pusty zbiór może być błędem.

## Zapis i bezpieczeństwo ponowień

Każdy przebieg ma osobny katalog: `data/output/<scenariusz>/<skrót-run_id>/`.
Ponowne wykonanie zapisu w TYM SAMYM przebiegu zastępuje pliki zamiast dopisywać duplikaty.
Nowy przebieg dostaje osobny katalog, więc wyniki różnych scenariuszy nie mieszają się.
Pliki są zastępowane atomowo pojedynczo, a summary.json publikowany ostatni. Nie jest to transakcja całego katalogu.
Odbiorca raportu powinien czytać CSV po pojawieniu się summary.json. Demo nie gwarantuje exactly-once dla dowolnych systemów.
Duży zbiór danych powinien być w magazynie danych, nie w XCom. Tutaj przekazujemy tylko kilka rekordów.

## Pliki

- `airflow-home/dags/raport_sprzedazy.py`: DAG, retry, branch i zależności.
- `sales_demo/logic.py`: walidacja, obliczenia Decimal i zapis.
- `scripts/serwis_danych.py`: lokalne źródło HTTP z symulacją.
- `data/input/orders.csv`: poprawne wejście.
- `data/scenarios/`: trzy warianty danych.
- `backups/`: poprzedni kod i plik wejściowy (z ujemną ceną).

## Testy logiki i usługi

```bash
.venv/bin/python -m unittest discover -s tests -v
```
