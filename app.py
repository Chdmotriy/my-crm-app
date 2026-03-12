import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import calendar
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM CashFlow Calendar", layout="wide")
ADMIN_PASSWORD = "D17v01ch89!" # ЗАМЕНИТЕ НА СВОЙ

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")
if user_password != ADMIN_PASSWORD:
    st.info("Введите пароль.")
    st.stop()

# --- 2. БАЗА ---
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
st.title("🏦 Финансовая CRM")

tabs = st.tabs(["📅 Календарь", "📈 Прогноз", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка"])

# Вкладка 1: Календарь
with tabs[0]:
    events = []
    with engine.connect() as conn:
        cal_inc = pd.read_sql("SELECT c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        cal_exp = pd.read_sql("SELECT description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    for _, row in cal_inc.iterrows():
        events.append({"title": f"➕ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#28a745"})
    for _, row in cal_exp.iterrows():
        events.append({"title": f"➖ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#dc3545"})

    st_calendar(events=events, options={"locale": "ru", "initialView": "dayGridMonth"})

# Вкладка 2: Прогноз
with tabs[1]:
    with engine.connect() as conn:
        inc_f = pd.read_sql("SELECT date, amount FROM schedule WHERE status = 'Ожидается'", conn)
        exp_f = pd.read_sql("SELECT date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    if not inc_f.empty or not exp_f.empty:
        inc_f['month'] = pd.to_datetime(inc_f['date']).dt.strftime('%Y-%m')
        exp_f['month'] = pd.to_datetime(exp_f['date']).dt.strftime('%Y-%m')
        inc_g = inc_f.groupby('month')['amount'].sum().reset_index()
        exp_g = exp_f.groupby('month')['amount'].sum().reset_index()
        cf = pd.merge(inc_g, exp_g, on='month', how='outer', suffixes=('_inc', '_exp')).fillna(0)
        st.plotly_chart(px.bar(cf, x='month', y=['amount_inc', 'amount_exp'], barmode='group', title="CashFlow", color_discrete_map={'amount_inc':'#28a745','amount_exp':'#dc3545'}), use_container_width=True)

# Вкладка 3: Реестр
with tabs[2]:
    with engine.connect() as conn:
        res = pd.read_sql(text("SELECT c.name, c.total_amount, COALESCE(SUM(e.amount), 0) as exp_sum FROM clients c LEFT JOIN expenses e ON c.id = e.client_id GROUP BY c.id"), conn)
    res['Прибыль'] = res['total_amount'] - res['exp_sum']
    st.dataframe(res.style.format("{:,.0f} ₽", subset=['total_amount', 'exp_sum', 'Прибыль']), use_container_width=True)

# Вкладка 4: Карточка
with tabs[3]:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Выберите клиента", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        t_pay, t_exp = st.tabs(["💵 Оплаты (Доход)", "💸 Затраты (Расход)"])
        with t_pay:
            with engine.connect() as conn:
                df_p = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id"), conn, params={"id":c_id})
            ed_p = st.data_editor(df_p, column_config={"id":None}, num_rows="dynamic", use_container_width=True, key=f"ed_p_{c_id}")
            if st.button("Сохранить оплаты", key=f"btn_p_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed_p.iterrows():
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id,:d,:a,:s)"), {"id":c_id,"d":r['date'],"a":r['amount'],"s":r['status']})
                    conn.commit()
                st.rerun()
        with t_exp:
            with engine.connect() as conn:
                df_e = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            ed_e = st.data_editor(df_e, column_config={"id":None, "status":{"options":["Планируется","ОПЛАЧЕНО"]}}, num_rows="dynamic", use_container_width=True, key=f"ed_e_{c_id}")
            if st.button("Сохранить затраты", key=f"btn_e_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM expenses WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed_e.iterrows():
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:id,:ds,:am,:st,:dt)"), {"id":c_id,"ds":r['description'],"am":r['amount'],"st":r['status'],"dt":r['date']})
                    conn.commit()
                st.rerun()

# Вкладка 5: Новая сделка
with tabs[4]:
    with st.form("new_deal_form"):
        n, t = st.text_input("ФИО"), st.number_input("Сумма", value=100000.0)
        tp = st.radio("Тип", ["Рассрочка", "Сразу"])
        m, d = st.number_input("Месяцев", min_value=1, value=1), st.date_input("Дата начала", datetime.now())
        if st.form_submit_button("Создать"):
            with engine.connect() as conn:
                res = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n,"t":t,"m":int(m),"d":d})
                cid = res.scalar()
                steps = 1 if tp == "Сразу" else int(m)
                for i in range(steps):
                    conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if tp=="Сразу" else "Ожидается"})
                conn.commit()
            st.rerun()
