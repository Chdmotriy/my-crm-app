import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px

# Конфигурация страницы
st.set_page_config(page_title="CRM Система", layout="wide")

# Настройка подключения к базе данных (Neon PostgreSQL)
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

# Функция для получения данных из БД
def get_data(query):
    with engine.connect() as conn:
        return pd.read_sql(query, conn)

# Заголовок системы
st.title("🚀 Моя CRM Система")

# Вкладки интерфейса
tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Реестр", "📅 Календарь", "💸 Финансы", "🗂️ Карточка", "📈 Аналитика"])

# Вкладка 1: Реестр клиентов
with tab1:
    st.subheader("Реестр клиентов")
    df_clients = get_data("SELECT * FROM clients")
    edited_df = st.data_editor(df_clients, num_rows="dynamic", key="clients_editor")
    
    if st.button("Сохранить изменения в Реестре"):
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM clients"))
            edited_df.to_sql('clients', engine, if_exists='append', index=False)
            conn.commit()
        st.success("Данные успешно сохранены!")

# Вкладка 2: Календарь платежей
with tab2:
    st.subheader("График предстоящих поступлений")
    df_schedule = get_data("SELECT * FROM schedule")
    st.dataframe(df_schedule, use_container_width=True)

# Вкладка 3: Финансы (Расходы)
with tab3:
    st.subheader("Учет расходов")
    df_expenses = get_data("SELECT * FROM expenses")
    st.dataframe(df_expenses, use_container_width=True)

# Вкладка 4: Карточка клиента
with tab4:
    st.subheader("Детальная информация по клиенту")
    clients_list = get_data("SELECT id, client_name FROM clients")
    
    if not clients_list.empty:
        selected_client = st.selectbox("Выберите клиента", clients_list['client_name'])
        client_id = clients_list[clients_list['client_name'] == selected_client]['id'].values[0]
        
        # Получение истории платежей клиента
        with engine.connect() as conn:
            query = text("SELECT amount, planned_date, status FROM schedule WHERE client_id = :id")
            client_payments = pd.read_sql(query, conn, params={"id": int(client_id)})
        
        st.write(f"### История платежей: {selected_client}")
        st.table(client_payments)
    else:
        st.info("Добавьте клиентов в Реестр")

# Вкладка 5: Аналитика
with tab5:
    st.subheader("Аналитика финансовых потоков")
    
    with engine.connect() as conn:
        total_income = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status = 'paid'")).scalar() or 0
        total_expense = conn.execute(text("SELECT SUM(amount) FROM expenses")).scalar() or 0
        df_analysis = pd.read_sql("SELECT category, amount FROM expenses", conn)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Общий доход", f"{total_income} ₽")
    col2.metric("Общий расход", f"{total_expense} ₽")
    col3.metric("Прибыль", f"{total_income - total_expense} ₽")
    
    if not df_analysis.empty:
        fig = px.pie(df_analysis, values='amount', names='category', title="Структура расходов по категориям")
        st.plotly_chart(fig, use_container_width=True)
