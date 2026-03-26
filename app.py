import streamlit as st
from db import get_engine

# --- CONFIG ---
st.set_page_config(page_title="CRM", layout="wide")

# --- AUTH ---
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")

if user_password != ADMIN_PASSWORD:
    st.stop()

engine = get_engine()

# --- MENU ---
with st.sidebar:
    page = st.radio("Меню", [
        "📊 Дашборд",
        "📅 Календарь",
        "📋 Реестр",
        "🔍 Карточка",
        "➕ Сделка",
        "📄 Договор"
    ])

# --- ROUTING ---
if page == "📊 Дашборд":
    from pages.dashboard import show
    show(engine)

elif page == "📅 Календарь":
    from pages.calendar_page import show
    show(engine)

elif page == "📋 Реестр":
    from pages.registry import show
    show(engine)

elif page == "🔍 Карточка":
    from pages.client_card import show
    show(engine)

elif page == "➕ Сделка":
    from pages.new_deal import show
    show(engine)

elif page == "📄 Договор":
    from pages.contract_template import show
    show(engine)
