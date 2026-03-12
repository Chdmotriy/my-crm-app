import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- ИНИЦИАЛИЗАЦИЯ И НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Система", layout="wide", page_icon="📈")

ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
STAFF_PASSWORD = st.secrets.get("STAFF_PASSWORD", "staff123")
DB_URL = st.secrets["DB_URL"]

engine = create_engine(DB_URL)

# Проверка/создание таблицы документов (если её еще нет)
with engine.connect() as conn:
    conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT, upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
    conn.commit()

# --- АВТОРИЗАЦИЯ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("🔐 Вход в CRM")
    pwd = st.text_input("Введите пароль", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.authenticated, st.session_state.role = True, "admin"
            st.rerun()
        elif pwd == STAFF_PASSWORD:
            st.session_state.authenticated, st.session_state.role = True, "assistant"
            st.rerun()
        else:
            st.error("Неверный пароль")
    st.stop()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
st.sidebar.title(f"👤 {st.session_state.role.upper()}")
if st.sidebar.button("Выход"):
    st.session_state.authenticated = False
    st.rerun()

# Твои оригинальные вкладки
tabs = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# 1. РЕЕСТР КЛИЕНТОВ
with tabs[0]:
    st.subheader("Список клиентов")
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            c_name = st.text_input("Имя / Организация")
            c_phone = st.text_input("Телефон")
            if st.form_submit_button("Создать"):
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO clients (name, phone) VALUES (:n, :p)"), {"n": c_name, "p": c_phone})
                    conn.commit()
                st.rerun()
    
    with engine.connect() as conn:
        clients_df = pd.read_sql_query(text("SELECT * FROM clients ORDER BY id DESC"), conn)
    st.dataframe(clients_df, use_container_width=True)

# 2. КАЛЕНДАРЬ ПЛАТЕЖЕЙ
with tabs[1]:
    st.subheader("Предстоящие поступления")
    with engine.connect() as conn:
        cl_list = pd.read_sql_query(text("SELECT id, name FROM clients"), conn)
    
    with st.expander("📅 Запланировать оплату"):
        with st.form("add_sched"):
            sel_cid = st.selectbox("Выберите клиента", cl_list['id'], format_func=lambda x: cl_list[cl_list['id']==x]['name'].values[0])
            s_amt = st.number_input("Сумма", min_value=0.0)
            s_date = st.date_input("Дата ожидания")
            s_comm = st.text_input("Комментарий")
            if st.form_submit_button("Добавить в план"):
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO schedule (client_id, amount, planned_date, comment) VALUES (:i, :a, :d, :c)"),
                              {"i": int(sel_cid), "a": s_amt, "d": s_date, "c": s_comm})
                    conn.commit()
                st.rerun()
    
    with engine.connect() as conn:
        sched_df = pd.read_sql_query(text("SELECT s.*, c.name as client_name FROM schedule s LEFT JOIN clients c ON s.client_id = c.id"), conn)
    st.dataframe(sched_df, use_container_width=True)

# 3. ФИНАНСЫ (РАСХОДЫ)
with tabs[2]:
    st.subheader("Учет расходов")
    with st.form("add_exp"):
        col1, col2, col3 = st.columns(3)
        e_amt = col1.number_input("Сумма", min_value=0.0)
        e_cat = col2.selectbox("Категория", ["ЗП", "Маркетинг", "Аренда", "Налоги", "Прочее"])
        e_date = col3.date_input("Дата")
        if st.form_submit_button("Записать расход"):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)"),
                          {"a": e_amt, "c": e_cat, "d": e_date})
                conn.commit()
            st.rerun()
    
    with engine.connect() as conn:
        expenses_df = pd.read_sql_query(text("SELECT * FROM expenses ORDER BY expense_date DESC"), conn)
    st.dataframe(expenses_df, use_container_width=True)

# 4. КАРТОЧКА КЛИЕНТА (ДЕТАЛИ + ДОКУМЕНТЫ)
with tabs[3]:
    st.subheader("История и документы")
    if not cl_list.empty:
        selected_client_name = st.selectbox("Поиск клиента", cl_list['name'])
        curr_id = int(cl_list[cl_list['name'] == selected_client_name]['id'].iloc[0])
        
        c_p, c_d = st.tabs(["💰 Платежи", "📄 Договоры и Ссылки"])
        
        with c_p:
            with engine.connect() as conn:
                p_hist = pd.read_sql_query(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": curr_id})
            st.table(p_hist)
            
        with c_d:
            with st.expander("➕ Прикрепить новую ссылку"):
                doc_n = st.text_input("Название (Договор №...)")
                doc_u = st.text_input("Ссылка на облако")
                if st.button("Сохранить ссылку"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"),
                                  {"i": curr_id, "n": doc_n, "u": doc_u})
                        conn.commit()
                    st.rerun()
            
            with engine.connect() as conn:
                docs = pd.read_sql_query(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": curr_cid if 'curr_cid' in locals() else curr_id})
            for _, d in docs.iterrows():
                col_n, col_b, col_del = st.columns([3, 1, 1])
                col_n.write(f"📎 {d['file_name']}")
                col_b.link_button("Открыть", d['file_url'])
                if st.session_state.role == "admin":
                    if col_del.button("🗑️", key=f"del_{d['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": int(d['id'])})
                            conn.commit()
                        st.rerun()

# 5. АНАЛИТИКА (ТОЛЬКО АДМИН)
with tabs[4]:
    if st.session_state.role == "admin":
        st.subheader("Финансовый результат")
        with engine.connect() as conn:
            # Метрики
            total_inc = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status='paid'")).scalar() or 0
            total_exp = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Доход", f"{total_inc} ₽")
            m2.metric("Расход", f"{total_exp} ₽")
            m3.metric("Прибыль", f"{total_inc - total_exp} ₽")
            
            # Графики
            exp_df = pd.read_sql_query(text("SELECT category, SUM(amount) as total FROM expenses GROUP BY category"), conn)
            if not exp_df.empty:
                fig = px.pie(exp_df, values='total', names='category', title="Траты по категориям", hole=0.3)
                st.plotly_chart(fig, use_container_width=True)
            
            # Твой оригинальный график по датам
            daily_exp = pd.read_sql_query(text("SELECT expense_date, SUM(amount) as total FROM expenses GROUP BY expense_date ORDER BY expense_date"), conn)
            if not daily_exp.empty:
                fig2 = px.line(daily_exp, x='expense_date', y='total', title="Динамика расходов")
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("⚠️ У вас нет прав для просмотра аналитики.")
