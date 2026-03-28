import streamlit as st
import pandas as pd
from sqlalchemy import text
from streamlit_calendar import calendar as st_calendar

def render(engine):
    st.subheader("📅 Календарь платежей и событий")
    st.info("💡 Нажмите на любое событие в календаре, чтобы быстро отметить его как оплаченное.")

    with engine.connect() as conn:
        # Тянем только неоплаченные доходы (Ожидается)
        cal_inc = pd.read_sql("""
            SELECT s.id, c.name, s.date, s.amount 
            FROM schedule s 
            JOIN clients c ON s.client_id = c.id 
            WHERE s.status = 'Ожидается'
        """, conn)
        
        # Тянем только плановые расходы
        cal_exp = pd.read_sql("""
            SELECT id, description as name, date, amount 
            FROM expenses 
            WHERE status = 'Планируется'
        """, conn)
    
    events = []
    
    # Зеленые события - ожидаемые поступления
    for _, row in cal_inc.iterrows():
        events.append({
            "id": f"inc_{row['id']}", 
            "title": f"➕ {row['name']}: {int(row['amount']):,} ₽".replace(",", " "), 
            "start": str(row['date']), 
            "color": "#28a745", 
            "allDay": True
        })
        
    # Красные события - плановые расходы
    for _, row in cal_exp.iterrows():
        events.append({
            "id": f"exp_{row['id']}", 
            "title": f"➖ {row['name']}: {int(row['amount']):,} ₽".replace(",", " "), 
            "start": str(row['date']), 
            "color": "#dc3545", 
            "allDay": True
        })

    # Отрисовка интерактивного календаря
    cal_res = st_calendar(
        events=events, 
        options={
            "locale": "ru", 
            "initialView": "dayGridMonth", 
            "selectable": True,
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay",
            }
        }, 
        key="main_calendar"
    )
    
    # Обработка клика по событию
    if cal_res and cal_res.get("eventClick"):
        clicked_event = cal_res["eventClick"]["event"]
        ev_id_str = clicked_event["id"]
        ev_type, ev_id = ev_id_str.split("_")
        ev_title = clicked_event["title"]
        
        st.divider()
        st.markdown("### ⚙️ Быстрое действие")
        st.write(f"Выбрано: **{ev_title}**")
        
        # Защита от случайного клика с уникальным ключом
        confirm = st.checkbox("Подтверждаю получение / списание средств", key=f"conf_check_{ev_id_str}")
        
        if st.button("✅ Перевести в статус 'ОПЛАЧЕНО'", use_container_width=True, type="primary", disabled=not confirm):
            target_table = "schedule" if ev_type == "inc" else "expenses"
            
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {target_table} SET status = 'ОПЛАЧЕНО' WHERE id = :id"),
                    {"id": int(ev_id)}
                )
            st.success("🎉 Статус обновлен! Операция переведена в оплаченные.")
            st.rerun()
