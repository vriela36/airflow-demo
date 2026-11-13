#!/usr/bin/env python3
"""Lokalna usługa HTTP. Pierwsze żądanie scenariusza awarii zwraca 503."""

import argparse
import json
import threading
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "poprawne": ROOT / "data/input/orders.csv",
    "awaria_uslugi": ROOT / "data/input/orders.csv",
    "bledna_cena": ROOT / "data/scenarios/orders_invalid.csv",
    "brak_kolumny": ROOT / "data/scenarios/orders_missing_column.csv",
    "brak_zamowien": ROOT / "data/scenarios/orders_empty.csv",
}


def make_handler():
    attempts = defaultdict(int)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, content, content_type="application/json; charset=utf-8"):
            body = content if isinstance(content, bytes) else content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/health":
                self.reply(200, '{"status":"ok"}')
                return
            if url.path != "/orders":
                self.reply(404, '{"error":"Nieznany endpoint"}')
                return
            query = parse_qs(url.query)
            scenario = query.get("scenario", ["poprawne"])[0]
            run_id = query.get("run_id", [""])[0]
            if scenario not in FILES or not run_id:
                self.reply(400, '{"error":"Niepoprawny scenariusz lub brak run_id"}')
                return
            with lock:
                key = (scenario, run_id)
                attempts[key] += 1
                attempt = attempts[key]
            if scenario == "awaria_uslugi" and attempt == 1:
                self.reply(503, '{"error":"Symulowana chwilowa awaria. Następna próba się powiedzie."}')
                return
            try:
                body = FILES[scenario].read_bytes()
            except OSError:
                self.reply(500, '{"error":"Nie można odczytać pliku wejściowego"}')
                return
            self.reply(200, body, "text/csv; charset=utf-8")

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler())
    print(f"Serwis danych: http://127.0.0.1:{args.port}/health", flush=True)
    print("Zostaw to okno otwarte. Zatrzymanie: Ctrl+C.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
