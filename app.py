import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text
import pytesseract
from PIL import Image
import io
import re

# Для облака Streamlit путь указывать НЕ НУЖНО, 
# система найдет его сама после добавления packages.txt
def add_log(client_id, action, details=""):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO logs (client_id, action, details) 
            VALUES (:cid, :act, :det)
        """), {"cid": client_id, "act": action, "det": details})
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
# --- ВКЛАДКА 3: РЕЕСТР (С поиском и итогами) ---
with tab_reestr:
    with engine.connect() as conn:
        query = text("""
            SELECT c.id, c.name as "Клиент", c.contract_no as "Договор", c.total_amount as "Сумма договора", 
            COALESCE((SELECT SUM(amount) FROM schedule WHERE client_id = c.id AND status = 'ОПЛАЧЕНО'), 0) as "Получено",
            COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты",
            EXISTS (SELECT 1 FROM schedule WHERE client_id = c.id AND date < CURRENT_DATE AND status = 'Ожидается') as "Есть_просрочка"
            FROM clients c ORDER BY "Есть_просрочка" DESC, c.name ASC
        """)
        df = pd.read_sql(query, conn)
    
    df["Остаток долга"] = df["Сумма договора"] - df["Получено"]
    df["Прибыль"] = df["Сумма договора"] - df["Затраты"]

    # Поиск и фильтрация
    search = st.text_input("🔍 Быстрый поиск (имя или номер договора)", "").lower()
    if search:
        df = df[df["Клиент"].str.lower().str.contains(search) | df["Договор"].str.lower().str.contains(search, na=False)]

    # Метрики
    t_rec = df[df["Остаток долга"] > 0]["Остаток долга"].sum()
    ov_c = int(df["Есть_просрочка"].sum())

    m1, m2 = st.columns(2)
    m1.metric("Дебиторка (в поиске)", f"{t_rec:,.0f} ₽")
    m2.metric("Клиентов с просрочкой", f"{ov_c} чел.", delta=f"{ov_c}" if ov_c > 0 else None, delta_color="inverse")

    st.divider()
    
    v_mode = st.radio("Показать:", ["Активные сделки", "Завершенные (Архив)"], horizontal=True)
    display_df = df[df["Остаток долга"] > 0].copy() if v_mode == "Активные сделки" else df[df["Остаток долга"] <= 0].copy()

    def style_r(row):
        return ['background-color: #ffcccc' if (v_mode == "Активные сделки" and row['Есть_просрочка']) else '' for _ in row]

    if not display_df.empty:
        st.dataframe(
            display_df.style.apply(style_r, axis=1),
            use_container_width=True,
            height=450,
            column_config={
                "id": None, "Есть_просрочка": None,
                "Сумма договора": st.column_config.NumberColumn(format="%d ₽"),
                "Получено": st.column_config.NumberColumn(format="%d ₽"),
                "Остаток долга": st.column_config.NumberColumn(format="%d ₽"),
                "Затраты": st.column_config.NumberColumn(format="%d ₽"),
                "Прибыль": st.column_config.NumberColumn(format="%d ₽")
            }
        )
    else:
        st.info("Данные отсутствуют или не соответствуют фильтру.")

# --- ВКЛАДКА 4: КАРТОЧКА (ПОЛНАЯ ВЕРСИЯ) ---
with tab_details:
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("👤 Выберите клиента", cl_list['name'], key="det_sel")
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        with engine.connect() as conn:
            c_info = conn.execute(text("SELECT name, phone, contract_no, comment, total_amount, passport, snils, inn, address FROM clients WHERE id = :id"), {"id":c_id}).fetchone()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("📞 Телефон", c_info[1] if c_info[1] else "—")
        c2.metric("📄 Договор", f"№{c_info[2]}" if c_info[2] else "—")
        c3.metric("💰 Сумма", f"{c_info[4]:,.0f} ₽")

        with st.expander("📝 Редактировать профиль (и документы)"):
            with st.form(f"f_edit_{c_id}"):
                un = st.text_input("ФИО", value=c_info[0] if c_info[0] else "")
                up = st.text_input("Телефон", value=c_info[1] if c_info[1] else "")
                uc = st.text_input("Номер договора", value=c_info[2] if c_info[2] else "")
                
                # Новые поля
                st.markdown("---")
                upass = st.text_input("Паспорт", value=c_info[5] if c_info[5] else "")
                usnils = st.text_input("СНИЛС", value=c_info[6] if c_info[6] else "")
                uinn = st.text_input("ИНН", value=c_info[7] if c_info[7] else "")
                uaddr = st.text_input("Адрес", value=c_info[8] if c_info[8] else "")
                st.markdown("---")
                
                ucm = st.text_area("Заметка", value=c_info[3] if c_info[3] else "")
                
                if st.form_submit_button("Сохранить изменения"):
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE clients 
                            SET name=:n, phone=:p, contract_no=:c, comment=:cm, passport=:pass, snils=:snils, inn=:inn, address=:addr 
                            WHERE id=:id
                        """), {
                            "n":un, "p":up, "c":uc, "cm":ucm, 
                            "pass":upass, "snils":usnils, "inn":uinn, "addr":uaddr, 
                            "id":c_id
                        })
                        conn.execute(text("INSERT INTO logs (client_id, action, details) VALUES (:id, 'Правка', 'Изменен профиль и документы')"), {"id":c_id})
                    st.success("Данные успешно обновлены!")
                    st.rerun()

        with engine.connect() as conn:
            p_cnt = conn.execute(text("SELECT COUNT(*) FROM schedule WHERE client_id = :id AND status = 'Ожидается'"), {"id":c_id}).scalar()
        
        if p_cnt > 0:
            if st.button(f"✅ Оплатить все счета ({p_cnt} шт.)", use_container_width=True):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE schedule SET status = 'ОПЛАЧЕНО' WHERE client_id = :id AND status = 'Ожидается'"), {"id":c_id})
                    conn.execute(text("INSERT INTO logs (client_id, action, details) VALUES (:id, 'Оплата', 'Массовое закрытие')"), {"id":c_id})
                st.rerun()

        st.divider()
        t1, t2, t3 = st.tabs(["💵 Оплаты", "💸 Расходы", "📜 История"])
        
        with t1:
            with engine.connect() as conn:
                df_p = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id":c_id})
            ed_p = st.data_editor(df_p, num_rows="dynamic", use_container_width=True, key=f"p_ed_{c_id}", column_config={"id": None})
            if st.button("Сохранить график", key=f"btn_p_{c_id}"):
                with engine.begin() as conn:
                    for _, r in ed_p.iterrows():
                        if pd.notnull(r.get('id')):
                            conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:rid"), {"d":r['date'], "a":r['amount'], "s":r['status'], "rid":int(r['id'])})
                    conn.execute(text("INSERT INTO logs (client_id, action, details) VALUES (:id, 'График', 'Правка таблицы')"), {"id":c_id})
                st.rerun()

        with t2:
            with engine.connect() as conn:
                df_e = pd.read_sql(text("SELECT id, description, amount, status, date FROM expenses WHERE client_id = :id"), conn, params={"id":c_id})
            ed_e = st.data_editor(df_e, num_rows="dynamic", use_container_width=True, key=f"e_ed_{c_id}", column_config={"id": None})
            if st.button("Сохранить расходы", key=f"btn_e_{c_id}"):
                with engine.begin() as conn:
                    for _, r in ed_e.iterrows():
                        if pd.notnull(r.get('id')):
                            conn.execute(text("UPDATE expenses SET description=:ds, amount=:am, status=:st, date=:dt WHERE id=:rid"), {"ds":r['description'], "am":r['amount'], "st":r['status'], "dt":r['date'], "rid":int(r['id'])})
                    conn.execute(text("INSERT INTO logs (client_id, action, details) VALUES (:id, 'Расходы', 'Правка таблицы')"), {"id":c_id})
                st.rerun()

        with t3:
            with engine.connect() as conn:
                l_df = pd.read_sql(text('SELECT timestamp as "Время", action as "Действие", details as "Детали" FROM logs WHERE client_id = :id ORDER BY timestamp DESC'), conn, params={"id":c_id})
            if not l_df.empty:
                st.dataframe(l_df, use_container_width=True)
            else:
                st.info("История пуста")

        with st.expander("⚠️ Удаление клиента"):
            confirm = st.checkbox(f"Удалить все данные {sel_c}")
            if st.button("🗑️ Удалить безвозвратно", type="primary", disabled=not confirm):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM expenses WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM logs WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                st.rerun()
    else:
        st.info("Нет активных клиентов.")
