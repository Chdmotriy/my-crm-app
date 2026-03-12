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

# --- ИНТЕРФЕЙС ---
st.sidebar.title(f"👤 {st.session_state.role.upper()}")
if st.sidebar.button("Выйти"):
    st.session_state.authenticated = False
    st.rerun()

t1, t2, t3, t4, t5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# 1. РЕЕСТР КЛИЕНТОВ
with t1:
    st.subheader("Управление клиентами")
    with st.form("add_client"):
        name = st.text_input("Имя / Компания")
        phone = st.text_input("Телефон")
        if st.form_submit_button("Создать"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO clients (name, phone) VALUES (:n, :p)"), {"n": name, "p": phone})
                conn.commit()
            st.rerun()
    
    with engine.connect() as conn:
        clients = pd.read_sql_query(text("SELECT * FROM clients"), conn)
    st.dataframe(clients, use_container_width=True)

# 2. КАЛЕНДАРЬ ПЛАТЕЖЕЙ
with t2:
    st.subheader("План поступлений")
    with engine.connect() as conn:
        cl_df = pd.read_sql_query(text("SELECT id, name FROM clients"), conn)
    
    with st.expander("📅 Запланировать приход"):
        with st.form("add_sch"):
            if not cl_df.empty:
                c_id = st.selectbox("Клиент", cl_df['id'], format_func=lambda x: cl_df[cl_df['id']==x]['name'].values[0])
                amt = st.number_input("Сумма", min_value=0.0)
                dt = st.date_input("Дата")
                comm = st.text_input("Комментарий")
                if st.form_submit_button("Добавить"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO schedule (client_id, amount, planned_date, comment) VALUES (:cid, :a, :d, :c)"),
                                  {"cid": int(c_id), "a": amt, "d": dt, "c": comm})
                        conn.commit()
                    st.rerun()
            else: st.warning("Сначала добавьте клиента")
    
    with engine.connect() as conn:
        sched = pd.read_sql_query(text("SELECT * FROM schedule"), conn)
    st.dataframe(sched, use_container_width=True)

# 3. РАСХОДЫ
with t3:
    st.subheader("Учет затрат")
    with st.form("add_exp"):
        e_amt = st.number_input("Сумма", min_value=0.0)
        e_cat = st.selectbox("Категория", ["Аренда", "Маркетинг", "ЗП", "Налоги", "Сервисы", "Прочее"])
        e_dt = st.date_input("Дата")
        if st.form_submit_button("Записать расход"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)"),
                          {"a": e_amt, "c": e_cat, "d": e_dt})
                conn.commit()
            st.rerun()
    
    with engine.connect() as conn:
        # Убираем жесткую сортировку, чтобы не вылетала ошибка из-за имен колонок
        try:
            exp_list = pd.read_sql_query(text("SELECT * FROM expenses ORDER BY id DESC"), conn)
        except:
            exp_list = pd.read_sql_query(text("SELECT * FROM expenses"), conn)
    st.dataframe(exp_list, use_container_width=True)

# 4. КАРТОЧКА КЛИЕНТА
with t4:
    st.subheader("Детальная информация")
    if not cl_df.empty:
        sel_name = st.selectbox("Выберите клиента", cl_df['name'])
        curr_cid = int(cl_df[cl_df['name'] == sel_name]['id'].iloc[0])
        
        tab_fin, tab_doc = st.tabs(["💰 Финансы", "📄 Документы"])
        
        with tab_fin:
            with engine.connect() as conn:
                p_hist = pd.read_sql_query(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": curr_cid})
            st.table(p_hist)
            
        with tab_doc:
            with st.expander("➕ Прикрепить ссылку"):
                d_n = st.text_input("Название")
                d_u = st.text_input("URL")
                if st.button("Сохранить"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:cid, :n, :u)"),
                                  {"cid": curr_cid, "n": d_n, "u": d_u})
                        conn.commit()
                    st.rerun()
            
            with engine.connect() as conn:
                docs = pd.read_sql_query(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": curr_cid})
            for _, d in docs.iterrows():
                c_txt, c_btn, c_del = st.columns([3,1,1])
                c_txt.write(f"📎 {d['file_name']}")
                c_btn.link_button("Открыть", d['file_url'])
                if st.session_state.role == "admin":
                    if c_del.button("🗑️", key=f"del_{d['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": int(d['id'])})
                            conn.commit()
                        st.rerun()

# 5. АНАЛИТИКА
with t5:
    if st.session_state.role == "admin":
        st.subheader("Визуализация данных")
        with engine.connect() as conn:
            inc = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status='paid'")).scalar() or 0
            exp = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
            e_df = pd.read_sql_query(text("SELECT category, SUM(amount) as total FROM expenses GROUP BY category"), conn)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Доход (оплачено)", f"{inc} ₽")
        c2.metric("Расходы", f"{exp} ₽")
        c3.metric("Прибыль", f"{inc - exp} ₽")
        
        if not e_df.empty:
            fig = px.pie(e_df, values='total', names='category', title="Структура расходов")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Доступ только для администратора")
