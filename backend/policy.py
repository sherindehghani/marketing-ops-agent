def decide(row, language="en"):
    fa = language == "fa"
    name, roas = row["name"], row["roas"]
    if row["objective"] == "brand_awareness":
        ctr = row["ctr"]
        if ctr is None:
            if fa:
                return f"{name} | Fallback | دادهٔ ناکافی برای تصمیم‌گیری؛ نرخ کلیک تعریف‌نشده است."
            return f"{name} | Fallback | Insufficient data to decide (CTR undefined)."
        if fa:
            status = "سالم" if ctr > 1.5 else "بازبینی محتوای تبلیغ یا هدف‌گیری"
            return f"{name} | R3 | {status}. نرخ کلیک: {ctr:.2f}٪."
        result = "Healthy" if ctr > 1.5 else "Review creative or targeting"
        return f"{name} | R3 | {result}. CTR {ctr:.2f}%."
    if roas is None:
        if fa:
            return f"{name} | Fallback | دادهٔ ناکافی برای تصمیم‌گیری؛ بازده هزینهٔ تبلیغات تعریف‌نشده است."
        return f"{name} | Fallback | Insufficient data to decide (ROAS undefined)."
    spend = row["spend"]
    if row["objective"] == "conversion" and spend > 500 and roas < 1.5:
        if fa:
            return f"{name} | R1 | توقف کمپین. هزینه: ${spend:.2f}، بازده هزینهٔ تبلیغات: {roas:.2f}."
        return f"{name} | R1 | Pause. Spend ${spend:.2f}, ROAS {roas:.2f}."
    rate = row["conversion_rate"]
    if rate is None:
        if fa:
            return f"{name} | Fallback | دادهٔ ناکافی برای تصمیم‌گیری؛ نرخ تبدیل تعریف‌نشده است."
        return f"{name} | Fallback | Insufficient data to decide (conversion rate undefined)."
    evidence = f"Spend ${spend:.2f}, ROAS {roas:.2f}, conversion rate {rate:.2f}%."
    if fa:
        evidence = f"هزینه: ${spend:.2f}، بازده هزینهٔ تبلیغات: {roas:.2f}، نرخ تبدیل: {rate:.2f}٪."
    if roas > 3.5 and rate > 5:
        budget = row["daily_budget"]
        if fa:
            return f"{name} | R2 | افزایش بودجهٔ روزانه از ${budget:.2f} به ${budget*1.2:.2f}. {evidence}"
        return f"{name} | R2 | Scale daily budget from ${budget:.2f} to ${budget*1.2:.2f}. {evidence}"
    if fa:
        return f"{name} | Fallback | حفظ وضعیت فعلی؛ شرایط تغییر بودجه برقرار نیست. {evidence}"
    return f"{name} | Fallback | Hold. No budget threshold matched. {evidence}"
