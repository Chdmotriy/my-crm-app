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
ADMIN_PASSWORD = "D17v01ch89!" 

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

def get_last_day_of_month(date_val):
    last_day = calendar.monthrange(date_val.year, date_val.month)[1]
    return date_val.replace(day=last_day)

# --- 3. ИНТЕРФЕЙС ---
st.title("🏦 Финансовый календарь и учет")

tabs = st.tabs(["📅 Календарь событий", "📈 Прогноз", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка"])

with tabs[0]:
    st.subheader("Сетка платежей и затрат")
    
    with engine.connect() as conn:
        # Собираем приходы
        cal_inc = pd.read_sql("SELECT c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        # Собираем расходы
        cal_exp = pd.read_sql("SELECT description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    events = []
    # Добавляем приходы в календарь (Зеленые)
    for _, row in cal_inc.iterrows():
        events.append({
            "title": f"➕ {row['name']}: {row['amount']:,.0f}₽",
            "start": str(row['date']),
            "color": "#28a745",
            "allDay": True
        })
    
    # Добавляем расходы в календарь (Красные)
    for _, row in cal_exp.iterrows():
        events.append({
            "title": f"➖ {row['name']}: {row['amount']:,.0f}₽",
            "start": str(row['date']),
            "color": "#dc3545",
            "allDay": True
        })

    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek"},
        "initialView": "dayGridMonth",
        "locale": "ru",
    }
    
    st_calendar(events=events, options=calendar_options)

with tabs[1]:
    # (Здесь остается ваш код графиков из прошлого сообщения)
    with engine.connect() as conn:
        inc_f = pd.read_sql("SELECT date, amount FROM schedule WHERE status = 'Ожидается'", conn)
        exp_f = pd.read_sql("SELECT date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    if not inc_f.empty or not exp_f.empty:
        inc_f['month'] = pd.to_datetime(inc_f['date']).dt.strftime('%Y-%m')
        exp_f['month'] = pd.to_datetime(exp_f['date']).dt.strftime('%Y-%m')
        cf = pd.merge(inc_f.groupby('month')['amount'].sum(), exp_f.groupby('month')['amount'].sum(), on='month', how='outer').fillna(0)
        st.plotly_chart(px.bar(cf, barmode='group', title="Прогноз CashFlow"), use_container_width=True)

with tabs[2]:
    with engine.connect() as conn:
        res = pd.read_sql(text("""
            SELECT c.name as "Клиент", c.total_amount as "Выручка", 
            COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты"
            FROM clients c ORDER BY c.name
        """), conn)
        res['Прибыль'] = res['Выручка'] - res['Затраты']
        st.dataframe(res, column_config={
            "Выручка": st.column_config.NumberColumn(format="%d ₽"),
            "Затраты": st.column_config.NumberColumn(format="%d ₽"),
            "Прибыль": st.column_config.NumberColumn(format="%d ₽")
        }, use_container_width=True)

with tabs[3]:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    if not cl_list.empty:
        sel_c = st.selectbox("Клиент", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        col_p, col_e = st.tabs(["💵 Оплаты", "💸 Затраты"])
        with col_p:
            sh = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id"), conn, params={"id":c_id})
            st.data_editor(sh, key=f"ed_p_{c_id}", use_container_width=True)
        with col_e:
            ex = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            st.data_editor(ex, key=f"ed_e_{c_id}", use_container_width=True)

with tabs[4]:
    with st.form("new_deal"):
        n, t = st.text_input("ФИО"), st.number_input("Сумма", value=100000.0)
        tp = st.radio("Тип", ["Рассрочка", "Сразу"])
        m, d = st.number_input("Месяцев", min_value=1, value=1), st.date_input("Дата", datetime.now())
        if st.form_submit_button("Создать"):
            with engine.connect() as conn:
                cid = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n,"t":t,"m":m,"d":d}).scalar()
                steps = 1 if tp == "Сразу" else int(m)
                for i in range(steps):
                    conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                 {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if tp=="Сразу" else "Ожидается"})
                conn.commit()
            st.rerun()
