import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="CRM Система", layout="wide", page_icon="📊")

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
STAFF_PASSWORD = st.secrets.get("STAFF_PASSWORD", "staff123")
DB_URL = st.secrets["DB_URL"]

engine = create_engine(DB_URL)

# --- УМНАЯ ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
def init_db():
    with engine.connect() as conn:
        # Создаем таблицы, если их нет
        conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, name TEXT, phone TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schedule (id SERIAL PRIMARY KEY, client_id INTEGER, amount FLOAT, planned_date DATE, comment TEXT, status TEXT DEFAULT 'pending')"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, amount FLOAT, category TEXT, expense_date DATE)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT, upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        
        # Проверяем колонку status в schedule (на случай старой базы)
        try: conn.execute(text("ALTER TABLE schedule ADD COLUMN status TEXT DEFAULT 'pending'"))
        except: pass
        
        # Проверяем колонку category в expenses
        try: conn.execute(text("ALTER TABLE expenses ADD COLUMN category TEXT DEFAULT 'Прочее'"))
        except: pass
        
        conn.commit()

init_db()

# --- АВТОРИЗАЦИЯ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("🔐 Вход в систему")
    pwd = st.text_input("Введите пароль", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.role = "admin"
            st.rerun()
        elif pwd == STAFF_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.role = "assistant"
            st.rerun()
        else:
            st.error("Неверный пароль")
    st.stop()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
st.sidebar.title(f"👤 {st.session_state.role.upper()}")
if st.sidebar.button("Выйти"):
    st.session_state.authenticated = False
    st.rerun()

t1, t2, t3, t4, t5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# 1. РЕЕСТР
with t1:
    st.subheader("Клиенты")
    with st.form("add_c"):
        n = st.text_input("Имя")
        p = st.text_input("Телефон")
        if st.form_submit_button("Добавить"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO clients (name, phone) VALUES (:n, :p)"), {"n": n, "p": p})
                conn.commit()
            st.rerun()
    with engine.connect() as conn:
        df_c = pd.read_sql_query(text("SELECT * FROM clients ORDER BY id DESC"), conn)
    st.dataframe(df_c, use_container_width=True)

# 2. КАЛЕНДАРЬ
with t2:
    st.subheader("План приходов")
    with engine.connect() as conn:
        cl_list = pd.read_sql_query(text("SELECT id, name FROM clients"), conn)
    
    if not cl_list.empty:
        with st.expander("📅 Запланировать"):
            with st.form("add_s"):
                sid = st.selectbox("Клиент", cl_list['id'], format_func=lambda x: cl_list[cl_list['id']==x]['name'].values[0])
                amt = st.number_input("Сумма", 0.0)
                dt = st.date_input("Дата")
                if st.form_submit_button("Ок"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO schedule (client_id, amount, planned_date) VALUES (:i, :a, :d)"), {"i": int(sid), "a": amt, "d": dt})
                        conn.commit()
                    st.rerun()
    
    with engine.connect() as conn:
        df_s = pd.read_sql_query(text("SELECT s.*, c.name FROM schedule s LEFT JOIN clients c ON s.client_id = c.id"), conn)
    st.dataframe(df_s, use_container_width=True)

# 3. РАСХОДЫ
with t3:
    st.subheader("Затраты")
    with st.form("add_e"):
        ea = st.number_input("Сумма", 0.0)
        ec = st.selectbox("Категория", ["Аренда", "Маркетинг", "ЗП", "Налоги", "Прочее"])
        ed = st.date_input("Дата")
        if st.form_submit_button("Сохранить"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)"), {"a": ea, "c": ec, "d": ed})
                conn.commit()
            st.rerun()
    with engine.connect() as conn:
        df_e = pd.read_sql_query(text("SELECT * FROM expenses ORDER BY id DESC"), conn)
    st.dataframe(df_e, use_container_width=True)

# 4. КАРТОЧКА
with t4:
    if not cl_list.empty:
        sel_c = st.selectbox("Клиент", cl_list['name'])
        cid = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        t_fin, t_doc = st.tabs(["Финансы", "Документы"])
        with t_fin:
            with engine.connect() as conn:
                st.table(pd.read_sql_query(text("SELECT amount, planned_date, status FROM schedule WHERE client_id = :id"), conn, params={"id": cid}))
        with t_doc:
            with st.expander("Добавить ссылку"):
                dn = st.text_input("Название")
                du = st.text_input("URL")
                if st.button("Добавить"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"), {"i": cid, "n": dn, "u": du})
                        conn.commit()
                    st.rerun()
            with engine.connect() as conn:
                docs = pd.read_sql_query(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": cid})
            for _, d in docs.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(d['file_name'])
                col2.link_button("Открыть", d['file_url'])
                if st.session_state.role == "admin":
                    if col3.button("🗑️", key=f"d_{d['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": int(d['id'])})
                            conn.commit()
                        st.rerun()

# 5. АНАЛИТИКА
with t5:
    if st.session_state.role == "admin":
        st.subheader("Отчеты")
        try:
            with engine.connect() as conn:
                inc = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status='paid'")).scalar() or 0
                exp = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
                st.columns(3)[0].metric("Доход", f"{inc} ₽")
                st.columns(3)[1].metric("Расход", f"{exp} ₽")
                st.columns(3)[2].metric("Чистая", f"{inc-exp} ₽")
                
                df_pie = pd.read_sql_query(text("SELECT category, SUM(amount) as total FROM expenses GROUP BY category"), conn)
                if not df_pie.empty:
                    st.plotly_chart(px.pie(df_pie, values='total', names='category', title="Траты по категориям"))
        except Exception as e:
            st.error(f"Ошибка аналитики: {e}")
    else:
        st.warning("Нет доступа")
