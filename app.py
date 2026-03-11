import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
from icalendar import Calendar, Event
import io

# Настройка базы данных
conn = sqlite3.connect('payments.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients 
                      (id INTEGER PRIMARY KEY, name TEXT, total_amount REAL, months INTEGER, start_date DATE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS schedule 
                      (id INTEGER PRIMARY KEY, client_id INTEGER, date DATE, amount REAL, status TEXT)''')
    conn.commit()

init_db()

st.set_page_config(page_title="CRM Рассрочки Pro Max", layout="wide")
st.title("📈 Управление платежами")

# --- ФУНКЦИЯ СОЗДАНИЯ ФАЙЛА КАЛЕНДАРЯ ---
def create_ics_stable(client_name, schedule_df):
    cal = Calendar()
    cal.add('prodid', '-//CRM Рассрочки//')
    cal.add('version', '2.0')
    for _, row in schedule_df.iterrows():
        event = Event()
        event.add('summary', f"💰 Платеж: {client_name}")
        date_obj = datetime.strptime(row['date'], '%Y-%m-%d').date()
        event.add('dtstart', date_obj)
        event.add('dtend', date_obj)
        event.add('description', f"Сумма: {row['amount']:,.0f} руб.")
        cal.add_component(event)
    return cal.to_ical()

# --- ВКЛАДКИ ---
tab_main, tab_reestr, tab_details, tab_add = st.tabs([
    "📊 Аналитика", "📋 Сводный реестр", "🔍 Карточка и Календарь", "➕ Новый клиент"
])

with tab_main:
    stats_q = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    t = stats_q['t'].iloc[0] if not pd.isna(stats_q['t'].iloc[0]) else 0
    p = stats_q['p'].iloc[0] if not pd.isna(stats_q['p'].iloc[0]) else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Портфель", f"{t:,.0f} ₽")
    c2.metric("Собрано", f"{p:,.0f} ₽")
    c3.metric("Остаток", f"{(t-p):,.0f} ₽")
    
    df_f = pd.read_sql("SELECT strftime('%Y-%m', date) as month, SUM(amount) as total FROM schedule WHERE status='Ожидается' GROUP BY month", conn)
    if not df_f.empty:
        st.plotly_chart(px.bar(df_f, x='month', y='total', title="Прогноз поступлений"), use_container_width=True)

with tab_reestr:
    search_query = st.text_input("🔍 Поиск клиента по ФИО", "")
    reestr_q = """
        SELECT c.name as 'Клиент', c.total_amount as 'Цена', 
        SUM(CASE WHEN s.status='ОПЛАЧЕНО' THEN s.amount ELSE 0 END) as 'Оплачено',
        SUM(CASE WHEN s.status='Ожидается' THEN s.amount ELSE 0 END) as 'Остаток'
        FROM clients c LEFT JOIN schedule s ON c.id=s.client_id 
        WHERE c.name LIKE ?
        GROUP BY c.id ORDER BY c.name ASC
    """
    reestr = pd.read_sql(reestr_q, conn, params=(f'%{search_query}%',))
    st.dataframe(reestr.style.format("{:,.0f} ₽", subset=['Цена', 'Оплачено', 'Остаток']), use_container_width=True)

with tab_details:
    client_list = pd.read_sql("SELECT id, name FROM clients", conn)
    if not client_list.empty:
        sel_name = st.selectbox("Выберите клиента", client_list['name'])
        c_id = int(client_list[client_list['name'] == sel_name]['id'].values[0])
        
        sched = pd.read_sql("SELECT date, amount, status FROM schedule WHERE client_id=?", conn, params=(c_id,))
        ics_data = create_ics_stable(sel_name, sched[sched['status']=='Ожидается'])
        
        st.download_button("📅 Скачать файл для Календаря (.ics)", ics_data, f"{sel_name}.ics", "text/calendar")
        
        st.write("---")
        all_s = pd.read_sql("SELECT id, date, amount, status FROM schedule WHERE client_id=? ORDER BY date", conn, params=(c_id,))
        for idx, row in all_s.iterrows():
            # ИСПРАВЛЕНО: добавлено количество колонок (4)
            col1, col2, col3, col4 = st.columns(4)
            new_d = col1.date_input(f"Дата {idx+1}", value=pd.to_datetime(row['date']), key=f"d_{row['id']}")
            new_a = col2.number_input(f"Сумма {idx+1}", value=float(row['amount']), key=f"a_{row['id']}")
            new_s = col3.selectbox(f"Статус", ["Ожидается", "ОПЛАЧЕНО"], index=0 if row['status']=="Ожидается" else 1, key=f"s_{row['id']}")
            if col4.button("💾", key=f"b_{row['id']}"):
                cursor.execute("UPDATE schedule SET date=?, amount=?, status=? WHERE id=?", (new_d.strftime('%Y-%m-%d'), new_a, new_s, row['id']))
                conn.commit(); st.rerun()
    else:
        st.info("База пуста")

with tab_add:
    with st.form("add_form"):
        name_in = st.text_input("ФИО")
        total_in = st.number_input("Сумма договора", value=180000.0)
        months_in = st.number_input("Кол-во месяцев", value=12, step=1)
        start_in = st.date_input("Дата начала", datetime.now())
        if st.form_submit_button("Создать"):
            if name_in:
                cursor.execute("INSERT INTO clients (name, total_amount, months, start_date) VALUES (?,?,?,?)", (name_in, total_in, int(months_in), start_in))
                last_id = cursor.lastrowid
                for i in range(int(months_in)):
                    m = (start_in.month + i - 1) % 12 + 1
                    y = start_in.year + (start_in.month + i - 1) // 12
                    pay_date = start_in.replace(year=y, month=m)
                    cursor.execute("INSERT INTO schedule (client_id, date, amount, status) VALUES (?,?,?,?)", 
                                   (last_id, pay_date.strftime('%Y-%m-%d'), total_in/months_in, "Ожидается"))
                conn.commit(); st.rerun()

if st.sidebar.button("🗑 Очистить базу"):
    cursor.execute("DELETE FROM clients"); cursor.execute("DELETE FROM schedule"); conn.commit(); st.rerun()

