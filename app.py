import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Interactive Calendar", layout="wide")
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

# --- 3. ГЛАВНЫЕ МЕТРИКИ ---
st.title("🏦 Интерактивная CRM")
with engine.connect() as conn:
    inc = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn).iloc
    exp = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn).iloc
t_rev, p_rev = float(inc['t'] or 0), float(inc['p'] or 0)
t_exp, p_exp = float(exp['t'] or 0), float(exp['p'] or 0)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Общий оборот", f"{t_rev:,.0f} ₽")
c2.metric("Всего затрат", f"{t_exp:,.0f} ₽", delta=f"-{t_exp:,.0f}", delta_color="inverse")
c3.metric("Прибыль (план)", f"{(t_rev - t_exp):,.0f} ₽")
c4.metric("Касса (факт)", f"{(p_rev - p_exp):,.0f} ₽")

st.divider()

# --- 4. ВКЛАДКИ ---
tab_cal, tab_flow, tab_reestr, tab_details, tab_add = st.tabs([
    "📅 Календарь", "📈 Аналитика", "📋 Реестр", "🔍 Карточка", "➕ Новая сделка"
])

# Вкладка 1: Интерактивный календарь
with tab_cal:
    with engine.connect() as conn:
        # Загружаем только ОЖИДАЕМЫЕ события
        cal_inc = pd.read_sql("SELECT s.id, c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        cal_exp = pd.read_sql("SELECT id, description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    events = []
    for _, row in cal_inc.iterrows():
        events.append({"id": f"inc_{row['id']}", "title": f"➕ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#28a745", "allDay": True})
    for _, row in cal_exp.iterrows():
        events.append({"id": f"exp_{row['id']}", "title": f"➖ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#dc3545", "allDay": True})

    # Отрисовка календаря
    cal_res = st_calendar(events=events, options={"locale": "ru", "initialView": "dayGridMonth", "selectable": True})
    
    # ОБРАБОТКА НАЖАТИЯ НА СОБЫТИЕ
    if cal_res.get("eventClick"):
        clicked_event = cal_res["eventClick"]["event"]
        ev_id_str = clicked_event["id"] # Получаем наш составной ID (например, inc_15)
        ev_type, ev_id = ev_id_str.split("_")
        ev_title = clicked_event["title"]
        
        st.write("---")
        st.subheader("⚙️ Управление событием")
        st.info(f"Вы выбрали: **{ev_title}**")
        
        if st.button("✅ Отметить как выполненное (ОПЛАЧЕНО)", use_container_width=True, type="primary"):
            table = "schedule" if ev_type == "inc" else "expenses"
            with engine.connect() as conn:
                conn.execute(text(f"UPDATE {table} SET status = 'ОПЛАЧЕНО' WHERE id = :id"), {"id": int(ev_id)})
                conn.commit()
            st.success("Статус обновлен! Данные пересчитаны.")
            st.rerun()

# Вкладка 2: Аналитика (код остается прежним)
with tab_flow:
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    sel_year = st.selectbox("Год", available_years)
    with engine.connect() as conn:
        rev_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as rev FROM schedule WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
        exp_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as exp FROM expenses WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
    if not rev_m.empty:
        chart_data = pd.merge(rev_m, exp_m, on=['month', 'm_num'], how='outer').fillna(0).sort_values('m_num')
        st.plotly_chart(px.bar(chart_data, x='month', y=['rev', 'exp'], barmode='group', color_discrete_map={'rev':'#28a745','exp':'#dc3545'}), use_container_width=True)

# Остальные вкладки (Реестр, Карточка, Новая сделка) без изменений, чтобы сохранить функционал
with tab_reestr:
    with engine.connect() as conn:
        res_df = pd.read_sql(text("SELECT c.name as \"Клиент\", c.total_amount as \"Выручка\", COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as \"Затраты\" FROM clients c ORDER BY c.name"), conn)
    res_df['Прибыль'] = res_df['Выручка'] - res_df['Затраты']
    st.dataframe(res_df, column_config={"Выручка":st.column_config.NumberColumn(format="%d ₽"), "Затраты":st.column_config.NumberColumn(format="%d ₽"), "Прибыль":st.column_config.NumberColumn(format="%d ₽")}, use_container_width=True)

with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    if not cl_list.empty:
        sel_c = st.selectbox("Клиент", cl_list['name'], key="det_sel")
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc)
        t_p, t_e = st.tabs(["💵 Оплаты", "💸 Затраты"])
        with t_p:
            with engine.connect() as conn:
                df_p = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            st.data_editor(df_p, column_config={"id":None}, use_container_width=True, key=f"p_ed_{c_id}")
        with t_e:
            with engine.connect() as conn:
                df_e = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            st.data_editor(df_e, column_config={"id":None}, use_container_width=True, key=f"e_ed_{c_id}")

with tab_add:
    with st.form("new_deal"):
        n, t = st.text_input("ФИО"), st.number_input("Сумма", value=100000.0)
        tp = st.radio("Тип", ["Рассрочка", "Сразу"], horizontal=True)
        m, d = st.number_input("Месяцев", min_value=1, value=1), st.date_input("Дата", datetime.now())
        if st.form_submit_button("Создать"):
            if n:
                with engine.connect() as conn:
                    cid = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n,"t":t,"m":int(m),"d":d}).scalar()
                    steps = 1 if tp == "Сразу" else int(m)
                    for i in range(steps):
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if tp=="Сразу" else "Ожидается"})
                    conn.commit()
                st.rerun()
