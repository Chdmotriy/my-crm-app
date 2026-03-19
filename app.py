import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Interactive Pro", layout="wide")
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

# --- 3. ГЛАВНЫЕ МЕТРИКИ (ИСПРАВЛЕНО) ---
st.title("🏦 Интерактивная CRM")

with engine.connect() as conn:
    # Доходы
    inc_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    t_rev = float(inc_data['t'].fillna(0).iloc[0])
    p_rev = float(inc_data['p'].fillna(0).iloc[0])
    
    # Расходы
    exp_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn)
    t_exp = float(exp_data['t'].fillna(0).iloc[0])
    p_exp = float(exp_data['p'].fillna(0).iloc[0])

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
        # Тянем только неоплаченные, чтобы не захламлять календарь выполненными задачами
        cal_inc = pd.read_sql("SELECT s.id, c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        cal_exp = pd.read_sql("SELECT id, description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    events = []
    for _, row in cal_inc.iterrows():
        events.append({"id": f"inc_{row['id']}", "title": f"➕ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#28a745", "allDay": True})
    for _, row in cal_exp.iterrows():
        events.append({"id": f"exp_{row['id']}", "title": f"➖ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#dc3545", "allDay": True})

    cal_res = st_calendar(events=events, options={"locale": "ru", "initialView": "dayGridMonth", "selectable": True}, key="main_calendar")
    
    if cal_res and cal_res.get("eventClick"):
        clicked_event = cal_res["eventClick"]["event"]
        ev_id_str = clicked_event["id"]
        ev_type, ev_id = ev_id_str.split("_")
        ev_title = clicked_event["title"]
        
        st.write("---")
        st.subheader("⚙️ Быстрое действие")
        st.info(f"Выбрано: **{ev_title}**")
        
        # Одна кнопка для мгновенного изменения статуса
        if st.button("✅ Подтвердить оплату (Перевести в ОПЛАЧЕНО)", use_container_width=True, type="primary"):
            target_table = "schedule" if ev_type == "inc" else "expenses"
            new_status = "ОПЛАЧЕНО"
            
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {target_table} SET status = :status WHERE id = :id"),
                    {"status": new_status, "id": int(ev_id)}
                )
            st.success(f"Статус обновлен! Теперь в реестре и карточке этот платеж отмечен как оплаченный.")
            st.rerun()

# Вкладка 2: Аналитика и Прогноз
with tab_flow:
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    sel_year = st.selectbox("Выберите год для графиков", available_years)
    
    with engine.connect() as conn:
        rev_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as rev FROM schedule WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
        exp_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as exp FROM expenses WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
    
    if not rev_m.empty:
        st.subheader(f"Статистика за {sel_year} год")
        chart_data = pd.merge(rev_m, exp_m, on=['month', 'm_num'], how='outer').fillna(0).sort_values('m_num')
        st.plotly_chart(px.bar(chart_data, x='month', y=['rev', 'exp'], barmode='group', 
                               labels={'value': 'Сумма (₽)', 'month': 'Месяц'},
                               color_discrete_map={'rev':'#28a745','exp':'#dc3545'}), use_container_width=True)

    st.divider()
    
    # --- БЛОК ПРОГНОЗА НА 30 ДНЕЙ ---
    st.subheader("🔮 Прогноз на ближайшие 30 дней")
    
    with engine.connect() as conn:
        # Прогноз приходов
        f_rev_res = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status = 'Ожидается' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'")).scalar()
        forecast_rev = float(f_rev_res) if f_rev_res else 0.0
        
        # Прогноз расходов
        f_exp_res = conn.execute(text("SELECT SUM(amount) FROM expenses WHERE status = 'Планируется' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'")).scalar()
        forecast_exp = float(f_exp_res) if f_exp_res else 0.0

    f_c1, f_c2, f_c3 = st.columns(3)
    f_c1.metric("Ожидаемый приход", f"{forecast_rev:,.0f} ₽")
    f_c2.metric("Плановые расходы", f"{forecast_exp:,.0f} ₽", delta=f"-{forecast_exp:,.0f}", delta_color="inverse")
    f_c3.metric("Прогноз остатка", f"{(forecast_rev - forecast_exp):,.0f} ₽")
    
    if forecast_rev < forecast_exp:
        st.error("⚠️ Внимание: запланированные расходы превышают ожидаемые приходы в ближайшие 30 дней!")
