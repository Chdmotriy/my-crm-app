import streamlit as st
import pandas as pd
from sqlalchemy import text

# Импорт наших утилит
from utils.db import init_db_connection

# Импорт всех страниц интерфейса
from views import (
    calendar_view, analytics_view, registry_view, 
    card_view, new_deal_view, template_view, profile_view
)

# --- 1. БАЗОВЫЕ НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Interactive Pro", layout="wide")

# 👇 ДОБАВЛЯЕМ CSS-МАГИЮ СЮДА 👇
def apply_custom_css():
    st.markdown("""
    <style>
        /* Красивые карточки для метрик (KPI) */
        [data-testid="stMetric"] {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 15px 20px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.04);
            border: 1px solid #f0f2f6;
            transition: transform 0.2s ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
        }
        
        /* Плавные и современные главные кнопки (Primary) */
        button[kind="primary"] {
            background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            transition: all 0.3s ease;
        }
        button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
            border: none;
        }
        
        /* Аккуратные вкладки (Tabs) в карточке клиента */
        [data-baseweb="tab-list"] {
            gap: 8px;
        }
        [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 10px 16px;
            background-color: #f8f9fa;
        }
        [data-baseweb="tab"][aria-selected="true"] {
            background-color: #eff6ff;
            color: #1d4ed8;
            font-weight: 600;
            border-bottom: 3px solid #3b82f6;
        }
        
        /* Смягчаем общий фон приложения для контраста карточек */
        .stApp {
            background-color: #fcfcfc;
        }
    </style>
    """, unsafe_allow_html=True)

# Запускаем наши стили
apply_custom_css()
# 👆 КОНЕЦ CSS-МАГИИ 👆

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
# 👇 ВРЕМЕННЫЙ ХАК ДЛЯ ПРИНУДИТЕЛЬНОГО ОБНОВЛЕНИЯ БАЗЫ 👇
from utils.db import setup_tables
setup_tables(engine)
# 👆 КОНЕЦ ХАКА 👆

# --- 4. НАВИГАЦИЯ (САЙДБАР) ---
# Читаем записку из Реестра до того, как отрисуем меню
if "change_page_to" in st.session_state:
    st.session_state.current_page = st.session_state.change_page_to
    del st.session_state.change_page_to # Удаляем записку, чтобы не зациклиться

with st.sidebar:
    st.divider()
    
    if "current_page" not in st.session_state:
        st.session_state.current_page = "📅 Календарь"

    page = st.radio(
         "📌 Главное меню",
         ["📅 Календарь", "📈 Аналитика", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка", "📄 Шаблон договора", "🏢 Профиль"], # 👈 ДОБАВИЛИ "🏢 Профиль"
         key="current_page"
     )
    
    # Умные алерты (Должники)
    st.divider()
    with engine.connect() as conn:
        overdue = pd.read_sql("""
            SELECT c.name, s.amount, s.date 
            FROM schedule s
            JOIN clients c ON s.client_id = c.id
            WHERE s.status = 'Ожидается' AND s.date < CURRENT_DATE
            ORDER BY s.date ASC
        """, conn)
    
    if not overdue.empty:
        st.error(f"🔥 Просрочки: {len(overdue)}")
        for _, row in overdue.iterrows():
            st.markdown(f"**{row['name']}** \n❌ {row['amount']:,.0f} ₽ (от {row['date'].strftime('%d.%m')})")
    else:
        st.success("✅ Нет просроченных платежей")

# --- 5. ГЛАВНЫЕ МЕТРИКИ (Только для Аналитики) ---
st.title("🏦 Интерактивная CRM")

if page == "📈 Аналитика":
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
elif page == "📄 Шаблон договора":
    template_view.render(engine)
elif page == "🏢 Профиль":           # 👈 ДОБАВИЛИ ЭТИ ДВЕ СТРОКИ
    profile_view.render(engine)
