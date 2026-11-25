FROM docker.arvancloud.ir/library/python:3.12-slim-bookworm AS dependencies
WORKDIR /app
RUN pip install --no-cache-dir poetry==1.8.3
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-interaction --no-ansi

FROM docker.arvancloud.ir/library/python:3.12-slim-bookworm
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
RUN useradd --create-home --uid 10001 dashboard
COPY app.py .
USER dashboard
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
