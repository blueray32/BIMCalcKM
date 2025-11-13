# BIMCalc

A production-grade scaffold for BIMCalc — an automated BIM → cost engine with:
- Classification-first blocking
- Canonical “mapping memory” keys
- Business risk flags + UI enforcement
- SCD Type-2 mapping history

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
bimcalc --help

# Run browser-based review UI locally
bimcalc web serve --host 0.0.0.0 --port 8001
```

## Docker

You can run BIMCalc (CLI + review UI) entirely inside Docker. The provided `docker-compose.yml` spins up Postgres and an interactive app container.

```bash
# Build the image
docker compose build

# Start Postgres
docker compose up -d db

# Initialize schema
docker compose run --rm app bimcalc init

# Run matches / review UI (replace arguments as needed)
docker compose run --rm app bimcalc ingest-schedules examples/schedules/project_a.csv --project project-a
docker compose run --rm app bimcalc match --project project-a

# Launch the Textual review UI (requires an interactive terminal)
docker compose run --rm app "bimcalc review ui --project project-a --user demo@acme"

# Serve the browser UI (exposes http://localhost:8001)
docker compose up app
```

Tips:

- The app service starts with `command: bash` so you can drop into a shell via `docker compose run --rm app bash` for ad-hoc workflows.
- Environment variables (e.g., `DATABASE_URL`, `DEFAULT_ORG_ID`) are defined in `docker-compose.yml`. Override them per run with `-e` or by editing the compose file.
- Because Textual requires a TTY, keep the entire command in quotes so the container receives it intact.
- The web UI is available at `http://localhost:8001` once the `app` service is running; approve actions immediately write mappings + audit rows.
