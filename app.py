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
ADMIN_PASSWORD = "ВАШ_ПАРОЛЬ" 

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

# --- 3. ФУНКЦИЯ УМНОЙ ДАТЫ ---
def get_end_of_month(date_val=None):
    if date_val is None:
        date_val = datetime.now()
    last_day = calendar.monthrange(date_val.year, date_val.month)[1]
    return date_val.replace(day=last_day)

# --- 4. ИНТЕРФЕЙС ---
st.title("💰 Прогноз движения денежных средств")

tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📈 Прогноз и Аналитика", "📋 Реестр сделок", "🔍 Карточка и Расходы", "➕ Новая сделка"
])

with tab_main:
    # Загрузка всех плановых данных
    with engine.connect() as conn:
        all_inc = pd.read_sql("SELECT date, amount FROM schedule WHERE status = 'Ожидается'", conn)
        all_exp = pd.read_sql("SELECT date, amount, status FROM expenses WHERE status = 'Планируется'", conn)
    
    # Обработка "плавающих" дат расходов
    today = datetime.now().date()
    def adjust_exp_date(d):
        if d is None or d < today:
            return get_end_of_month(datetime.now()).date()
        return d

    if not all_exp.empty:
        all_exp['date'] = all_exp['date'].apply(adjust_exp_date)

    # Группировка для графика Cash Flow
    all_inc['month'] = pd.to_datetime(all_inc['date']).dt.to_period('M').astype(str)
    all_exp['month'] = pd.to_datetime(all_exp['date']).dt.to_period('M').astype(str)
    
    inc_m = all_inc.groupby('month')['amount'].sum().reset_index(name='Доход')
    exp_m = all_exp.groupby('month')['amount'].sum().reset_index(name='Расход')
    
    cf_df = pd.merge(inc_m, exp_m, on='month', how='outer').fillna(0).sort_values('month')
    cf_df['Остаток за месяц'] = cf_df['Доход'] - cf_df['Расход']

    st.subheader("🗓 Прогноз поступлений и трат по месяцам")
    if not cf_df.empty:
        fig_cf = px.bar(cf_df, x='month', y=['Доход', 'Расход'], barmode='group',
                        title="Ожидаемые входящие и исходящие потоки",
                        color_discrete_map={'Доход': '#00CC96', 'Расход': '#EF553B'})
        st.plotly_chart(fig_cf, use_container_width=True)
        
        st.write("### Детализация прогноза")
        st.table(cf_df.rename(columns={'month': 'Месяц'}).style.format("{:,.0f} ₽", subset=['Доход', 'Расход', 'Остаток за месяц']))
    else:
        st.info("Нет запланированных движений денег.")

with tab_reestr:
    # Стандартный реестр (код из прошлых шагов)
    with engine.connect() as conn:
        clients = pd.read_sql("SELECT id, name, total_amount FROM clients ORDER BY name", conn)
        exp_sum = pd.read_sql("SELECT client_id, SUM(amount) as total_exp FROM expenses GROUP BY client_id", conn)
    
    if not clients.empty:
        res = pd.merge(clients, exp_sum, left_on='id', right_on='client_id', how='left').fillna(0)
        res['Прибыль'] = res['total_amount'] - res['total_exp']
        st.dataframe(res[['name', 'total_amount', 'total_exp', 'Прибыль']].style.format("{:,.0f} ₽"), use_container_width=True)

with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Выберите клиента", cl_list['name'])
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc)
        
        t1, t2 = st.tabs(["💰 Оплаты клиента", "💸 Затраты"])
        
        with t1:
            with engine.connect() as conn:
                df1 = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            ed1 = st.data_editor(df1, column_config={"id":None}, num_rows="dynamic", use_container_width=True, key=f"p_{c_id}")
            if st.button("Сохранить оплаты", key="s1"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed1.iterrows():
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id,:d,:a,:s)"), {"id":c_id,"d":r['date'],"a":r['amount'],"s":r['status']})
                    conn.commit()
                st.rerun()

        with t2:
            with engine.connect() as conn:
                df2 = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            st.caption("Если дата пустая, расход встанет на конец текущего месяца.")
            ed2 = st.data_editor(df2, column_config={"id":None, "status":{"options":["Планируется","ОПЛАЧЕНО"]}}, num_rows="dynamic", use_container_width=True, key=f"e_{c_id}")
            if st.button("Сохранить затраты", key="s2"):
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM expenses WHERE client_id=:id"), {"id":c_id})
                    for _, r in ed2.iterrows():
                        # Авто-подстановка даты конца месяца, если дата не введена
                        final_date = r['date'] if not pd.isna(r['date']) else get_end_of_month().date()
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:id,:ds,:am,:st,:dt)"), 
                                     {"id":c_id,"ds":r['description'],"am":r['amount'],"st":r['status'],"dt":final_date})
                    conn.commit()
                st.rerun()

with tab_add:
    # Код добавления клиента из прошлого сообщения
    with st.form("add"):
        n, t, type_p = st.text_input("ФИО"), st.number_input("Сумма"), st.radio("Тип", ["Рассрочка", "Сразу"])
        m, d = st.number_input("Месяцев", value=1), st.date_input("Дата", datetime.now())
        if st.form_submit_button("Создать"):
            with engine.connect() as conn:
                res = conn.execute(text("INSERT INTO clients (name, total_amount, months, start_date) VALUES (:n,:t,:m,:d) RETURNING id"), {"n":n,"t":t,"m":m,"d":d})
                cid = res.scalar()
                steps = 1 if type_p == "Сразу" else int(m)
                for i in range(steps):
                    conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:id, :dt, :am, :st)"), 
                                 {"id":cid, "dt":d+timedelta(days=30*i), "am":t/steps, "st":"ОПЛАЧЕНО" if type_p=="Сразу" else "Ожидается"})
                conn.commit()
            st.rerun()
