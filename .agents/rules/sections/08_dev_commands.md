# Development Commands

## Local Development

### Setup

```bash
# Clone repository
git clone <repo-url>
cd BIMCalcKM

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration
```

### Database

```bash
# Start PostgreSQL (via Docker)
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Add new table"

# Rollback migration
alembic downgrade -1

# Reset database (DESTRUCTIVE)
alembic downgrade base
alembic upgrade head
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bimcalc --cov-report=html

# Run specific test file
pytest tests/unit/test_classifier.py

# Run specific test
pytest tests/unit/test_classifier.py::test_classification_trust_hierarchy

# Run integration tests only
pytest tests/integration -m integration

# Watch mode (requires pytest-watch)
ptw
```

### Code Quality

```bash
# Format code
black bimcalc tests

# Lint
ruff check --fix bimcalc tests

# Type check
mypy bimcalc

# All checks (run before commit)
black . && ruff check --fix && mypy bimcalc && pytest
```

### CLI Commands

```bash
# Ingest schedule
python -m bimcalc.cli ingest schedule data/schedule.csv --org-id 1

# Ingest pricebook
python -m bimcalc.cli ingest pricebook data/pricebook.csv --org-id 1

# Run matching
python -m bimcalc.cli match run --schedule-id 1 --min-confidence 0.7

# Review matches
python -m bimcalc.cli review ui

# Generate report
python -m bimcalc.cli report build --schedule-id 1 --output report.xlsx
```

### Docker

```bash
# Build image
docker build -t bimcalc:latest .

# Run container
docker run -p 8000:8000 bimcalc:latest

# Docker Compose (full stack)
docker-compose up

# Rebuild services
docker-compose up --build

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Web Application

```bash
# Run development server
uvicorn bimcalc.web.app_enhanced:app --reload --port 8000

# Run with hot reload
uvicorn bimcalc.web.app_enhanced:app --reload --log-level debug

# Run in production mode
uvicorn bimcalc.web.app_enhanced:app --host 0.0.0.0 --port 8000
```

### Utilities

```bash
# Generate sample data
python scripts/generate_sample_data.py

# Backup database
python scripts/backup_database.py

# Performance profiling
python -m cProfile -o profile.stats -m bimcalc.cli match run
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumtime').print_stats(20)"
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Commit changes
git add .
git commit -m "feat: add new feature"

# Push to remote
git push -u origin feature/your-feature-name

# Create pull request (use GitHub UI or gh CLI)
gh pr create --title "Add new feature" --body "Description"

# Update branch from main
git checkout main
git pull
git checkout feature/your-feature-name
git rebase main
```

### Commit Message Format

Follow Conventional Commits:

```
feat: add new feature
fix: correct bug
docs: update documentation
style: format code
refactor: restructure without changing behavior
test: add tests
chore: update dependencies
```

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres
```

### Import Errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Migration Conflicts
```bash
# Reset to clean state
alembic downgrade base
alembic upgrade head

# If conflicts persist, manually resolve migration files
```

---

**Daily Workflow**: `git pull` → `docker-compose up -d` → `pytest` → code → `black . && ruff check --fix && mypy bimcalc` → commit
