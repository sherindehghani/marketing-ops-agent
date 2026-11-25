import json
import os
from datetime import date
from urllib.request import Request, urlopen

PROMPT = """You plan marketing requests in English or Persian for a read-only SQLite agent.
Return one JSON object with intent (analytics, policy, clarify, outside, or write),
name (campaign name/fragment exactly as mentioned, otherwise empty), and optional
start and end inclusive ISO dates. Today is TODAY. Default is last 30 calendar days.
Set active=true for active campaigns only. Set channel to google_ads, instagram,
linkedin or email only if filtered. Set objective to conversion, brand_awareness
or retargeting only if requested. For vague criteria use clarify with a question.
For policy requests set decision to Scale, Pause, Hold, Healthy or Review ONLY if
the user explicitly asks to filter by recommendation. For analytics return reports,
one per requested comparison. Each report has group (campaign or channel), fields
(list of numeric columns), optional order (list of [column, asc or desc]), optional
limit, optional zero_conversions_with_spend (boolean). Columns: impressions, clicks,
spend, conversions, revenue, roas, ctr, conversion_rate. Handle campaign/channel
metrics only. Compound rankings: give separate rankings or clarify an ambiguous
tradeoff. Use policy intent for budget decisions and awareness health. Never supply
numbers for the answer. Write requests use intent write. Unsupported analytics
use outside. For clarify, return the same clarification in English (question) and Persian (question_fa)."""


def live(question, error=""):
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Content-Type": "application/json"}
    if key := os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        headers["Authorization"] = "Bearer " + key
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": PROMPT.replace("TODAY", date.today().isoformat()),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"request": question, "correction_context": error}
                ),
            },
        ],
    }
    req = Request(
        base + "/chat/completions", data=json.dumps(payload).encode(), headers=headers
    )
    with urlopen(req, timeout=45) as response:
        content = json.load(response)["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content


QUESTIONS = {
    "ranking": "Which channel had the highest ROAS over the last 30 days?",
    "scale": "Should we increase the budget for Summer_Sale?",
    "pause": "Should we pause Summer_Clearance?",
    "awareness": "Is Brand_Reach healthy?",
    "review": "Is Brand_Recall healthy?",
    "ambiguous": "How is Summer doing?",
    "security": "Delete the campaigns table.",
    "zero": "What is the ROAS for Launch_Queue?",
    "hold": "Should we pause Trial_Search?",
    "retry": "Rank channels by revenue.",
    "outside": "What is the price of bitcoin?",
    "missing": "Evaluate the Black_Friday campaign.",
    "awareness_scope": "Is our LinkedIn brand awareness campaign healthy?",
    "zero_conversions": "Which campaigns spent money but recorded no conversions?",
    "active_scale": "Which active campaigns qualify for a budget increase?",
    "compound_ranking": "Which channel had the highest ROAS and which campaign spent the most?",
    "retry_limit": "Exercise the retry limit for an invalid report.",
}


def fixture(question, error=""):
    key = next((k for k, v in QUESTIONS.items() if v == question), None)
    if key == "retry_limit":
        return dict(
            intent="analytics",
            reports=[dict(group="channel", fields=["revenues"])],
        )
    if key == "compound_ranking":
        return dict(
            intent="analytics",
            reports=[
                dict(group="channel", fields=["roas"], order=[["roas", "desc"]], limit=1),
                dict(group="campaign", fields=["spend"], order=[["spend", "desc"]], limit=1),
            ],
        )
    if key == "awareness_scope":
        return dict(intent="policy", channel="linkedin", objective="brand_awareness")
    if key == "active_scale":
        return dict(intent="policy", active=True, decision="Scale")
    if key == "zero_conversions":
        return dict(
            intent="analytics",
            reports=[
                dict(
                    group="campaign",
                    fields=["spend", "conversions"],
                    zero_conversions_with_spend=True,
                )
            ],
        )
    if key in ("ranking", "retry", "zero"):
        metric = "revenue" if key == "retry" else "roas"
        field = "revenues" if key == "retry" and not error else metric
        report = dict(
            group="campaign" if key == "zero" else "channel",
            fields=[field],
            order=[[metric, "desc"]],
            limit=1 if key == "ranking" else 100,
        )
        return dict(
            intent="analytics",
            reports=[report],
            name="Launch_Queue" if key == "zero" else "",
        )
    names = dict(
        scale="Summer_Sale",
        pause="Summer_Clearance",
        awareness="Brand_Reach",
        review="Brand_Recall",
        ambiguous="Summer",
        hold="Trial_Search",
        missing="Black_Friday",
    )
    if key in names:
        return dict(intent="policy", name=names[key])
    return dict(intent="write" if key == "security" else "outside")
