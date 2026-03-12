import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import calendar
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Profit & CashFlow", layout="wide")
ADMIN_PASSWORD = "D17v01ch89!" # ЗАМЕНИТЕ НА СВОЙ

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")
if user_password != ADMIN_PASSWORD:
    st.info("Введите пароль для доступа.")
    st.stop()

# --- 2. БАЗА ---
try:
    DB_URL = st.secrets["DB_URL"]
except:
    DB_URL = "postgresql://neondb_owner:npg_ymONePvDcf43@ep-snowy-forest-a4f6efz3-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
engine = sqlalchemy.create_engine(DB_URL)

# --- 3. АНАЛИТИКА (ОБЩИЕ ЦИФРЫ) ---
st.title("🏦 Управление финансами")

with engine.connect() as conn:
    # Доходы
    inc_df = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    total_rev = float(inc_df['t'].fillna(0).iloc[0])
    paid_rev = float(inc_df['p'].fillna(0).iloc[0])
    # Расходы
    exp_df = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn)
    total_exp = float(exp_df['t'].fillna(0).iloc[0])
    paid_exp = float(exp_df['p'].fillna(0).iloc[0])

st.subheader("💰 Итоговые показатели (Весь период)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Общий оборот", f"{total_rev:,.0f} ₽")
c2.metric("Всего затрат", f"{total_exp:,.0f} ₽", delta=f"-{total_exp:,.0f}", delta_color="inverse")
c3.metric("Чистая прибыль (план)", f"{(total_rev - total_exp):,.0f} ₽")
c4.metric("Деньги в кассе (факт)", f"{(paid_rev - paid_exp):,.0f} ₽")

st.divider()

# --- 4. ВКЛАДКИ ---
tab_cal, tab_flow, tab_reestr, tab_details, tab_add = st.tabs([
    "📅 Календарь", "📈 Аналитика и Прогноз", "📋 Реестр сделок", "🔍 Карточка", "➕ Новая сделка"
])

# Вкладка 1: Календарь
with tab_cal:
    events = []
    with engine.connect() as conn:
        cal_inc = pd.read_sql("SELECT c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        cal_exp = pd.read_sql("SELECT description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    for _, row in cal_inc.iterrows():
        events.append({"title": f"➕ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#28a745", "allDay": True})
    for _, row in cal_exp.iterrows():
        events.append({"title": f"➖ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#dc3545", "allDay": True})

    st_calendar(events=events, options={"locale": "ru", "initialView": "dayGridMonth"})

# Вкладка 2: Аналитика и Прогноз
with tab_flow:
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    sel_year = st.selectbox("Выберите год для анализа", available_years)

    with engine.connect() as conn:
        # Доходы и расходы по месяцам для графика
        rev_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as rev FROM schedule WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
        exp_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as exp FROM expenses WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
    
    if not rev_m.empty:
        chart_data = pd.merge(rev_m, exp_m, on=['month', 'm_num'], how='outer').fillna(0).sort_values('m_num')
        fig = px.bar(chart_data, x='month', y=['rev', 'exp'], barmode='group', 
                     title=f"Доходы vs Расходы ({sel_year})",
                     labels={'value': 'Сумма (₽)', 'variable': 'Тип'},
                     color_discrete_map={'rev': '#28a745', 'exp': '#dc3545'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Данных за этот год еще нет.")

# Вкладка 3: Реестр
with tab_reestr:
    with engine.connect() as conn:
        res_df = pd.read_sql(text("""
            SELECT c.name as "Клиент", c.total_amount as "Выручка", 
            COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты"
            FROM clients c ORDER BY c.name
        """), conn)
    res_df['Прибыль'] = res_df['Выручка'] - res_df['Затраты']
    st.dataframe(res_df, column_config={
        "Выручка": st.column_config.NumberColumn(format="%d ₽"),
        "Затраты": st.column_config.NumberColumn(format="%d ₽"),
        "Прибыль": st.column_config.NumberColumn(format="%d ₽")
    }, use_container_width=True)

# Вкладка 4: Карточка
with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Выберите клиента", cl_list['name'], key="sel_client_card")
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        t_p, t_e = st.tabs(["💵 Оплаты (Доход)", "💸 Затраты (Расход)"])
        with t_p:
            with engine.connect() as conn:
                df_p = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            ed_p = st.data_editor(df_p, column_config={"id":None}, num_rows="dynamic", use_container_width=True, key=f"ed_p_{c_id}")
            if st.button("Сохранить оплаты", key=f"save_p_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed_p.iterrows():
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id,:d,:a,:s)"), {"id":c_id,"d":r['date'],"a":r['amount'],"s":r['status']})
                    conn.commit()
                st.rerun()
        with t_e:
            with engine.connect() as conn:
                df_e = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            ed_e = st.data_editor(df_e, column_config={"id":None, "status":{"options":["Планируется","ОПЛАЧЕНО"]}}, num_rows="dynamic", use_container_width=True, key=f"ed_e_{c_id}")
            if st.button("Сохранить затраты", key=f"save_e_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM expenses WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed_e.iterrows():
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:id,:ds,:am,:st,:dt)"), {"id":c_id,"ds":r['description'],"am":r['amount'],"st":r['status'],"dt":r['date']})
                    conn.commit()
                st.rerun()

# Вкладка 5: Новая сделка
with tab_add:
    with st.form("new_deal_final"):
        n = st.text_input("ФИО клиента")
        t = st.number_input("Сумма сделки", value=100000.0)
        tp = st.radio("Тип", ["Рассрочка", "Сразу"], horizontal=True)
        m = st.number_input("Месяцев", min_value=1, value=1)
        d = st.date_input("Дата начала", datetime.now())
        if st.form_submit_button("✅ Создать сделку"):
            if n:
                with engine.connect() as conn:
                    res = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n,"t":t,"m":int(m),"d":d})
                    cid = res.scalar()
                    steps = 1 if tp == "Сразу" else int(m)
                    for i in range(steps):
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                     {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if tp=="Сразу" else "Ожидается"})
                    conn.commit()
                st.rerun()
