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

# --- ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ---
def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, name TEXT, phone TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schedule (id SERIAL PRIMARY KEY, client_id INTEGER, amount FLOAT, planned_date DATE, comment TEXT, status TEXT DEFAULT 'pending')"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, amount FLOAT, category TEXT, expense_date DATE)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT, upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        try:
            conn.execute(text("ALTER TABLE schedule ADD COLUMN status TEXT DEFAULT 'pending'"))
        except: pass
        conn.commit()

init_db()

# --- АВТОРИЗАЦИЯ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated, st.session_state.role = False, None

if not st.session_state.authenticated:
    st.title("🔐 Вход")
    pwd = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PASSWORD: st.session_state.authenticated, st.session_state.role = True, "admin"
        elif pwd == STAFF_PASSWORD: st.session_state.authenticated, st.session_state.role = True, "assistant"
        else: st.error("Неверно")
        if st.session_state.authenticated: st.rerun()
    st.stop()

# --- ИНТЕРФЕЙС ---
st.sidebar.title(f"👤 {st.session_state.role.upper()}")
if st.sidebar.button("Выйти"):
    st.session_state.authenticated = False
    st.rerun()

t1, t2, t3, t4, t5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# 1. РЕЕСТР
with t1:
    with st.form("c_f"):
        n, p = st.text_input("Имя"), st.text_input("Телефон")
        if st.form_submit_button("Добавить"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO clients (name, phone) VALUES (:n, :p)"), {"n":n, "p":p})
                conn.commit()
            st.rerun()
    with engine.connect() as conn:
        st.dataframe(pd.read_sql_query(text("SELECT * FROM clients ORDER BY id DESC"), conn), use_container_width=True)

# 2. КАЛЕНДАРЬ
with t2:
    with engine.connect() as conn:
        cl_df = pd.read_sql_query(text("SELECT id, name FROM clients"), conn)
    if not cl_df.empty:
        with st.expander("➕ План"):
            with st.form("s_f"):
                sid = st.selectbox("Клиент", cl_df['id'], format_func=lambda x: cl_df[cl_df['id']==x]['name'].values[0])
                amt, dt = st.number_input("Сумма", 0.0), st.date_input("Дата")
                if st.form_submit_button("Ок"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO schedule (client_id, amount, planned_date) VALUES (:i, :a, :d)"), {"i":int(sid), "a":amt, "d":dt})
                        conn.commit()
                    st.rerun()
    with engine.connect() as conn:
        st.dataframe(pd.read_sql_query(text("SELECT * FROM schedule"), conn), use_container_width=True)

# 3. РАСХОДЫ
with t3:
    with st.form("e_f"):
        ea, ec, ed = st.number_input("Сумма"), st.selectbox("Категория", ["ЗП", "Маркетинг", "Аренда", "Прочее"]), st.date_input("Дата")
        if st.form_submit_button("Сохранить"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)"), {"a":ea, "c":ec, "d":ed})
                conn.commit()
            st.rerun()
    with engine.connect() as conn:
        st.dataframe(pd.read_sql_query(text("SELECT * FROM expenses ORDER BY id DESC"), conn), use_container_width=True)

# 4. КАРТОЧКА
with t4:
    if not cl_df.empty:
        sel_c = st.selectbox("Клиент", cl_df['name'], key="card_sel")
        cid = int(cl_df[cl_df['name'] == sel_name if 'sel_name' in locals() else cl_df['name'] == sel_c]['id'].iloc[0])
        
        tab_f, tab_d = st.tabs(["Финансы", "Документы"])
        with tab_f:
            with engine.connect() as conn:
                # ЗАЩИТА: выбираем всё, чтобы не упасть из-за отсутствия status
                st.table(pd.read_sql_query(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": cid}))
        with tab_d:
            with st.expander("Добавить ссылку"):
                dn, du = st.text_input("Название"), st.text_input("URL")
                if st.button("Сохранить ссылку"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"), {"i":cid, "n":dn, "u":du})
                        conn.commit()
                    st.rerun()
            with engine.connect() as conn:
                docs = pd.read_sql_query(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": cid})
            for _, d in docs.iterrows():
                c1, c2, c3 = st.columns([3,2,1])
                c1.write(d['file_name'])
                c2.link_button("Открыть", d['file_url'])
                if st.session_state.role == "admin" and c3.button("🗑️", key=f"d_{d['id']}"):
                    with engine.connect() as conn:
                        conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": int(d['id'])})
                        conn.commit()
                    st.rerun()

# 5. АНАЛИТИКА
with t5:
    if st.session_state.role == "admin":
        with engine.connect() as conn:
            # Безопасный подсчет
            exp = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
            st.metric("Общий расход", f"{exp} ₽")
            try:
                df_p = pd.read_sql_query(text("SELECT category, SUM(amount) as total FROM expenses GROUP BY category"), conn)
                if not df_p.empty: st.plotly_chart(px.pie(df_p, values='total', names='category'))
            except: st.info("Нет данных для графиков")
    else: st.warning("Доступ закрыт")
