#!/bin/bash
set -eu
DEMO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export AIRFLOW_HOME="$DEMO_ROOT/airflow-home"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
cd "$DEMO_ROOT"
exec "$DEMO_ROOT/.venv/bin/airflow" standalone
