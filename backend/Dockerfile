FROM docker.arvancloud.ir/library/python:3.12-slim-bookworm AS dependencies
WORKDIR /app
RUN pip install --no-cache-dir poetry==1.8.3
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

FROM docker.arvancloud.ir/library/python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MARKETING_DB=/data/marketing.db
WORKDIR /app

COPY --from=dependencies /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --system --uid 10001 --user-group agent \
    && install -d -o agent -g agent /data /app/logs

COPY api.py agent.py cli.py database.py planner.py policy.py scenarios.py seed_db.py ./
USER agent
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
