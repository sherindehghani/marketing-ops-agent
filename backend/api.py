import asyncio
import os
from pathlib import Path
from urllib.error import HTTPError, URLError

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agent import run
from database import query

app = FastAPI(title="Marketing Operations API")
database = Path(os.getenv("MARKETING_DB", "marketing.db"))
max_requests = int(os.getenv("API_CONCURRENCY", "8"))
if max_requests < 1:
    raise ValueError("API_CONCURRENCY must be positive")
capacity = asyncio.Semaphore(max_requests)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4096)
    offline: bool = False


@app.get("/health")
def health():
    try:
        query(database, "SELECT id FROM campaigns LIMIT 1")
    except Exception as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ready"}


@app.post("/questions")
async def ask(request: Question):
    if not request.question.strip():
        raise HTTPException(422, "A question is required")
    if capacity.locked():
        raise HTTPException(503, "All workers are busy", headers={"Retry-After": "1"})
    async with capacity:
        try:
            result = await asyncio.to_thread(run, request.question, database, request.offline, bilingual=True)
        except HTTPError as exc:
            if exc.code == 402:
                raise HTTPException(402, "Planning provider requires payment") from exc
            raise HTTPException(502, "Planning service unavailable") from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(502, "Planning service unavailable") from exc
        return result