# Вкладка 3: Реестр (Актив/Архив + Итоги по дебиторке)
with tab_reestr:
    with engine.connect() as conn:
        query = text("""
            SELECT 
                c.id,
                c.name as "Клиент", 
                c.total_amount as "Сумма договора", 
                COALESCE((SELECT SUM(amount) FROM schedule WHERE client_id = c.id AND status = 'ОПЛАЧЕНО'), 0) as "Получено",
                COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты",
                EXISTS (
                    SELECT 1 FROM schedule 
                    WHERE client_id = c.id AND date < CURRENT_DATE AND status = 'Ожидается'
                ) as "Есть_просрочка"
            FROM clients c 
            ORDER BY "Есть_просрочка" DESC, c.name ASC
        """)
        df = pd.read_sql(query, conn)
    
    # Расчеты
    df["Остаток долга"] = df["Сумма договора"] - df["Получено"]
    df["Прибыль"] = df["Сумма договора"] - df["Затраты"]

    # Метрики над таблицей (только по активным долгам)
    total_receivable = df[df["Остаток долга"] > 0]["Остаток долга"].sum()
    overdue_count = df[df["Есть_просroчка"] == True]["Клиент"].count()

    m_col1, m_col2 = st.columns(2)
    m_col1.metric("Общая дебиторка (ожидается)", f"{total_receivable:,.0f} ₽")
    m_col2.metric("Клиентов с просрочкой", f"{overdue_count} чел.", delta=f"{overdue_count}" if overdue_count > 0 else None, delta_color="inverse")

    st.divider()

    # Выбор режима отображения
    view_mode = st.radio("Показать клиентов:", ["Активные (есть долг)", "Архив (оплачено 100%)"], horizontal=True, key="reestr_mode")

    # Логика фильтрации
    if view_mode == "Активные (есть долг)":
        display_df = df[df["Остаток долга"] > 0].copy()
    else:
        display_df = df[df["Остаток долга"] <= 0].copy()

    # Стилизация просрочки
    def highlight_debt(row):
        if view_mode == "Активные (есть долг)" and row['Есть_просрочка']:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)

    if not display_df.empty:
        st.dataframe(
            display_df.style.apply(highlight_
# Вкладка 4: Карточка (Исправленные отступы и сохранение)
with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("Клиент", cl_list['name'], key="det_sel")
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        t_p, t_e = st.tabs(["💵 Оплаты", "💸 Затраты"])
        
        # --- ПОДВКЛАДКА: ОПЛАТЫ ---
        with t_p:
            with engine.connect() as conn:
                df_p = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            
            ed_p = st.data_editor(
                df_p, 
                num_rows="dynamic", 
                column_config={"id": None, "status": st.column_config.SelectboxColumn("Статус", options=["Ожидается", "ОПЛАЧЕНО"], required=True)}, 
                use_container_width=True, 
                key=f"p_ed_{c_id}"
            )
            
            if st.button("Сохранить оплаты", key=f"btn_p_{c_id}"):
                with engine.begin() as conn:
                    for _, r in ed_p.iterrows():
                        if pd.notnull(r.get('id')):
                            conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:rid"), {"d":r['date'], "a":r['amount'], "s":r['status'], "rid":int(r['id'])})
                        elif pd.notnull(r.get('date')):
                            conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:cid, :d, :a, :s)"), {"cid":c_id, "d":r['date'], "a":r['amount'], "s":r.get('status', 'Ожидается')})
                st.rerun()

        # --- ПОДВКЛАДКА: ЗАТРАТЫ (Исправлено здесь) ---
        with t_e:
            with engine.connect() as conn:
                df_e = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            
            ed_e = st.data_editor(
                df_e, 
                num_rows="dynamic", 
                column_config={"id": None, "status": st.column_config.SelectboxColumn("Статус", options=["Планируется", "ОПЛАЧЕНО"], required=True)}, 
                use_container_width=True, 
                key=f"e_ed_{c_id}"
            )
            
            if st.button("Сохранить затраты", key=f"btn_e_{c_id}"):
                with engine.begin() as conn:
                    for _, r in ed_e.iterrows():
                        if pd.notnull(r.get('id')):
                            conn.execute(text("UPDATE expenses SET description=:ds, amount=:am, status=:st, date=:dt WHERE id=:rid"), {"ds":r['description'], "am":r['amount'], "st":r['status'], "dt":r['date'], "rid":int(r['id'])})
                        elif pd.notnull(r.get('description')):
                            conn.execute(text("INSERT INTO expenses (client_id, description, amount, status, date) VALUES (:cid, :ds, :am, :st, :dt)"), {"cid":c_id, "ds":r['description'], "am":r['amount'], "st":r['status'], "dt":r['date']})
                st.rerun()

# Вкладка 5: Новая сделка
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
