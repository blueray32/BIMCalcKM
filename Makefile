.PHONY: fmt lint test cov

fmt:
	black .
	ruff check --fix .

lint:
	ruff check .
	mypy bimcalc

test:
	pytest -q

cov:
	pytest --cov=bimcalc --cov-report=term-missing
