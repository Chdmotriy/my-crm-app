import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from icalendar import Calendar, Event
import sqlalchemy
from sqlalchemy import text

# --- 1. ЗАЩИТА ПАРОЛЕМ ---
st.set_page_config(page_title="Secure Cloud CRM", layout="wide")

# Придумайте свой пароль здесь
ADMIN_PASSWORD = "D17v01ch89!" 

with st.sidebar:
    st.title("🔐 Авторизация")
    user_password = st.text_input("Введите пароль доступа", type="password")

if user_password != ADMIN_PASSWORD:
    st.info("Пожалуйста, введите пароль в боковой панели, чтобы получить доступ к данным.")
    st.stop() # Программа замирает здесь, пока пароль неверный

# --- 2. БЕЗОПАСНОЕ ПОДКЛЮЧЕНИЕ К БАЗЕ ---
# Программа сначала ищет пароль в "сейфе" (Secrets), если не находит - берет из кода
try:
    DB_URL = st.secrets["DB_URL"]
except:
    DB_URL = "postgresql://neondb_owner:npg_ymONePvDcf43@ep-snowy-forest-a4f6efz3-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

engine = sqlalchemy.create_engine(DB_URL)

def init_db():
    with engine.connect() as conn:
        conn.execute(text('''CREATE TABLE IF NOT EXISTS clients 
                      (id SERIAL PRIMARY KEY, name TEXT, total_amount REAL, months INTEGER, start_date DATE)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS schedule 
                      (id SERIAL PRIMARY KEY, client_id INTEGER, date DATE, amount REAL, status TEXT)'''))
        conn.commit()

init_db()

# --- ДАЛЕЕ ВЕСЬ ВАШ ПРЕДЫДУЩИЙ ФУНКЦИОНАЛ ---
st.title("☁️ Облачная CRM: Управление рассрочками")

# (Функция создания календаря)
def create_ics_stable(client_name, schedule_df):
    cal = Calendar()
    for _, row in schedule_df.iterrows():
        event = Event()
        event.add('summary', f"💰 Платеж: {client_name}")
        event.add('dtstart', row['date'])
        event.add('dtend', row['date'])
        event.add('description', f"Сумма: {row['amount']:,.0f} руб.")
        cal.add_component(event)
    return cal.to_ical()

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📊 Аналитика", "📋 Сводный реестр", "🔍 Карточка и Управление", "➕ Новый клиент"
])

with tab_main:
    with engine.connect() as conn:
        stats = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    t = stats['t'].iloc[0] if stats['t'].iloc[0] else 0
    p = stats['p'].iloc[0] if stats['p'].iloc[0] else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Портфель", f"{t:,.0f} ₽")
    c2.metric("Собрано", f"{p:,.0f} ₽")
    c3.metric("Остаток", f"{(t-p):,.0f} ₽")
    
    with engine.connect() as conn:
        df_f = pd.read_sql("SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as total FROM schedule WHERE status='Ожидается' GROUP BY month ORDER BY month", conn)
    if not df_f.empty:
        st.plotly_chart(px.bar(df_f, x='month', y='total', title="Прогноз поступлений"), use_container_width=True)

with tab_reestr:
    search = st.text_input("🔍 Поиск клиента", "")
    with engine.connect() as conn:
        reestr = pd.read_sql(text("SELECT c.name as \"Клиент\", c.total_amount as \"Цена\", SUM(CASE WHEN s.status='ОПЛАЧЕНО' THEN s.amount ELSE 0 END) as \"Оплачено\", SUM(CASE WHEN s.status='Ожидается' THEN s.amount ELSE 0 END) as \"Остаток\" FROM clients c LEFT JOIN schedule s ON c.id=s.client_id WHERE c.name ILIKE :name GROUP BY c.id ORDER BY c.name ASC"), conn, params={"name": f"%{search}%"})
    st.dataframe(reestr.style.format("{:,.0f} ₽", subset=["Цена", "Оплачено", "Остаток"]), use_container_width=True)

with tab_details:
    with engine.connect() as conn:
        client_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    if not client_list.empty:
        col_sel, col_del = st.columns(2)
        sel_name = col_sel.selectbox("Выберите клиента", client_list['name'])
        c_id = int(client_list[client_list['name'] == sel_name]['id'].values[0])
        
        if col_del.button("❌ Удалить клиента"):
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                conn.commit()
            st.rerun()

        with engine.connect() as conn:
            sched_data = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
        
        st.download_button("📅 Скачать Календарь (.ics)", create_ics_stable(sel_name, sched_data[sched_data['status']=='Ожидается']), f"{sel_name}.ics")
        
        for idx, row in sched_data.iterrows():
            c1, c2, c3, c4 = st.columns(4)
            new_d = c1.date_input(f"Дата {idx+1}", value=row['date'], key=f"d_{row['id']}")
            new_a = c2.number_input(f"Сумма {idx+1}", value=float(row['amount']), key=f"a_{row['id']}")
            new_s = c3.selectbox(f"Статус", ["Ожидается", "ОПЛАЧЕНО"], index=0 if row['status']=="Ожидается" else 1, key=f"s_{row['id']}")
            if c4.button("💾", key=f"b_{row['id']}"):
                with engine.connect() as conn:
                    conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:id"), {"d": new_d, "a": new_a, "s": new_s, "id": row['id']})
                    conn.commit()
                st.rerun()

with tab_add:
    with st.form("add_form"):
        n, t, m, d = st.text_input("ФИО"), st.number_input("Сумма", value=180000.0), st.number_input("Месяцев", value=12), st.date_input("Старт", datetime.now())
        if st.form_submit_button("Создать"):
            if n:
                with engine.connect() as conn:
                    res = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n, "t":t, "m":m, "d":d})
                    new_id = res.fetchone()[0]
                    for i in range(int(m)):
                        mo = (d.month + i - 1) % 12 + 1
                        yr = d.year + (d.month + i - 1) // 12
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, 'Ожидается')"), {"id": new_id, "dt": d.replace(year=yr, month=mo), "am": t/m})
                    conn.commit()
                st.rerun()
