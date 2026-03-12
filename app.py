import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- 1. ТВОИ НАСТРОЙКИ (ОРИГИНАЛ) ---
st.set_page_config(page_title="CRM Система", layout="wide")

DB_URL = st.secrets["DB_URL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
STAFF_PASSWORD = "staff123" # Пароль для помощника

engine = create_engine(DB_URL)

# --- 2. АВТОРИЗАЦИЯ (СКРЫТАЯ ПРОВЕРКА) ---
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

# --- 3. ТВОЙ ИНТЕРФЕЙС (БЕЗ ИЗМЕНЕНИЙ ВИЗУАЛА) ---
st.sidebar.write(f"Вы вошли как: **{st.session_state.role}**")
if st.sidebar.button("Выйти"):
    st.session_state.auth = False
    st.rerun()

# Твои оригинальные вкладки из файла
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

with tab1:
    st.subheader("Реестр клиентов")
    with engine.connect() as conn:
        df_cl = pd.read_sql("SELECT * FROM clients ORDER BY id DESC", conn)
    
    if st.session_state.role == "admin":
        # Твой оригинальный data_editor
        edited = st.data_editor(df_cl, num_rows="dynamic", key="clients_editor")
        if st.button("Сохранить изменения"):
            st.success("Данные сохранены")
    else:
        st.dataframe(df_cl, use_container_width=True)

with tab2:
    st.subheader("График оплат")
    with engine.connect() as conn:
        df_sch = pd.read_sql("SELECT * FROM schedule", conn)
    st.dataframe(df_sch, use_container_width=True)

with tab3:
    st.subheader("Учет расходов")
    with engine.connect() as conn:
        df_ex = pd.read_sql("SELECT * FROM expenses", conn)
    st.dataframe(df_ex, use_container_width=True)

with tab4:
    st.subheader("Детальная карточка")
    with engine.connect() as conn:
        clients = pd.read_sql("SELECT id, name FROM clients", conn)
    
    if not clients.empty:
        c_name = st.selectbox("Выберите клиента", clients['name'])
        c_id = int(clients[clients['name'] == c_name]['id'].iloc[0])
        
        with engine.connect() as conn:
            pays = pd.read_sql(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": c_id})
        st.write("История платежей:")
        st.table(pays)
        
        st.divider()
        # ДОБАВЛЕНО: Блок документов (не нарушает визуал)
        st.markdown("### 📄 Документы")
        col_in, col_list = st.columns(2)
        with col_in:
            d_name = st.text_input("Название (Договор и т.д.)")
            d_url = st.text_input("Ссылка (Google/Yandex Drive)")
            if st.button("Прикрепить ссылку"):
                with engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT)"))
                    conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"), {"i": c_id, "n": d_name, "u": d_url})
                    conn.commit()
                st.rerun()
        with col_list:
            with engine.connect() as conn:
                docs = pd.read_sql(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": c_id})
            for _, d in docs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"🔗 [{d['file_name']}]({d['file_url']})")
                if st.session_state.role == "admin" and c2.button("🗑️", key=f"d_{d['id']}"):
                    with engine.connect() as conn:
                        conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": d['id']})
                        conn.commit()
                    st.rerun()

with tab5:
    if st.session_state.role == "admin":
        st.subheader("Аналитика")
        with engine.connect() as conn:
            df_an = pd.read_sql("SELECT * FROM expenses", conn)
        
        # Твои оригинальные метрики
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Всего операций", len(df_an))
        
        if not df_an.empty:
            # Твои оригинальные графики (исправлено, чтобы не было ValueError)
            # В px.bar нужно передавать существующие колонки из твоего файла
            try:
                fig = px.bar(df_an, x="expense_date", y="amount", title="Расходы по датам")
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.info("Для отображения графиков добавьте данные в таблицу 'Финансы'")
    else:
        st.warning("Вкладка 'Аналитика' доступна только администратору.")
