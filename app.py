import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import calendar
from icalendar import Calendar, Event
import sqlalchemy
from sqlalchemy import text
import io

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM CashFlow Pro", layout="wide")
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

# --- 3. ФУНКЦИЯ КОНЦА МЕСЯЦА ---
def get_last_day_of_month(date_val):
    last_day = calendar.monthrange(date_val.year, date_val.month)[1]
    return date_val.replace(day=last_day)

# --- 4. ИНТЕРФЕЙС ---
st.title("💰 Прогноз движения денежных средств")

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📈 Прогноз и Аналитика", "📋 Реестр сделок", "🔍 Карточка и Расходы", "➕ Новая сделка"
])

with tab_main:
    with engine.connect() as conn:
        # Доходы (только будущие)
        inc_df = pd.read_sql("SELECT date, amount FROM schedule WHERE status = 'Ожидается'", conn)
        # Расходы (планируемые)
        exp_df = pd.read_sql("SELECT date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    today = datetime.now().date()
    end_of_current_month = get_last_day_of_month(today)

    # Умный перенос расходов: если даты нет или она в прошлом — ставим на конец текущего месяца
    def fix_exp_date(d):
        if pd.isna(d) or d < today:
            return end_of_current_month
        return d

    if not exp_df.empty:
        exp_df['date'] = pd.to_datetime(exp_df['date']).dt.date.apply(fix_exp_date)

    # Группировка по месяцам
    inc_df['month'] = pd.to_datetime(inc_df['date']).dt.strftime('%Y-%m')
    exp_df['month'] = pd.to_datetime(exp_df['date']).dt.strftime('%Y-%m')
    
    inc_m = inc_df.groupby('month')['amount'].sum().reset_index(name='Доход')
    exp_m = exp_df.groupby('month')['amount'].sum().reset_index(name='Расход')
    
    cf_df = pd.merge(inc_m, exp_m, on='month', how='outer').fillna(0).sort_values('month')
    cf_df['Баланс месяца'] = cf_df['Доход'] - cf_df['Расход']

    if not cf_df.empty:
        st.plotly_chart(px.bar(cf_df, x='month', y=['Доход', 'Расход'], barmode='group', 
                             color_discrete_map={'Доход':'#00CC96','Расход':'#EF553B'},
                             title="Прогноз: Входящие vs Исходящие потоки"), use_container_width=True)
        
        st.dataframe(cf_df, column_config={
            "month": "Месяц",
            "Доход": st.column_config.NumberColumn(format="%d ₽"),
            "Расход": st.column_config.NumberColumn(format="%d ₽"),
            "Баланс месяца": st.column_config.NumberColumn(format="%d ₽")
        }, use_container_width=True)
    else:
        st.info("Будущих платежей и расходов не запланировано.")

with tab_reestr:
    with engine.connect() as conn:
        cl = pd.read_sql("SELECT id, name, total_amount FROM clients ORDER BY name", conn)
        ex = pd.read_sql("SELECT client_id, SUM(amount) as total_exp FROM expenses GROUP BY client_id", conn)
    
    if not cl.empty:
        res = pd.merge(cl, ex, left_on='id', right_on='client_id', how='left')
        res['total_exp'] = pd.to_numeric(res['total_exp']).fillna(0)
        res['Прибыль'] = res['total_amount'] - res['total_exp']
        
        st.dataframe(res[['name', 'total_amount', 'total_exp', 'Прибыль']], 
            column_config={
                "name": "Клиент",
                "total_amount": st.column_config.NumberColumn("Выручка", format="%d ₽"),
                "total_exp": st.column_config.NumberColumn("Затраты", format="%d ₽"),
                "Прибыль": st.column_config.NumberColumn("Прибыль", format="%d ₽")
            }, use_container_width=True)

with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Выберите клиента", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        t1, t2 = st.tabs(["💰 Оплаты (Доход)", "💸 Затраты (Расход)"])
        
        with t1:
            with engine.connect() as conn:
                df1 = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            ed1 = st.data_editor(df1, column_config={"id":None}, num_rows="dynamic", use_container_width=True, key=f"p_{c_id}")
            if st.button("💾 Сохранить оплаты", key=f"btn_p_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed1.iterrows():
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id,:d,:a,:s)"), {"id":c_id,"d":r['date'],"a":r['amount'],"s":r['status']})
                    conn.commit()
                st.rerun()

        with t2:
            with engine.connect() as conn:
                df2 = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            st.caption("Если дата пустая/прошедшая — расход встанет на конец текущего месяца.")
            ed2 = st.data_editor(df2, column_config={"id":None, "status":{"options":["Планируется","ОПЛАЧЕНО"]}}, num_rows="dynamic", use_container_width=True, key=f"e_{c_id}")
            if st.button("💾 Сохранить затраты", key=f"btn_e_{c_id}"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM expenses WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed2.iterrows():
                        # Логика: если даты нет, ставим конец текущего месяца
                        raw_date = pd.to_datetime(r['date']).date() if not pd.isna(r['date']) else None
                        final_d = fix_exp_date(raw_date)
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:id,:ds,:am,:st,:dt)"), 
                                     {"id":c_id,"ds":r['description'],"am":r['amount'],"st":r['status'],"dt":final_d})
                    conn.commit()
                st.rerun()

with tab_add:
    with st.form("add_new"):
        n = st.text_input("ФИО")
        t = st.number_input("Сумма", value=100000.0)
        tp = st.radio("Тип", ["Рассрочка", "Сразу"])
        m = st.number_input("Месяцев", min_value=1, value=1)
        d = st.date_input("Дата начала", datetime.now())
        if st.form_submit_button("✅ Создать"):
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

if st.sidebar.button("🗑 Сбросить всё"):
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS clients; DROP TABLE IF EXISTS schedule; DROP TABLE IF EXISTS expenses;"))
        conn.commit()
    st.rerun()
