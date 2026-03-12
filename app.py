import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from icalendar import Calendar, Event
import sqlalchemy
from sqlalchemy import text

# --- 1. НАСТРОЙКИ И ПАРОЛЬ ---
st.set_page_config(page_title="CRM Рассрочки Pro", layout="wide")

ADMIN_PASSWORD = "D17v01ch89!" # ЗАМЕНИТЕ НА СВОЙ

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")

if user_password != ADMIN_PASSWORD:
    st.info("Введите пароль в боковой панели для входа.")
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
        conn.commit()

init_db()

# --- 3. ФУНКЦИИ ---
def create_ics_stable(client_name, schedule_df):
    cal = Calendar()
    for _, row in schedule_df.iterrows():
        event = Event()
        event.add('summary', f"💰 Платеж: {client_name}")
        event.add('dtstart', pd.to_datetime(row['date']).date())
        event.add('dtend', pd.to_datetime(row['date']).date())
        event.add('description', f"Сумма: {row['amount']:,.0f} руб.")
        cal.add_component(event)
    return cal.to_ical()

# --- 4. ИНТЕРФЕЙС ---
st.title("📈 Облачная CRM")

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📊 Аналитика", "📋 Сводный реестр", "🔍 Карточка и Редактор", "➕ Новый клиент"
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
        col_sel, col_del = st.columns([3, 1])
        sel_name = col_sel.selectbox("Выберите клиента", client_list['name'])
        c_id = int(client_list[client_list['name'] == sel_name]['id'].values[0])
        
        if col_del.button("❌ Удалить клиента", use_container_width=True):
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                conn.commit()
            st.rerun()

        with engine.connect() as conn:
            sched_df = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
        
        st.write(f"### Редактор графика: {sel_name}")
        edited_df = st.data_editor(
            sched_df, 
            column_config={
                "id": None,
                "date": st.column_config.DateColumn("Дата", required=True),
                "amount": st.column_config.NumberColumn("Сумма", min_value=0),
                "status": st.column_config.SelectboxColumn("Статус", options=["Ожидается", "ОПЛАЧЕНО"])
            },
            num_rows="dynamic", use_container_width=True, key=f"ed_{c_id}"
        )

        c_save, c_cal = st.columns(2)
        if c_save.button("💾 Сохранить весь график", type="primary", use_container_width=True):
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                for _, row in edited_df.iterrows():
                    conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                 {"id": c_id, "dt": row['date'], "am": row['amount'], "st": row['status']})
                conn.commit()
            st.success("Обновлено!"); st.rerun()

        ics_data = create_ics_stable(sel_name, sched_df[sched_df['status']=='Ожидается'])
        c_cal.download_button("📅 Скачать Календарь", ics_data, f"{sel_name}.ics", use_container_width=True)

with tab_add:
    with st.form("add_form"):
        n = st.text_input("ФИО клиента")
        t = st.number_input("Общая сумма договора", min_value=0.0, value=180000.0)
        m = st.number_input("Кол-во месяцев (платежей)", min_value=1, value=12, step=1)
        d = st.date_input("Дата первого платежа", datetime.now())
        
        if st.form_submit_button("🚀 Создать клиента и график"):
            if n:
                try:
                    with engine.connect() as conn:
                        # 1. Добавляем клиента
                        res = conn.execute(
                            text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n, :t, :m, :d) RETURNING id"),
                            {"n": n, "t": t, "m": int(m), "d": d}
                        )
                        # Получаем ID (совместимо с разными версиями SQLAlchemy)
                        new_id = res.scalar() 
                        
                        # 2. Генерируем график платежей (Безопасный расчет дат)
                        monthly_amount = t / m
                        current_pay_date = d
                        
                        for i in range(int(m)):
                            # Запись текущего платежа
                            conn.execute(
                                text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :date, :amount, :status)"),
                                {"id": new_id, "date": current_pay_date, "amount": monthly_amount, "status": "Ожидается"}
                            )
                            # Сдвигаем дату на 30 дней для следующего шага
                            from datetime import timedelta
                            current_pay_date = current_pay_date + timedelta(days=30)
                            
                        conn.commit()
                    st.success(f"Клиент {n} успешно добавлен!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка при сохранении: {e}")
            else:
                st.error("Пожалуйста, введите ФИО клиента.")



if st.sidebar.button("🗑 Очистить базу (Все данные)"):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM clients")); conn.execute(text("DELETE FROM schedule")); conn.commit()
    st.rerun()
