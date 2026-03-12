import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="CRM Система", layout="wide", page_icon="📊")

# Пароли (лучше прописать в Streamlit Secrets)
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
STAFF_PASSWORD = st.secrets.get("STAFF_PASSWORD", "staff123")
DB_URL = st.secrets["DB_URL"]

engine = create_engine(DB_URL)

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

# --- ФУНКЦИИ ---
def run_query(query, params=None):
    with engine.connect() as conn:
        res = conn.execute(text(query), params or {})
        conn.commit()
        return res

# --- ИНТЕРФЕЙС ---
st.sidebar.title(f"👤 {st.session_state.role.upper()}")
if st.sidebar.button("Выйти"):
    st.session_state.authenticated = False
    st.rerun()

tabs = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# 1. РЕЕСТР КЛИЕНТОВ
with tabs[0]:
    st.subheader("Управление клиентами")
    with st.expander("➕ Добавить нового клиента"):
        with st.form("add_client"):
            name = st.text_input("Имя / Компания")
            phone = st.text_input("Телефон")
            if st.form_submit_button("Создать"):
                run_query("INSERT INTO clients (name, phone) VALUES (:n, :p)", {"n": name, "p": phone})
                st.success("Готово!")
                st.rerun()
    
    clients = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", engine)
    st.dataframe(clients, use_container_width=True)

# 2. КАЛЕНДАРЬ ПЛАТЕЖЕЙ
with tabs[1]:
    st.subheader("План поступлений")
    cl_df = pd.read_sql("SELECT id, name FROM clients", engine)
    
    with st.expander("📅 Запланировать приход"):
        with st.form("add_sch"):
            c_id = st.selectbox("Клиент", cl_df['id'], format_func=lambda x: cl_df[cl_df['id']==x]['name'].values[0])
            amt = st.number_input("Сумма", min_value=0)
            dt = st.date_input("Дата")
            comm = st.text_input("Комментарий")
            if st.form_submit_button("Добавить"):
                run_query("INSERT INTO schedule (client_id, amount, planned_date, comment) VALUES (:cid, :a, :d, :c)",
                          {"cid": c_id, "a": amt, "d": dt, "c": comm})
                st.rerun()
    
    sched = pd.read_sql("SELECT s.*, c.name as client_name FROM schedule s JOIN clients c ON s.client_id = c.id", engine)
    st.dataframe(sched, use_container_width=True)

# 3. РАСХОДЫ
with tabs[2]:
    st.subheader("Учет затрат")
    with st.form("add_exp"):
        e_amt = st.number_input("Сумма", min_value=0)
        e_cat = st.selectbox("Категория", ["Аренда", "Маркетинг", "ЗП", "Налоги", "Сервисы", "Прочее"])
        e_dt = st.date_input("Дата")
        if st.form_submit_button("Записать расход"):
            run_query("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)",
                      {"a": e_amt, "c": e_cat, "d": e_dt})
            st.rerun()

# 4. КАРТОЧКА КЛИЕНТА + ДОКУМЕНТЫ
with tabs[3]:
    st.subheader("Детальная информация")
    if not cl_df.empty:
        sel_name = st.selectbox("Выберите клиента для просмотра", cl_df['name'])
        curr_cid = int(cl_df[cl_df['name'] == sel_name]['id'].iloc[0])
        
        c1, c2 = st.tabs(["💰 История оплат", "📄 Документы и Ссылки"])
        
        with c1:
            p_hist = pd.read_sql(text("SELECT amount, planned_date, status FROM schedule WHERE client_id = :id"), engine, params={"id": curr_cid})
            st.table(p_hist)
            
        with c2:
            # Блок ссылок на документы
            with st.expander("➕ Прикрепить ссылку на договор/файл"):
                d_n = st.text_input("Название документа")
                d_u = st.text_input("Ссылка (Google Drive/Dropbox)")
                if st.button("Прикрепить"):
                    run_query("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:cid, :n, :u)",
                              {"cid": curr_cid, "n": d_n, "u": d_u})
                    st.rerun()
            
            docs = pd.read_sql(text("SELECT id, file_name, file_url FROM client_documents WHERE client_id = :id"), engine, params={"id": curr_cid})
            for _, d in docs.iterrows():
                cols = st.columns([3, 1, 1])
                cols[0].write(f"📎 {d['file_name']}")
                cols[1].link_button("Открыть", d['file_url'])
                if st.session_state.role == "admin":
                    if cols[2].button("🗑️", key=f"del_{d['id']}"):
                        run_query("DELETE FROM client_documents WHERE id = :id", {"id": d['id']})
                        st.rerun()

# 5. АНАЛИТИКА (ТОЛЬКО ДЛЯ АДМИНА)
with tabs[4]:
    if st.session_state.role == "admin":
        st.subheader("Визуализация данных")
        
        # Считаем итоги
        inc_total = pd.read_sql("SELECT SUM(amount) FROM schedule WHERE status='paid'", engine).iloc[0,0] or 0
        exp_total = pd.read_sql("SELECT SUM(amount) FROM expenses", engine).iloc[0,0] or 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Общий доход", f"{inc_total} ₽")
        m2.metric("Расходы", f"{exp_total} ₽")
        m3.metric("Чистая прибыль", f"{inc_total - exp_total} ₽")
        
        # График расходов
        exp_df = pd.read_sql("SELECT category, SUM(amount) as total FROM expenses GROUP BY category", engine)
        if not exp_df.empty:
            fig = px.pie(exp_df, values='total', names='category', title="Структура расходов")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ У вас нет прав для просмотра аналитики.")
