
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY ingestion/ ./ingestion/
COPY scripts/ ./scripts/
COPY transformations/ ./transformations/

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

CMD ["python", "scripts/run_pipeline.py"]
