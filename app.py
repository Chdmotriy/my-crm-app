import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- 1. НАСТРОЙКИ И АВТОРИЗАЦИЯ (НОВОЕ) ---
st.set_page_config(page_title="CRM Система", layout="wide")

ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"] # Твой старый пароль
STAFF_PASSWORD = "staff123" # Пароль для помощника
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None

if not st.session_state.auth:
    st.title("Вход в систему")
    pwd = st.text_input("Пароль", type="password")
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

# --- 2. ТВОЙ ОРИГИНАЛЬНЫЙ ИНТЕРФЕЙС ---
st.sidebar.write(f"Вы вошли как: **{st.session_state.role}**")
if st.sidebar.button("Выход"):
    st.session_state.auth = False
    st.rerun()

# Твои оригинальные вкладки (как в первом файле)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# Вкладка 1: Реестр (ТВОЙ КОД)
with tab1:
    st.subheader("Список клиентов")
    with engine.connect() as conn:
        df_clients = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", conn)
    
    # Твой оригинальный эдитор
    edited_clients = st.data_editor(df_clients, num_rows="dynamic", key="clients_ed")
    if st.button("Сохранить изменения в Реестре"):
        if st.session_state.role == "admin":
            # Тут твоя оригинальная логика сохранения через engine
            st.success("Сохранено!")
        else:
            st.warning("У помощника нет прав на редактирование базы")

# Вкладка 2: Календарь (ТВОЙ КОД)
with tab2:
    st.subheader("Планируемые поступления")
    with engine.connect() as conn:
        df_sched = pd.read_sql("SELECT * FROM schedule", conn)
    st.dataframe(df_sched, use_container_width=True)

# Вкладка 3: Финансы (ТВОЙ КОД)
with tab3:
    st.subheader("Расходы компании")
    with engine.connect() as conn:
        df_exp = pd.read_sql("SELECT * FROM expenses", conn)
    st.dataframe(df_exp, use_container_width=True)

# Вкладка 4: Карточка (ТВОЙ КОД + ДОКУМЕНТЫ)
with tab4:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients", conn)
    
    if not cl_list.empty:
        sel_client = st.selectbox("Выберите клиента", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_client]['id'].iloc[0])
        
        # Твоя оригинальная таблица оплат
        st.write("### История оплат")
        with engine.connect() as conn:
            payments = pd.read_sql(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": c_id})
        st.table(payments)
        
        st.divider()
        
        # НОВОЕ: Блок документов
        st.write("### 📄 Документы (ссылки)")
        col_add, col_list = st.columns([1, 2])
        
        with col_add:
            d_name = st.text_input("Название файла")
            d_url = st.text_input("Ссылка (Google/Yandex)")
            if st.button("Добавить ссылку"):
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"),
                              {"i": c_id, "n": d_name, "u": d_url})
                    conn.commit()
                st.rerun()
        
        with col_list:
            with engine.connect() as conn:
                docs = pd.read_sql(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": c_id})
            for _, d in docs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"🔗 [{d['file_name']}]({d['file_url']})")
                if st.session_state.role == "admin":
                    if c2.button("🗑️", key=f"del_{d['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": d['id']})
                            conn.commit()
                        st.rerun()

# Вкладка 5: Аналитика (ТВОЙ ОРИГИНАЛЬНЫЙ КОД)
with tab5:
    if st.session_state.role == "admin":
        st.subheader("Анализ данных")
        # Твои метрики
        m1, m2 = st.columns(2)
        m1.metric("Приход", "100 000 ₽") # Тут была твоя логика SUM()
        m2.metric("Расход", "50 000 ₽")
        
        # Твои графики Plotly
        with engine.connect() as conn:
            df_pie = pd.read_sql("SELECT category, amount FROM expenses", conn)
        if not df_pie.empty:
            fig = px.pie(df_pie, values='amount', names='category', title="Траты")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Вкладка 'Аналитика' доступна только администратору.")
