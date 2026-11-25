import json
import os
from html import escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st


API_URL = os.getenv("MARKETING_API_URL", "http://localhost:8080").rstrip("/")
EXAMPLES = {
    "Which channel had the highest ROAS over the last 30 days?":
        "در ۳۰ روز گذشته کدام کانال بیشترین بازده هزینهٔ تبلیغات را داشت؟",
    "Which active campaigns qualify for a budget increase?":
        "کدام کمپین‌های فعال شرایط افزایش بودجه را دارند؟",
    "Is our LinkedIn brand awareness campaign healthy?":
        "آیا کمپین آگاهی از برند ما در لینکدین عملکرد خوبی دارد؟",
}


def label(english, persian):
    if language == "فارسی":
        return f"\u2067{persian}\u2069"
    return english


st.set_page_config(page_title="Campaign analysis | تحلیل کمپین", page_icon="📊")
language = st.selectbox("زبان / Language", ["فارسی", "English"])
st.html("""
<style>
.stMainBlockContainer { max-width: 59rem; }
.campaign-header {
    display: flex; justify-content: space-between; align-items: end;
    flex-wrap: wrap; gap: 1rem; color: white; border-radius: 1.25rem;
    padding: clamp(1.5rem, 4vw, 3rem);
    background: radial-gradient(ellipse at top right, #8559af 0%, transparent 65%),
                linear-gradient(110deg, #332047, #563378);
}
.campaign-header h1 { color: white; margin: 0; padding: 0; line-height: 1.2;
    font-size: clamp(1.9rem, 4vw, 2.7rem); }
.campaign-header span { margin-inline-start: auto; font-size: 1.65rem; }
[data-testid="stForm"] { background: white; border-color: #ded2e9; border-radius: 1rem; }
textarea { unicode-bidi: plaintext; }
</style>
""")
english_title = "<h1>Campaign analysis</h1>" if language != "فارسی" else ""
persian_title = '<span lang="fa" dir="rtl">تحلیل کمپین‌ها</span>' if language != "English" else ""
st.html(f'<header class="campaign-header">{english_title}{persian_title}</header>')
mode = st.radio(label("Analysis mode", "روش تحلیل"), ["sample", "live"],
                format_func=lambda value: label("Sample questions", "سؤال‌های نمونه")
                if value == "sample" else label("Live analysis", "تحلیل زنده"),
                horizontal=True)
offline = mode == "sample"
with st.form("campaign_question"):
    if offline:
        question = st.selectbox(label("Choose a question", "یک سؤال انتخاب کنید"),
                                list(EXAMPLES), format_func=lambda q: label(q, EXAMPLES[q]))
    else:
        question = st.text_area(label("Your question", "سؤال شما"), max_chars=4096,
                                placeholder=label("Ask in either language", "فارسی یا انگلیسی بنویسید"))
        st.caption(label("Uses the configured model", "با مدل تنظیم‌شده روی سرور"))
    submitted = st.form_submit_button(label("Run analysis", "اجرای تحلیل"), type="primary")

if submitted:
    st.session_state.pop("result", None)
    if not question.strip():
        st.warning(label("Enter a question to analyze.", "برای تحلیل، یک سؤال وارد کنید."))
    else:
        request = Request(
            f"{API_URL}/questions",
            data=json.dumps({"question": question.strip(), "offline": offline}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with st.spinner(label("Analyzing campaign data...", "در حال تحلیل داده‌های کمپین…")):
                with urlopen(request, timeout=155) as response:
                    st.session_state.result = json.load(response)
        except HTTPError as error:
            if error.code == 402:
                st.error(label("Check your model provider's API balance.", "موجودی کیف پول API ارائه‌دهندهٔ مدل را بررسی کنید."))
            elif error.code == 503:
                st.warning(label("The API is busy. Try again in a moment.", "سرور مشغول است. کمی بعد دوباره تلاش کنید."))
            elif error.code == 502:
                st.error(label("The planning service is unavailable. Check the API provider settings.", "سرویس مدل در دسترس نیست. تنظیمات ارائه‌دهنده را بررسی کنید."))
            else:
                st.error(label(f"API error {error.code}", f"خطای سرور {error.code}"))
        except (URLError, TimeoutError):
            st.error(label("Could not reach the marketing API. Check the connection and try again.", "ارتباط با سرور برقرار نشد. اتصال را بررسی و دوباره تلاش کنید."))


if "result" in st.session_state:
    st.subheader(label("Analysis result", "نتیجهٔ تحلیل"))
    result = st.session_state.result
    if language == "فارسی":
        with st.container(border=True):
            st.html('<div dir="rtl" lang="fa" style="white-space:pre-wrap">' +
                    escape(result["answer_fa"]) + '</div>')
    else:
        with st.container(border=True):
            st.text(result["answer"])
