#!/bin/bash
set -eu
DEMO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DEMO_ROOT"
exec "$DEMO_ROOT/.venv/bin/python" scripts/serwis_danych.py
