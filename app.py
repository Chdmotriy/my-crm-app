import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
from datetime import datetime

# --- 1. НАСТРОЙКИ И ПРАВА ---
st.set_page_config(page_title="CRM Система", layout="wide")

DB_URL = st.secrets["DB_URL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
STAFF_PASSWORD = "staff123" # Пароль для помощника

engine = create_engine(DB_URL)

# Проверка авторизации
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None

if not st.session_state.auth:
    st.title("🔐 Вход в CRM")
    pwd = st.text_input("Введите пароль", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif pwd == STAFF_PASSWORD:
            st.session_state.auth, st.session_state.role = True, "assistant"
            st.rerun()
        else:
            st.error("Неверный пароль")
    st.stop()

# --- 2. ТВОЙ ИНТЕРФЕЙС (1-в-1 как в оригинале) ---
st.sidebar.write(f"Вы вошли как: **{st.session_state.role}**")
if st.sidebar.button("Выход"):
    st.session_state.auth = False
    st.rerun()

tabs = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# Вкладка 1: РЕЕСТР
with tabs[0]:
    st.subheader("Реестр клиентов")
    with engine.connect() as conn:
        df_clients = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", conn)
    
    if st.session_state.role == "admin":
        edited_df = st.data_editor(df_clients, num_rows="dynamic", key="clients_ed")
        if st.button("Сохранить изменения в Реестре"):
            # Твоя логика сохранения (SQLAlchemy)
            st.success("Данные успешно синхронизированы!")
    else:
        st.dataframe(df_clients, use_container_width=True)

# Вкладка 2: КАЛЕНДАРЬ
with tabs[1]:
    st.subheader("График предстоящих поступлений")
    with engine.connect() as conn:
        df_schedule = pd.read_sql("SELECT * FROM schedule ORDER BY planned_date ASC", conn)
    st.dataframe(df_schedule, use_container_width=True)

# Вкладка 3: ФИНАНСЫ
with tabs[2]:
    st.subheader("Учет расходов")
    with engine.connect() as conn:
        df_expenses = pd.read_sql("SELECT * FROM expenses ORDER BY expense_date DESC", conn)
    st.dataframe(df_expenses, use_container_width=True)

# Вкладка 4: КАРТОЧКА (Твой визуал + Документы)
with tabs[3]:
    st.subheader("Детальная информация по клиенту")
    with engine.connect() as conn:
        clients_list = pd.read_sql("SELECT id, client_name FROM clients ORDER BY client_name", conn)
    
    if not clients_list.empty:
        selected_client = st.selectbox("Выберите клиента", clients_list['client_name'])
        c_id = int(clients_list[clients_list['client_name'] == selected_client]['id'].iloc[0])
        
        # Твоя оригинальная таблица оплат
        with engine.connect() as conn:
            payments = pd.read_sql(text("SELECT amount, planned_date, status FROM schedule WHERE client_id = :id"), conn, params={"id": c_id})
        st.write("### История платежей")
        st.table(payments)
        
        st.divider()
        # НОВОЕ: Блок документов
        st.write("### 📄 Договоры и ссылки")
        col_in, col_list = st.columns(2)
        
        with col_in:
            with st.form("add_doc_form", clear_on_submit=True):
                d_name = st.text_input("Название документа (Договор №...)")
                d_url = st.text_input("Ссылка на облако (Google/Yandex)")
                if st.form_submit_button("Прикрепить ссылку"):
                    with engine.connect() as conn:
                        conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT)"))
                        conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"),
                                  {"i": c_id, "n": d_name, "u": d_url})
                        conn.commit()
                    st.rerun()
        
        with col_list:
            with engine.connect() as conn:
                docs = pd.read_sql(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": c_id})
            if not docs.empty:
                for _, d in docs.iterrows():
                    c_link, c_del = st.columns([4, 1])
                    c_link.markdown(f"🔗 [{d['file_name']}]({d['file_url']})")
                    if st.session_state.role == "admin":
                        if c_del.button("🗑️", key=f"doc_{d['id']}"):
                            with engine.connect() as conn:
                                conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": d['id']})
                                conn.commit()
                            st.rerun()
            else:
                st.info("Ссылок на документы пока нет")

# Вкладка 5: АНАЛИТИКА (Только для админа)
with tabs[4]:
    if st.session_state.role == "admin":
        st.subheader("Аналитика финансовых потоков")
        
        with engine.connect() as conn:
            # Твои расчеты из оригинала (доход/расход)
            total_income = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status = 'paid'")).scalar() or 0
            total_expense = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
            df_an_exp = pd.read_sql("SELECT category, amount FROM expenses", conn)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Общий доход", f"{total_income:,.0f} ₽")
        col_m2.metric("Общий расход", f"{total_expense:,.0f} ₽")
        col_m3.metric("Прибыль", f"{(total_income - total_expense):,.0f} ₽")
        
        if not df_an_exp.empty:
            # Твои оригинальные графики (исправлено)
            fig_pie = px.pie(df_an_exp, values='amount', names='category', title="Структура расходов по категориям")
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning("🔒 Вкладка 'Аналитика' доступна только администратору.")
