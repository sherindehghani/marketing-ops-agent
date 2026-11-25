FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MARKETING_DB=/data/marketing.db
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --user-group agent \
    && install -d -o agent -g agent /data /app/logs

COPY agent.py cli.py database.py planner.py policy.py scenarios.py seed_db.py ./
USER agent
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
