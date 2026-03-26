import streamlit as st
import config
from utils.db import init_db_connection, setup_tables
from views import (
    calendar_view, analytics_view, registry_view, 
    card_view, new_deal_view, template_view
)

# 1. Базовые настройки
st.set_page_config(page_title="CRM Interactive Pro", layout="wide")

# 2. Авторизация
with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")
    
if user_password != st.secrets.get("ADMIN_PASSWORD"):
    st.info("Введите пароль.")
    st.stop()

# 3. Инициализация БД
engine = init_db_connection()
setup_tables(engine) # Создаст таблицы, если их нет

# 4. Навигация
with st.sidebar:
    st.divider()
    page = st.radio(
        "📌 Главное меню",
        ["📅 Календарь", "📈 Аналитика", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка", "📄 Шаблон договора"]
    )

# 5. Роутинг (вызов модулей)
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
