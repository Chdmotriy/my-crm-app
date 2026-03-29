import streamlit as st
import pandas as pd
from sqlalchemy import text

# Импорт наших утилит
from utils.db import init_db_connection, setup_tables

# Импорт всех страниц интерфейса
from views import (
    calendar_view, analytics_view, registry_view, 
    card_view, new_deal_view, template_view
)

# --- 1. БАЗОВЫЕ НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Interactive Pro", layout="wide")

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
    DB_URL = st.secrets["DB_URL"]
except KeyError:
    st.error("⚠️ Ошибка: Проверьте файл .streamlit/secrets.toml. Отсутствует пароль или ссылка на БД.")
    st.stop()

# --- 2. АВТОРИЗАЦИЯ ---
with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")
    
if user_password != ADMIN_PASSWORD:
    st.info("Пожалуйста, введите пароль для доступа к системе.")
    st.stop()

# --- 3. ИНИЦИАЛИЗАЦИЯ БД ---
# Используем кэшированное подключение, чтобы CRM летала!
engine = init_db_connection(DB_URL)
setup_tables(engine)

# --- 4. ГЛАВНЫЕ МЕТРИКИ (Отображаются на всех страницах) ---
st.title("🏦 Интерактивная CRM")

with engine.connect() as conn:
    inc_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    exp_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn)
    
t_rev, p_rev = float(inc_data['t'].iloc[0] or 0), float(inc_data['p'].iloc[0] or 0)
t_exp, p_exp = float(exp_data['t'].iloc[0] or 0), float(exp_data['p'].iloc[0] or 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Общий оборот", f"{t_rev:,.0f} ₽")
c2.metric("Всего затрат", f"{t_exp:,.0f} ₽", delta=f"-{t_exp:,.0f}", delta_color="inverse")
c3.metric("Прибыль (план)", f"{(t_rev - t_exp):,.0f} ₽")
c4.metric("Касса (факт)", f"{(p_rev - p_exp):,.0f} ₽")

st.divider()

# --- 5. НАВИГАЦИЯ (САЙДБАР) ---

# 👈 ЧИТАЕМ ЗАПИСКУ ИЗ РЕЕСТРА ДО ТОГО, КАК ОТРИСУЕМ МЕНЮ
if "change_page_to" in st.session_state:
    st.session_state.current_page = st.session_state.change_page_to
    del st.session_state.change_page_to # Удаляем записку, чтобы не зациклиться

with st.sidebar:
    st.divider()
    
    if "current_page" not in st.session_state:
        st.session_state.current_page = "📅 Календарь"

    page = st.radio(
        "📌 Главное меню",
        ["📅 Календарь", "📈 Аналитика", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка", "📄 Шаблон договора"],
        key="current_page"
    )

# --- 6. РОУТИНГ (Запуск выбранной страницы) ---
if page == "📅 Календарь":
    calendar_view.render(engine)
elif page == "📈 Аналитика":
    analytics_view.render(engine)
elif page == "📋 Реестр":
    registry_view.render(engine)
elif page == "🔍 Карточка":
    card_view.render(engine)
elif page == "➕ Новая сделка":
    new_deal_view.render(engine)
elif page == "📄 Шаблон договора":
    template_view.render(engine)
