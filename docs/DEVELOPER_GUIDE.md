# BIMCalc Developer Guide

This guide covers the setup, development, and testing workflows for BIMCalc.

## Prerequisites
- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 15+ (if running locally without Docker)
- Redis 7+ (if running locally without Docker)

## Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/bimcalc.git
   cd bimcalc
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Copy `.env.example` to `.env` and configure your local settings.
   ```bash
   cp .env.example .env
   ```

5. **Run the application**:
   ```bash
   uvicorn bimcalc.web.app_enhanced:app --reload
   ```

## Docker Setup

Run the full stack (App, Worker, DB, Redis) using Docker Compose:
```bash
docker compose up --build
```

## Testing

Run the test suite using `pytest`:
```bash
pytest
```

## Project Structure
- `bimcalc/core`: Core logic (logging, config, embeddings).
- `bimcalc/db`: Database models and connection logic.
- `bimcalc/web`: FastAPI web application (routes, templates).
- `bimcalc/ingestion`: Data ingestion logic (Revit, Price Books).
- `bimcalc/matching`: Core matching engine.
- `bimcalc/intelligence`: AI features (Price Trend, Smart Matching).

## Contributing
1. Create a feature branch (`feature/my-feature`).
2. Commit your changes with clear messages.
3. Open a Pull Request for review.
