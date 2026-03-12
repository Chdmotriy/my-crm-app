import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# --- НАСТРОЙКИ И ПАРОЛИ ---
# Добавь эти пароли в Secrets на Streamlit Cloud или используй эти по умолчанию
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "admin123")
STAFF_PASSWORD = st.secrets.get("STAFF_PASSWORD", "staff123")
DB_URL = st.secrets["DB_URL"]

engine = create_engine(DB_URL)

st.set_page_config(page_title="CRM Система", layout="wide")

# --- АВТОРИЗАЦИЯ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("Вход в CRM")
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

# --- ФУНКЦИИ БАЗЫ ---
def run_query(query, params=None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result

# --- ИНТЕРФЕЙС ---
st.title(f"🚀 Моя CRM ({'Админ' if st.session_state.role == 'admin' else 'Помощник'})")

tabs = st.tabs(["👥 Клиенты", "🗓️ График платежей", "📉 Расходы", "🗂️ Карточка клиента", "📊 Отчеты"])

# 1. КЛИЕНТЫ
with tabs[0]:
    st.subheader("Добавить нового клиента")
    with st.form("new_client"):
        c_name = st.text_input("Имя/Название")
        c_phone = st.text_input("Телефон")
        if st.form_submit_button("Сохранить"):
            run_query("INSERT INTO clients (name, phone) VALUES (:n, :p)", {"n": c_name, "p": c_phone})
            st.success("Клиент добавлен")
            st.rerun()
    
    st.subheader("Список клиентов")
    clients_df = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", engine)
    st.dataframe(clients_df, use_container_width=True)

# 2. ГРАФИК ПЛАТЕЖЕЙ (ПРИХОД)
with tabs[1]:
    st.subheader("Запланировать приход денег")
    clients_list = pd.read_sql("SELECT id, name FROM clients", engine)
    with st.form("new_payment"):
        c_id = st.selectbox("Клиент", clients_list['id'], format_func=lambda x: clients_list[clients_list['id']==x]['name'].values[0])
        amount = st.number_input("Сумма", min_value=0)
        p_date = st.date_input("Дата ожидания")
        comment = st.text_input("Комментарий")
        if st.form_submit_button("Добавить в график"):
            run_query("INSERT INTO schedule (client_id, amount, planned_date, comment) VALUES (:cid, :a, :d, :c)",
                      {"cid": c_id, "a": amount, "d": p_date, "c": comment})
            st.success("Платёж добавлен")
            st.rerun()

    st.subheader("Предстоящие оплаты")
    sched_df = pd.read_sql("SELECT s.*, c.name FROM schedule s JOIN clients c ON s.client_id = c.id WHERE status='pending'", engine)
    st.dataframe(sched_df, use_container_width=True)

# 3. РАСХОДЫ
with tabs[2]:
    st.subheader("Учет расходов")
    with st.form("new_expense"):
        exp_amount = st.number_input("Сумма расхода", min_value=0)
        exp_cat = st.selectbox("Категория", ["Аренда", "ЗП", "Маркетинг", "Налоги", "Прочее"])
        exp_date = st.date_input("Дата")
        if st.form_submit_button("Записать расход"):
            run_query("INSERT INTO expenses (amount, category, expense_date) VALUES (:a, :c, :d)",
                      {"a": exp_amount, "c": exp_cat, "d": exp_date})
            st.rerun()

# 4. КАРТОЧКА КЛИЕНТА (ДЕТАЛИ + ДОКУМЕНТЫ)
with tabs[3]:
    st.subheader("История по клиенту")
    cl_choice = pd.read_sql("SELECT id, name FROM clients", engine)
    if not cl_choice.empty:
        selected_client = st.selectbox("Выберите клиента", cl_choice['name'])
        curr_id = int(cl_choice[cl_choice['name'] == selected_client]['id'].iloc[0])
        
        sub_tabs = st.tabs(["💰 Финансы", "📄 Документы"])
        
        with sub_tabs[0]:
            payments = pd.read_sql(text("SELECT * FROM schedule WHERE client_id = :id"), engine, params={"id": curr_id})
            st.write("История платежей:")
            st.table(payments)
        
        with sub_tabs[1]:
            st.write("### Ссылки на договора (Google Drive / Облако)")
            # Форма добавления ссылки
            with st.expander("➕ Добавить новый документ"):
                d_name = st.text_input("Название (например, Договор №5)")
                d_url = st.text_input("Ссылка на файл")
                if st.button("Сохранить ссылку"):
                    if d_name and d_url:
                        run_query("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:cid, :n, :u)",
                                 {"cid": curr_id, "n": d_name, "u": d_url})
                        st.success("Добавлено!")
                        st.rerun()
            
            # Список ссылок
            docs = pd.read_sql(text("SELECT * FROM client_documents WHERE client_id = :id"), engine, params={"id": curr_id})
            for _, doc in docs.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"🔹 {doc['file_name']}")
                col2.link_button("Открыть", doc['file_url'])
                # КНОПКА УДАЛЕНИЯ ТОЛЬКО ДЛЯ АДМИНА
                if st.session_state.role == "admin":
                    if col3.button("🗑️", key=f"del_{doc['id']}"):
                        run_query("DELETE FROM client_documents WHERE id = :id", {"id": doc['id']})
                        st.rerun()

# 5. ОТЧЕТЫ (ТОЛЬКО ДЛЯ АДМИНА)
with tabs[4]:
    if st.session_state.role == "admin":
        st.subheader("Финансовый результат")
        inc = pd.read_sql("SELECT SUM(amount) FROM schedule WHERE status='paid'", engine).iloc[0,0] or 0
        exp = pd.read_sql("SELECT SUM(amount) FROM expenses", engine).iloc[0,0] or 0
        st.metric("Прибыль", f"{inc - exp} руб.", delta=f"Доход: {inc}")
    else:
        st.warning("У вас нет доступа к финансовой аналитике.")

# --- КНОПКА ВЫХОДА ---
if st.sidebar.button("Выйти из системы"):
    st.session_state.authenticated = False
    st.rerun()
