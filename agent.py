import json
import re
import sqlite3
from datetime import date
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from database import BASE, RATIOS, query, window
from planner import fixture, live
from policy import decide


class State(TypedDict, total=False):
    question: str
    plan: dict
    attempt: int
    error: str
    answer: str


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch("[a-z][a-z_]{0,39}", value):
        raise ValueError("Invalid column identifier")
    # Qualify columns so unknown identifiers produce a real SQLite error.
    return "r." + value


def run(question, path, offline=False, trace=lambda event: None):
    def read(sql, args=()):
        trace(dict(sql=sql, parameters=args))
        rows = query(path, sql, args)
        trace(dict(row_count=len(rows), sample=rows[:4]))
        return rows

    def planning(s):
        attempt = s.get("attempt", 0) + 1
        trace(dict(attempt=attempt))
        model = fixture if offline else live
        context = json.dumps([s.get("plan"), s["error"]]) if s.get("error") else ""
        plan = model(question, context)
        trace(dict(plan=plan))
        return dict(plan=plan, attempt=attempt, error="")

    def execute(s):
        p = s["plan"]
        try:
            if not isinstance(p, dict):
                raise ValueError("The planner must return a JSON object")
            intent = p["intent"]
            if intent == "write":
                return dict(answer="Blocked. This agent has read-only database access.")
            if intent == "clarify":
                return dict(
                    answer=p.get("question", "Which campaign or metric do you mean?")
                )
            if intent == "outside":
                return dict(
                    answer="This agent supports campaign performance and budget recommendations."
                )
            if intent not in ("policy", "analytics"):
                raise ValueError("Unknown plan intent")
            start, end = window(30)
            start, end = p.get("start") or start, p.get("end") or end
            if date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError("Start date must precede end date")
            filters, args = [], [start, end]
            name = p.get("name")
            if name:
                matches = read(
                    "SELECT id,name FROM campaigns WHERE instr(lower(name),lower(?))>0 ORDER BY name",
                    (name,),
                )
                exact = [r for r in matches if r["name"].casefold() == name.casefold()]
                matches = exact or matches
                if not matches:
                    return dict(answer=f'No campaign matches "{name}".')
                if len(matches) > 1:
                    return dict(
                        answer="Which campaign do you mean? "
                        + ", ".join(r["name"] for r in matches)
                    )
                trace(dict(resolved=matches[0]))
                filters.append("id=?")
                args.append(matches[0]["id"])
            if p.get("active"):
                filters.append("status='active'")
            if p.get("channel"):
                filters.append("channel=?")
                args.append(p["channel"])
            if p.get("objective"):
                filters.append("objective=?")
                args.append(p["objective"])
            where = " WHERE " + " AND ".join(filters) if filters else ""
            cte = f"WITH totals AS ({BASE}), scoped AS (SELECT * FROM totals{where})"
            campaign = f"{cte} SELECT *,{RATIOS} FROM scoped"
            output = []
            if intent == "policy":
                for row in read(campaign + " ORDER BY name", args):
                    decision = decide(row)
                    trace(dict(decision=decision))
                    if not p.get("decision") or decision.split("|")[
                        2
                    ].strip().startswith(p["decision"]):
                        output.append(decision)
            else:
                if not p.get("reports"):
                    raise ValueError("Supply at least one report")
                for report in p["reports"]:
                    source = campaign
                    label = "name"
                    if report["group"] == "channel":
                        label = "channel"
                        totals = ",".join(
                            f"SUM({col}) AS {col}"
                            for col in (
                                "impressions",
                                "clicks",
                                "spend",
                                "conversions",
                                "revenue",
                            )
                        )
                        source = f"{cte}, grouped AS (SELECT channel,{totals} FROM scoped GROUP BY channel) SELECT *,{RATIOS} FROM grouped"
                    elif report["group"] != "campaign":
                        raise ValueError("Group by channel or campaign")
                    columns = [identifier(v) for v in report["fields"]]
                    if not columns:
                        raise ValueError("Supply at least one report field")
                    sql = (
                        f"SELECT r.{label}, "
                        + ", ".join(columns)
                        + f" FROM ({source}) AS r"
                    )
                    if report.get("zero_conversions_with_spend"):
                        sql += " WHERE r.conversions=0 AND r.spend>0"
                    orders = []
                    for field, direction in report.get("order", []):
                        if direction not in ("asc", "desc"):
                            raise ValueError("Invalid sort direction")
                        orders.append(f"{identifier(field)} {direction} NULLS LAST")
                    sql += " ORDER BY " + ", ".join([*orders, "r." + label])
                    limit = int(report.get("limit", 200))
                    if not 1 <= limit <= 200:
                        raise ValueError("Limit must be 1 to 200")
                    for row in read(sql + " LIMIT ?", (*args, limit)):
                        output.append(
                            " | ".join(
                                f"{k}: {format_value(v)}"
                                + (
                                    "%"
                                    if v is not None and k in ("ctr", "conversion_rate")
                                    else ""
                                )
                                for k, v in row.items()
                            )
                        )
            body = "\n".join(output) or "No matching results."
            return dict(answer=f"{start} through {end}\n{body}")
        except (sqlite3.Error, ValueError, KeyError, TypeError, IndexError) as exc:
            trace(dict(error=str(exc)))
            return dict(
                error=str(exc),
                answer=f'Unable to complete the query after {s["attempt"]} attempt(s): {exc}',
            )

    graph = StateGraph(State)
    graph.add_node("plan_request", planning)
    graph.add_node("execute", execute)
    graph.add_edge(START, "plan_request")
    graph.add_edge("plan_request", "execute")
    graph.add_conditional_edges(
        "execute",
        lambda s: "plan_request" if s.get("error") and s["attempt"] < 3 else END,
    )
    trace(dict(mode="offline fixture" if offline else "live LLM", question=question))
    answer = graph.compile().invoke(dict(question=question))["answer"]
    trace(dict(answer=answer))
    return answer


def format_value(value):
    if value is None:
        return "undefined (insufficient data)"
    return f"{value:.2f}" if isinstance(value, float) else str(value)
