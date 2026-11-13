import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from sales_demo.logic import ROOT, DataError, calculate, read_csv, validate, write_report
from scripts.serwis_danych import make_handler


class LogicTests(unittest.TestCase):
    def test_correct_total_and_product_aggregation(self):
        rows = validate(read_csv((ROOT / 'data/input/orders.csv').read_text()))
        result = calculate(rows)
        self.assertEqual(result['laczna_sprzedaz'], '1990.00')
        self.assertEqual(result['liczba_zamowien'], 5)
        keyboard = next(p for p in result['produkty'] if p['product'] == 'Klawiatura')
        self.assertEqual(keyboard, {'product': 'Klawiatura', 'quantity': 3, 'sales': '450.00'})

    def test_invalid_price(self):
        with self.assertRaisesRegex(DataError, 'Wiersz 6: cena'):
            validate(read_csv((ROOT / 'data/scenarios/orders_invalid.csv').read_text()))

    def test_missing_column(self):
        with self.assertRaisesRegex(DataError, 'quantity'):
            validate(read_csv((ROOT / 'data/scenarios/orders_missing_column.csv').read_text()))

    def test_empty_is_valid(self):
        self.assertEqual(validate(read_csv((ROOT / 'data/scenarios/orders_empty.csv').read_text())), [])

    def test_nonfinite_and_duplicate_ids_rejected(self):
        header = 'order_id,product,quantity,unit_price\n'
        for value in ('NaN', 'Infinity', '-Infinity', '0', '0.001'):
            with self.subTest(value=value), self.assertRaises(DataError):
                validate(read_csv(header + f'1,Mysz,1,{value}\n'))
        with self.assertRaisesRegex(DataError, 'powtórzony'):
            validate(read_csv(header + '1,Mysz,1,1.00\n1,Mysz,2,1.00\n'))

    def test_rerun_replaces_report_and_runs_are_separate(self):
        summary = calculate(validate(read_csv((ROOT / 'data/input/orders.csv').read_text())))
        with tempfile.TemporaryDirectory() as root:
            first = Path(write_report(summary, 'run-one', 'poprawne', root))
            before = (first / 'sales_summary.csv').read_bytes()
            self.assertEqual(write_report(summary, 'run-one', 'poprawne', root), str(first))
            self.assertEqual((first / 'sales_summary.csv').read_bytes(), before)
            self.assertEqual(json.loads((first / 'summary.json').read_text())['laczna_sprzedaz'], '1990.00')
            self.assertNotEqual(write_report(summary, 'run-two', 'poprawne', root), str(first))


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def get(self, query):
        with urlopen(self.base + query, timeout=3) as response:
            return response.read().decode()

    def test_retry_per_run(self):
        for run_id in ('a', 'b'):
            path = f'/orders?scenario=awaria_uslugi&run_id={run_id}'
            with self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertEqual(error.exception.code, 503)
            self.assertEqual(calculate(validate(read_csv(self.get(path))))['laczna_sprzedaz'], '1990.00')

    def test_empty_and_invalid_delivered_over_http(self):
        self.assertEqual(validate(read_csv(self.get('/orders?scenario=brak_zamowien&run_id=x'))), [])
        with self.assertRaises(DataError):
            validate(read_csv(self.get('/orders?scenario=bledna_cena&run_id=x')))
        with self.assertRaises(DataError):
            validate(read_csv(self.get('/orders?scenario=brak_kolumny&run_id=x')))

    def test_health_and_bad_scenario(self):
        self.assertEqual(json.loads(self.get('/health')), {'status': 'ok'})
        with self.assertRaises(HTTPError) as error:
            self.get('/orders?scenario=unknown&run_id=x')
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
