import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from datetime import datetime

def render(engine):
    st.subheader("📈 Финансовая аналитика")
    
    # 1. Получаем доступные года из базы для фильтра
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    
    # Если база пустая, предлагаем текущий год
    available_years = [int(y) for y in years_df['year'].dropna().tolist()] if not years_df.empty else [datetime.now().year]
    
    # Фильтр по году
    sel_year = st.selectbox("📅 Выберите год для графиков", available_years)
    
    # 2. Собираем статистику по месяцам
    with engine.connect() as conn:
        rev_m = pd.read_sql(text("""
            SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as rev 
            FROM schedule 
            WHERE EXTRACT(YEAR FROM date) = :y 
            GROUP BY month, m_num
        """), conn, params={"y": sel_year})
        
        exp_m = pd.read_sql(text("""
            SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as exp 
            FROM expenses 
            WHERE EXTRACT(YEAR FROM date) = :y 
            GROUP BY month, m_num
        """), conn, params={"y": sel_year})
    
    # 3. Отрисовка графика
    if not rev_m.empty or not exp_m.empty:
        # Объединяем доходы и расходы в одну таблицу, заполняем пустоты нулями
        chart_data = pd.merge(rev_m, exp_m, on=['month', 'm_num'], how='outer').fillna(0).sort_values('m_num')
        
        fig = px.bar(
            chart_data, 
            x='month', 
            y=['rev', 'exp'], 
            barmode='group', 
            labels={'value': 'Сумма (₽)', 'month': 'Месяц', 'variable': 'Движение средств'},
            color_discrete_map={'rev':'#28a745', 'exp':'#dc3545'}
        )
        
        # Делаем легенду красивой (переводим системные ключи в понятные слова)
        fig.for_each_trace(lambda t: t.update(name='🟢 Доходы' if t.name == 'rev' else '🔴 Расходы'))
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"📊 Нет финансовых операций (доходов или расходов) за {sel_year} год.")

    st.divider()
    
    # 4. Прогноз на ближайшие 30 дней (Кассовый разрыв)
    st.subheader("🔮 Прогноз на ближайшие 30 дней")
    
    with engine.connect() as conn:
        # Считаем ожидаемые доходы
        f_rev_res = conn.execute(text("""
            SELECT SUM(amount) FROM schedule 
            WHERE status = 'Ожидается' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
        """)).scalar()
        forecast_rev = float(f_rev_res) if f_rev_res else 0.0
        
        # Считаем ожидаемые расходы
        f_exp_res = conn.execute(text("""
            SELECT SUM(amount) FROM expenses 
            WHERE status = 'Планируется' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
        """)).scalar()
        forecast_exp = float(f_exp_res) if f_exp_res else 0.0

    f_c1, f_c2, f_c3 = st.columns(3)
    f_c1.metric("Ожидаемый приход", f"{forecast_rev:,.0f} ₽")
    f_c2.metric("Плановые расходы", f"{forecast_exp:,.0f} ₽", delta=f"-{forecast_exp:,.0f}", delta_color="inverse")
    
    saldo = forecast_rev - forecast_exp
    f_c3.metric("Прогноз остатка", f"{saldo:,.0f} ₽")
    
    # Умные уведомления
    if saldo < 0:
        st.error(f"⚠️ Внимание: ожидается кассовый разрыв! Плановые расходы превышают приходы на {abs(saldo):,.0f} ₽.")
    elif forecast_rev == 0 and forecast_exp == 0:
        st.write("Тишина. На ближайшие 30 дней не запланировано ни приходов, ни расходов.")
    else:
        st.success("✅ Финансовый прогноз положительный. Кассовый разрыв не предвидится.")
