import streamlit as st
import pandas as pd

def show(engine):
    st.title("📊 Дашборд")

    df = pd.read_sql("SELECT SUM(amount) as total FROM schedule", engine)

    total = df["total"].iloc[0] or 0

    st.metric("Оборот", f"{total:,.0f} ₽")
