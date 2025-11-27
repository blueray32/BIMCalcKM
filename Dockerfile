FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md README_BIMCALC_MVP.md ./
COPY bimcalc ./bimcalc
COPY config ./config
COPY tests ./tests
COPY examples ./examples

# Clean up macOS metadata files that might have been copied
RUN find . -name "._*" -delete

RUN pip install --upgrade pip && \
    pip install -e .

COPY . ./

# Clean up macOS metadata files (again, in case COPY . ./ brought them back)
RUN find . -name "._*" -delete

EXPOSE 8001

CMD ["bash"]
