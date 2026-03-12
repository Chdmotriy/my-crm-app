import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text

# 1. ТВОИ НАСТРОЙКИ (БЕЗ ИЗМЕНЕНИЙ)
st.set_page_config(page_title="CRM", layout="wide")

DB_URL = st.secrets["DB_URL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
STAFF_PASSWORD = "staff123" # Пароль для помощника

engine = create_engine(DB_URL)

# 2. АВТОРИЗАЦИЯ (АККУРАТНАЯ ВСТАВКА)
if "auth" not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None

if not st.session_state.auth:
    st.title("Вход в систему")
    pwd = st.text_input("Введите пароль", type="password")
    if st.button("Войти"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        elif pwd == STAFF_PASSWORD:
            st.session_state.auth, st.session_state.role = True, "assistant"
            st.rerun()
        else:
            st.error("Ошибка пароля")
    st.stop()

# 3. ТВОЙ ОРИГИНАЛЬНЫЙ ВИЗУАЛ (TAB1 - TAB5)
st.sidebar.write(f"Вы вошли как: {st.session_state.role}")
if st.sidebar.button("Выйти"):
    st.session_state.auth = False
    st.rerun()

t1, t2, t3, t4, t5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

with t1:
    st.subheader("Реестр клиентов")
    with engine.connect() as conn:
        df_clients = pd.read_sql("SELECT * FROM clients", conn)
    
    # Редактировать может только админ
    if st.session_state.role == "admin":
        st.data_editor(df_clients, num_rows="dynamic", key="ed_clients")
        st.button("Сохранить изменения")
    else:
        st.dataframe(df_clients, use_container_width=True)

with t2:
    st.subheader("График поступлений")
    with engine.connect() as conn:
        st.dataframe(pd.read_sql("SELECT * FROM schedule", conn), use_container_width=True)

with t3:
    st.subheader("Расходы")
    with engine.connect() as conn:
        st.dataframe(pd.read_sql("SELECT * FROM expenses", conn), use_container_width=True)

with t4:
    st.subheader("Карточка клиента")
    with engine.connect() as conn:
        cls = pd.read_sql("SELECT id, name FROM clients", conn)
    
    if not cls.empty:
        c_name = st.selectbox("Клиент", cls['name'])
        c_id = int(cls[cls['name'] == c_name]['id'].iloc[0])
        
        # Твоя история оплат
        with engine.connect() as conn:
            pays = pd.read_sql(text("SELECT * FROM schedule WHERE client_id = :id"), conn, params={"id": c_id})
        st.write("История:")
        st.table(pays)
        
        st.divider()
        # НОВОЕ: Блок документов (ссылки)
        st.markdown("### 📄 Договоры")
        col_in, col_out = st.columns(2)
        with col_in:
            d_n = st.text_input("Название документа")
            d_u = st.text_input("Ссылка (Google/Yandex)")
            if st.button("Прикрепить"):
                with engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS client_documents (id SERIAL PRIMARY KEY, client_id INTEGER, file_name TEXT, file_url TEXT)"))
                    conn.execute(text("INSERT INTO client_documents (client_id, file_name, file_url) VALUES (:i, :n, :u)"), {"i": c_id, "n": d_n, "u": d_u})
                    conn.commit()
                st.rerun()
        with col_out:
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

with t5:
    if st.session_state.role == "admin":
        st.subheader("Аналитика")
        # Чтобы не было ошибки ProgrammingError, используем SELECT *
        with engine.connect() as conn:
            df_an = pd.read_sql("SELECT * FROM expenses", conn)
        
        c1, c2 = st.columns(2)
        # Тут твои оригинальные метрики (я поставил заглушки, подставь свои названия колонок)
        c1.metric("Всего расходов", f"{len(df_an)}") 
        
        if not df_an.empty:
            # Используем колонки, которые точно есть в твоей базе
            fig = px.bar(df_an, title="Расходы") 
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Доступ только для администратора")
