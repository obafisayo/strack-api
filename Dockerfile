FROM python:3.12-slim

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic ./alembic
COPY alembic.ini ./
COPY static ./static
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Production entrypoint: runs migrations, then serves without --reload, on
# $PORT if the platform sets one (Render et al), else 8000. Local dev's
# docker-compose.yml overrides `command` with its own --reload variant.
CMD ["./docker-entrypoint.sh"]
