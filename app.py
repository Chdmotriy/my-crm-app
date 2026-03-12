import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import sqlalchemy
from sqlalchemy import text
import io

# --- 1. НАСТРОЙКИ И ПАРОЛЬ ---
st.set_page_config(page_title="CRM Profit Pro", layout="wide")

ADMIN_PASSWORD = "D17v01ch89!" # ЗАМЕНИТЕ НА СВОЙ

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")

if user_password != ADMIN_PASSWORD:
    st.info("Введите пароль в боковой панели.")
    st.stop()

# --- 2. БАЗА ДАННЫХ ---
try:
    DB_URL = st.secrets["DB_URL"]
except:
    DB_URL = "postgresql://neondb_owner:npg_ymONePvDcf43@ep-snowy-forest-a4f6efz3-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

engine = sqlalchemy.create_engine(DB_URL)

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, name TEXT, total_amount REAL, months INTEGER, start_date DATE)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schedule (id SERIAL PRIMARY KEY, client_id INTEGER, date DATE, amount REAL, status TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, client_id INTEGER, description TEXT, amount REAL, status TEXT, date DATE)"))
        conn.commit()

init_db()

# --- 3. ИНТЕРФЕЙС ---
st.title("🚀 CRM: Выручка и Чистая прибыль")

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📊 Аналитика прибыли", "📋 Сводный реестр", "🔍 Карточка и Затраты", "➕ Новая сделка"
])

# --- ВКЛАДКА: АНАЛИТИКА ---
with tab_main:
    with engine.connect() as conn:
        # Безопасное извлечение доходов
        inc_df = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
        total_revenue = float(inc_df['t'].iloc[0]) if not pd.isna(inc_df['t'].iloc[0]) else 0.0
        paid_revenue = float(inc_df['p'].iloc[0]) if not pd.isna(inc_df['p'].iloc[0]) else 0.0

        # Безопасное извлечение расходов
        exp_df = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn)
        total_expenses = float(exp_df['t'].iloc[0]) if not pd.isna(exp_df['t'].iloc[0]) else 0.0
        paid_expenses = float(exp_df['p'].iloc[0]) if not pd.isna(exp_df['p'].iloc[0]) else 0.0
    
    st.subheader("💰 Финансовый результат (Все время)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Общая выручка", f"{total_revenue:,.0f} ₽")
    c2.metric("Всего затрат", f"{total_expenses:,.0f} ₽", delta=f"-{total_expenses:,.0f}", delta_color="inverse")
    
    profit = total_revenue - total_expenses
    c3.metric("Чистая прибыль (план)", f"{profit:,.0f} ₽")
    
    real_cash = paid_revenue - paid_expenses
    c4.metric("Деньги в кассе (факт)", f"{real_cash:,.0f} ₽")
    
    st.divider()
    
    # График по годам
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    sel_year = st.selectbox("📅 Детализация за год", available_years)
    
    with engine.connect() as conn:
        chart_data = pd.read_sql(text("""
            SELECT TO_CHAR(date, 'Month') as month, 
            SUM(amount) as revenue,
            (SELECT SUM(amount) FROM expenses WHERE TO_CHAR(date, 'Month') = TO_CHAR(s.date, 'Month') AND EXTRACT(YEAR FROM date) = :y) as expense,
            TO_CHAR(date, 'MM') as month_num
            FROM schedule s WHERE EXTRACT(YEAR FROM date) = :y 
            GROUP BY month, month_num ORDER BY month_num
        """), conn, params={"y": sel_year})
        
    if not chart_data.empty:
        st.plotly_chart(px.bar(chart_data, x='month', y=['revenue', 'expense'], barmode='group', 
                             title=f"Доходы vs Расходы ({sel_year})",
                             labels={'value': 'Сумма (₽)', 'month': 'Месяц', 'variable': 'Тип'}), use_container_width=True)
    else:
        st.info("Данных за этот год пока нет.")

# --- ВКЛАДКА: РЕЕСТР ---
with tab_reestr:
    search = st.text_input("🔍 Найти клиента", "")
    query = text("""
        SELECT c.name as "Клиент", c.total_amount as "Выручка", 
        COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты",
        (c.total_amount - COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0)) as "Прибыль"
        FROM clients c WHERE c.name ILIKE :n ORDER BY c.name ASC
    """)
    with engine.connect() as conn:
        df_r = pd.read_sql(query, conn, params={"n": f"%{search}%"})
    st.dataframe(df_r.style.format("{:,.0f} ₽", subset=["Выручка", "Затраты", "Прибыль"]), use_container_width=True)

# --- ВКЛАДКА: КАРТОЧКА И ЗАТРАТЫ ---
with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Выберите клиента", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].values[0])
        
        col_pay, col_exp = st.tabs(["💵 График оплат (Доход)", "💸 Затраты по клиенту (Расход)"])
        
        with col_pay:
            with engine.connect() as conn:
                sh_df = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
            ed_pay = st.data_editor(sh_df, column_config={"id":None}, num_rows="dynamic", use_container_width=True, key=f"p_{c_id}")
            if st.button("💾 Сохранить оплаты", key=f"sp_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                    for _, r in ed_pay.iterrows():
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                     {"id": c_id, "dt": r['date'], "am": r['amount'], "st": r['status']})
                    conn.commit()
                st.rerun()

        with col_exp:
            with engine.connect() as conn:
                ex_df = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id": c_id})
            ed_exp = st.data_editor(ex_df, column_config={
                "id":None, 
                "status": st.column_config.SelectboxColumn("Статус", options=["Планируется","ОПЛАЧЕНО"]),
                "date": st.column_config.DateColumn("Дата")
            }, num_rows="dynamic", use_container_width=True, key=f"e_{c_id}")
            if st.button("💾 Сохранить затраты", key=f"se_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM expenses WHERE client_id = :id"), {"id": c_id})
                    for _, r in ed_exp.iterrows():
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:id, :ds, :am, :st, :dt)"), 
                                     {"id": c_id, "ds": r['description'], "am": r['amount'], "st": r['status'], "dt": r['date']})
                    conn.commit()
                st.rerun()
    else:
        st.info("Добавьте первого клиента")

# --- ВКЛАДКА: НОВЫЙ КЛИЕНТ ---
with tab_add:
    with st.form("add_c"):
        n = st.text_input("ФИО клиента")
        t = st.number_input("Сумма сделки", value=100000.0)
        type_p = st.radio("Тип оплаты", ["Рассрочка", "Сразу"], horizontal=True)
        m = st.number_input("Кол-во месяцев (для рассрочки)", value=1, min_value=1)
        d = st.date_input("Дата начала", datetime.now())
        if st.form_submit_button("✅ Создать сделку"):
            if n:
                with engine.connect() as conn:
                    res = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), 
                                     {"n":n,"t":t,"m":m,"d":d})
                    cid = res.scalar()
                    steps = 1 if type_p == "Сразу" else int(m)
                    for i in range(steps):
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                     {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if type_p=="Сразу" else "Ожидается"})
                    conn.commit()
                st.rerun()

if st.sidebar.button("🗑 Сбросить базу"):
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS clients; DROP TABLE IF EXISTS schedule; DROP TABLE IF EXISTS expenses;"))
        conn.commit()
    st.rerun()
