def decide(row):
    name, roas = row["name"], row["roas"]
    if row["objective"] == "brand_awareness":
        ctr = row["ctr"]
        if ctr is None:
            return f"{name} | Fallback | Insufficient data to decide (CTR undefined)."
        result = "Healthy" if ctr > 1.5 else "Review creative or targeting"
        return f"{name} | R3 | {result}. CTR {ctr:.2f}%."
    if roas is None:
        return f"{name} | Fallback | Insufficient data to decide (ROAS undefined)."
    spend = row["spend"]
    if row["objective"] == "conversion" and spend > 500 and roas < 1.5:
        return f"{name} | R1 | Pause. Spend ${spend:.2f}, ROAS {roas:.2f}."
    rate = row["conversion_rate"]
    if rate is None:
        return f"{name} | Fallback | Insufficient data to decide (conversion rate undefined)."
    evidence = f"Spend ${spend:.2f}, ROAS {roas:.2f}, conversion rate {rate:.2f}%."
    if roas > 3.5 and rate > 5:
        budget = row["daily_budget"]
        return f"{name} | R2 | Scale daily budget from ${budget:.2f} to ${budget*1.2:.2f}. {evidence}"
    return f"{name} | Fallback | Hold. No budget threshold matched. {evidence}"
