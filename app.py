import streamlit as st
from openai import OpenAI
import pandas as pd

st.set_page_config(
    page_title="AI Optimisation Audit Checklist",
    page_icon="✅",
    layout="wide"
)

st.title("AI Optimisation Audit Checklist")

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

uploaded_file = st.file_uploader("Upload your audit checklist Excel file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    st.subheader("Checklist Preview")
    st.dataframe(df)

    if "Score" in df.columns and "Weighting" in df.columns:
        df["Weighted Score"] = df["Score"] * df["Weighting"]
        total_score = df["Weighted Score"].sum()
        max_score = (5 * df["Weighting"]).sum()
        readiness = round((total_score / max_score) * 100, 1)

        st.metric("Total Weighted Score", total_score)
        st.metric("Max Possible Score", max_score)
        st.metric("AI Readiness %", f"{readiness}%")