# Вкладка 5: Новая сделка (с доп. полями)
with tab_add:
    st.subheader("🤖 Автоматическое распознавание документов")
    
    # Хранилище временных данных, чтобы поля не сбрасывались
    if 'ocr_inn' not in st.session_state: st.session_state.ocr_inn = ""
    if 'ocr_snils' not in st.session_state: st.session_state.ocr_snils = ""
    if 'ocr_pass' not in st.session_state: st.session_state.ocr_pass = ""

    uploaded_file = st.file_uploader("Загрузить скан или фото (Паспорт, ИНН, СНИЛС)", type=['png', 'jpg', 'jpeg'])
    if uploaded_file is not None:
        if st.button("✨ Распознать текст", type="primary"):
            with st.spinner('Читаем документ...'):
                image = Image.open(uploaded_file)
                # Распознаем текст на русском и английском
                text = pytesseract.image_to_string(image, lang='rus+eng')
                
                # Ищем СНИЛС (формат 123-456-789 12 или слитно)
                snils_match = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}', text)
                if snils_match: st.session_state.ocr_snils = snils_match.group(0)
                
                # Ищем ИНН (обычно 10 или 12 цифр)
                inn_match = re.search(r'\b\d{10,12}\b', text)
                if inn_match: st.session_state.ocr_inn = inn_match.group(0)
                
                # Ищем серию и номер паспорта (4 цифры, пробел, 6 цифр)
                pass_match = re.search(r'\b\d{2}\s?\d{2}\s?\d{6}\b', text)
                if pass_match: st.session_state.ocr_pass = pass_match.group(0)
                
            st.success("Документ обработан! Проверьте заполненные поля ниже.")

    st.divider()

    with st.form("new_deal"):
        col1, col2 = st.columns(2)
        with col1:
            n = st.text_input("ФИО клиента")
            p = st.text_input("Телефон")
        with col2:
            t = st.number_input("Сумма договора", value=100000.0)
            c_no = st.text_input("Номер договора")
            
        st.markdown("##### 🪪 Документы")
        doc1, doc2 = st.columns(2)
        with doc1:
            # Сюда подставляются данные из нейросети, если они нашлись
            passp = st.text_input("Паспортные данные", value=st.session_state.ocr_pass)
            snils_val = st.text_input("СНИЛС", value=st.session_state.ocr_snils)
        with doc2:
            inn_val = st.text_input("ИНН", value=st.session_state.ocr_inn)
            addr = st.text_input("Адрес регистрации")

        st.markdown("##### ⚙️ Условия")
        tp = st.radio("Тип оплаты", ["Рассрочка", "Сразу"], horizontal=True)
        m = st.number_input("Кол-во платежей (месяцев)", min_value=1, value=1)
        d = st.date_input("Дата первого платежа", datetime.now())
        comm = st.text_area("Комментарий к сделке")
        
        if st.form_submit_button("Создать сделку"):
            if n:
                with engine.begin() as conn:
                    cid = conn.execute(text("""
                        INSERT INTO clients (name, total_amount, months, start_date, phone, contract_no, comment, passport, snils, inn, address) 
                        VALUES (:n, :t, :m, :d, :p, :c_no, :comm, :passp, :snils, :inn, :addr) RETURNING id
                    """), {"n":n, "t":t, "m":int(m), "d":d, "p":p, "c_no":c_no, "comm":comm, "passp":passp, "snils":snils_val, "inn":inn_val, "addr":addr}).scalar()
                    
                    steps = 1 if tp == "Сразу" else int(m)
                    amount_per_step = round(t / steps, 2)
                    for i in range(steps):
                        p_date = d + timedelta(days=i*30)
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:cid, :dt, :am, 'Ожидается')"),
                                     {"cid":cid, "dt":p_date, "am":amount_per_step})
                
                # Очищаем временную память после сохранения
                st.session_state.ocr_inn = ""
                st.session_state.ocr_snils = ""
                st.session_state.ocr_pass = ""
                st.success(f"Клиент {n} успешно добавлен!")
                st.rerun()
