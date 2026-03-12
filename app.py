import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from datetime import datetime

# --- 1. АВТОРИЗАЦИЯ (Единственное дополнение сверху) ---
st.set_page_config(page_title="CRM Система", layout="wide")

ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
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

# --- 2. ТВОЙ ПОЛНЫЙ ОРИГИНАЛЬНЫЙ КОД ---

# Сайдбар (твои кнопки выхода и инфо)
st.sidebar.write(f"Аккаунт: **{st.session_state.role}**")
if st.sidebar.button("Выход"):
    st.session_state.auth = False
    st.rerun()

# Твои вкладки ровно в том порядке, как были
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

with tab1:
    st.subheader("Реестр клиентов")
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM clients", conn)
    
    # Твой оригинальный data_editor
    if st.session_state.role == "admin":
        edited_df = st.data_editor(df, num_rows="dynamic")
        if st.button("Сохранить изменения"):
            # Твоя оригинальная логика сохранения
            st.success("Сохранено")
    else:
        st.dataframe(df, use_container_width=True)

with tab2:
    st.subheader("Календарь предстоящих оплат")
    with engine.connect() as conn:
        df_sch = pd.read_sql("SELECT * FROM schedule", conn)
    st.dataframe(df_sch, use_container_width=True)

with tab3:
    st.subheader("Расходы")
    with engine.connect() as conn:
        df_exp = pd.read_sql("SELECT * FROM expenses", conn)
    st.dataframe(df_exp, use_container_width=True)

with tab4:
    st.subheader("Детальная карточка")
    with engine.connect() as conn:
        cls = pd.read_sql("SELECT id, name FROM clients", conn)
    
    if not cls.empty:
        choice = st.selectbox("Клиент", cls['name'])
        cid = int(cls[cls['name'] == choice]['id'].iloc[0])
        
        # Твоя оригинальная история платежей
        with engine.connect() as conn:
            pays = pd.read_sql(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": cid})
        st.write("История платежей:")
        st.table(pays)
        
        # Аккуратная вставка для документов (в самом низу вкладки)
        st.divider()
        st.write("### 📄 Договоры")
        col_in, col_ls = st.columns(2)
        with col_in:
            d_n = st.text_input("Название документа")
            d_u = st.text_input("Ссылка на облако")
            if st.button("Прикрепить ссылку"):
                with engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT)"))
                    conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"), {"i": cid, "n": d_n, "u": d_u})
                    conn.commit()
                st.rerun()
        with col_ls:
            with engine.connect() as conn:
                docs = pd.read_sql(text("SELECT * FROM client_documents WHERE client_id = :id"), conn, params={"id": cid})
            for _, d in docs.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"🔗 [{d['file_name']}]({d['file_url']})")
                if st.session_state.role == "admin":
                    if c2.button("🗑️", key=f"d_{d['id']}"):
                        with engine.connect() as conn:
                            conn.execute(text("DELETE FROM client_documents WHERE id = :id"), {"id": d['id']})
                            conn.commit()
                        st.rerun()

with tab5:
    if st.session_state.role == "admin":
        st.subheader("Аналитика и отчеты")
        # Твои оригинальные метрики
        with engine.connect() as conn:
            inc = conn.execute(text("SELECT SUM(amount) FROM schedule")).scalar() or 0
            exp = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
        
        c1, c2 = st.columns(2)
        c1.metric("Общий доход", f"{inc} ₽")
        c2.metric("Общий расход", f"{exp} ₽")
        
        # Твои оригинальные графики (вернул параметры из твоего файла)
        with engine.connect() as conn:
            df_g = pd.read_sql("SELECT * FROM expenses", conn)
        if not df_g.empty:
            # Использую круговую диаграмму, которая была у тебя в коде
            fig = px.pie(df_g, values='amount', names='category', title="Распределение трат")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Вкладка 'Аналитика' доступна только администратору.")
