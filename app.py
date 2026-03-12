import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import sqlalchemy
from sqlalchemy import text
import io

# --- 1. НАСТРОЙКИ И ПАРОЛЬ ---
st.set_page_config(page_title="CRM Рассрочки Pro", layout="wide")

ADMIN_PASSWORD = "D17v01ch89!" # !!! ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ НА СВОЙ !!!

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
st.title("📈 Облачная CRM: Полный учет")

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📊 Аналитика", "📋 Сводный реестр", "🔍 Карточка и Редактор", "➕ Новый клиент / Продажа"
])

# --- ВКЛАДКА: АНАЛИТИКА ---
with tab_main:
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    selected_year = st.selectbox("📅 Выберите год для анализа", available_years, index=0)

    with engine.connect() as conn:
        stats_query = text("""
            SELECT SUM(amount) as t, 
            SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p 
            FROM schedule 
            WHERE EXTRACT(YEAR FROM date) = :year
        """)
        stats = pd.read_sql(stats_query, conn, params={"year": selected_year})
    
    t_year = stats['t'].iloc[0] if stats['t'].iloc[0] else 0
    p_year = stats['p'].iloc[0] if stats['p'].iloc[0] else 0
    
    st.subheader(f"Итоги за {selected_year} год")
    c1, c2, c3 = st.columns(3)
    c1.metric("Оборот за год", f"{t_year:,.0f} ₽")
    c2.metric(f"Получено в {selected_year}", f"{p_year:,.0f} ₽")
    c3.metric("Ожидается к получению", f"{(t_year - p_year):,.0f} ₽")
    
    st.divider()

    with engine.connect() as conn:
        chart_query = text("""
            SELECT TO_CHAR(date, 'MM') as month_num, TO_CHAR(date, 'Month') as month_name, 
            SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as "Оплачено",
            SUM(CASE WHEN status='Ожидается' THEN amount ELSE 0 END) as "Ожидается"
            FROM schedule 
            WHERE EXTRACT(YEAR FROM date) = :year
            GROUP BY month_num, month_name
            ORDER BY month_num
        """)
        df_chart = pd.read_sql(chart_query, conn, params={"year": selected_year})

    if not df_chart.empty:
        fig = px.bar(df_chart, x='month_name', y=['Оплачено', 'Ожидается'], 
                     title=f"Движение средств по месяцам ({selected_year})",
                     labels={'value': 'Сумма (₽)', 'month_name': 'Месяц', 'variable': 'Статус'},
                     color_discrete_map={'Оплачено': '#00CC96', 'Ожидается': '#EF553B'},
                     text_auto='.2s')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"Данных за {selected_year} год пока нет.")

# --- ВКЛАДКА: РЕЕСТР ---
with tab_reestr:
    col_search, col_excel = st.columns([3, 1])
    search = col_search.text_input("🔍 Поиск клиента", "")
    with engine.connect() as conn:
        reestr = pd.read_sql(text("""
            SELECT c.name as "Клиент", c.total_amount as "Цена договора", 
            SUM(CASE WHEN s.status='ОПЛАЧЕНО' THEN s.amount ELSE 0 END) as "Оплачено",
            SUM(CASE WHEN s.status='Ожидается' THEN s.amount ELSE 0 END) as "Остаток"
            FROM clients c LEFT JOIN schedule s ON c.id=s.client_id 
            WHERE c.name ILIKE :name GROUP BY c.id ORDER BY c.name ASC
        """), conn, params={"name": f"%{search}%"})
    
    st.dataframe(reestr.style.format("{:,.0f} ₽", subset=["Цена договора", "Оплачено", "Остаток"]), use_container_width=True)

    if not reestr.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            reestr.to_excel(writer, index=False)
        col_excel.download_button("📥 Скачать в Excel", buffer.getvalue(), f"CRM_Export_{selected_year}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- ВКЛАДКА: КАРТОЧКА И РЕДАКТОР ---
with tab_details:
    with engine.connect() as conn:
        client_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not client_list.empty:
        col_sel, col_del = st.columns([3, 1])
        sel_name = col_sel.selectbox("Выберите клиента", client_list['name'])
        c_id = int(client_list[client_list['name'] == sel_name]['id'].values[0])
        
        if col_del.button("❌ Удалить сделку", use_container_width=True):
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
                "date": st.column_config.DateColumn("Дата"),
                "amount": st.column_config.NumberColumn("Сумма"),
                "status": st.column_config.SelectboxColumn("Статус", options=["Ожидается", "ОПЛАЧЕНО"])
            },
            num_rows="dynamic", use_container_width=True, key=f"ed_{c_id}"
        )

        c_save, c_cal = st.columns(2)
        if c_save.button("💾 Сохранить изменения", type="primary", use_container_width=True):
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                for _, row in edited_df.iterrows():
                    conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                 {"id": c_id, "dt": row['date'], "am": row['amount'], "st": row['status']})
                conn.commit()
            st.success("Обновлено!"); st.rerun()

        ics_data = create_ics_stable(sel_name, sched_df[sched_df['status']=='Ожидается'])
        c_cal.download_button("📅 Календарь платежей", ics_data, f"{sel_name}.ics", use_container_width=True)

# --- ВКЛАДКА: НОВЫЙ КЛИЕНТ ---
with tab_add:
    st.subheader("Регистрация новой продажи")
    with st.form("add_form"):
        n = st.text_input("ФИО клиента")
        t = st.number_input("Полная сумма сделки (руб)", min_value=0.0, value=180000.0)
        pay_type = st.radio("Тип оплаты", ["Рассрочка", "Оплата сразу (одним чеком)"], horizontal=True)
        
        col_m, col_d = st.columns(2)
        m = col_m.number_input("Кол-во месяцев (для рассрочки)", min_value=1, value=12, step=1)
        d = col_d.date_input("Дата первого платежа / Оплаты", datetime.now())
        
        if st.form_submit_button("✅ Внести в базу"):
            if n:
                try:
                    with engine.connect() as conn:
                        actual_months = 1 if pay_type == "Оплата сразу (одним чеком)" else int(m)
                        res = conn.execute(
                            text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n, :t, :m, :d) RETURNING id"),
                            {"n": n, "t": t, "m": actual_months, "d": d}
                        )
                        new_id = res.scalar() 
                        
                        if pay_type == "Оплата сразу (одним чеком)":
                            conn.execute(
                                text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :date, :amount, :status)"),
                                {"id": new_id, "date": d, "amount": t, "status": "ОПЛАЧЕНО"}
                            )
                        else:
                            monthly_amount = t / m
                            curr_date = d
                            for i in range(int(m)):
                                conn.execute(
                                    text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :date, :amount, :status)"),
                                    {"id": new_id, "date": curr_date, "amount": monthly_amount, "status": "Ожидается"}
                                )
                                curr_date = curr_date + timedelta(days=30)
                        conn.commit()
                    st.success(f"Запись создана!"); st.rerun()
                except Exception as e:
                    st.error(f"Ошибка: {e}")

if st.sidebar.button("🗑 Очистить базу (Все данные)"):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM clients")); conn.execute(text("DELETE FROM schedule")); conn.commit()
    st.rerun()

