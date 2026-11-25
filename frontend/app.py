import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st


API_URL = os.getenv("MARKETING_API_URL", "http://localhost:8080").rstrip("/")
EXAMPLES = [
    "Which channel had the highest ROAS over the last 30 days?",
    "Which active campaigns qualify for a budget increase?",
    "Is our LinkedIn brand awareness campaign healthy?",
]

st.set_page_config(page_title="Marketing Ops", page_icon="📊")
st.title("Campaign analysis")
mode = st.radio("Question mode", ["Sample questions", "Live analysis"], horizontal=True)
offline = mode == "Sample questions"
with st.form("campaign_question"):
    if offline:
        question = st.selectbox("Sample question", EXAMPLES)
    else:
        question = st.text_area("Your question", max_chars=4096,
                                placeholder="Ask about campaign performance or budget policy.")
        st.caption("Live analysis uses the model configured on the API server.")
    submitted = st.form_submit_button("Analyze", type="primary")

if submitted:
    if not question.strip():
        st.warning("Enter a question to analyze.")
    else:
        request = Request(
            f"{API_URL}/questions",
            data=json.dumps({"question": question.strip(), "offline": offline}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with st.spinner("Analyzing campaign data..."):
                with urlopen(request, timeout=155) as response:
                    answer = json.load(response)["answer"]
            st.subheader("Result")
            st.text(answer)
        except HTTPError as error:
            if error.code == 503:
                st.warning("The API is busy. Try again in a moment.")
            elif error.code == 502:
                st.error("The planning service is unavailable. Check the API provider settings.")
            else:
                st.error(f"The API returned HTTP {error.code}.")
        except (URLError, TimeoutError):
            st.error("Could not reach the marketing API. Check the connection and try again.")
