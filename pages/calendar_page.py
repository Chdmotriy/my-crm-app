import streamlit as st
import pandas as pd

def show(engine):
    with engine.connect() as conn:
        # Тянем только неоплаченные
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
        
        # УЛУЧШЕНИЕ: Добавлена защита от случайного клика
        confirm = st.checkbox("Подтверждаю получение / списание средств")
        
        if st.button("✅ Перевести в ОПЛАЧЕНО", use_container_width=True, type="primary", disabled=not confirm):
            target_table = "schedule" if ev_type == "inc" else "expenses"
            
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {target_table} SET status = 'ОПЛАЧЕНО' WHERE id = :id"),
                    {"id": int(ev_id)}
                )
            st.success(f"Статус обновлен! Платеж отмечен как оплаченный.")
            st.rerun()
