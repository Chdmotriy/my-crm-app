import streamlit as st
import pandas as pd
from sqlalchemy import text

def render(engine):
    st.subheader("📋 Реестр сделок")
    
    # 1. Загрузка данных
    with engine.connect() as conn:
        df = pd.read_sql(text("""
            SELECT 
                id, name, phone, contract_no, total_amount, start_date 
            FROM clients 
            ORDER BY id DESC
        """), conn)
        
    if df.empty:
        st.info("В базе пока нет ни одной сделки. Перейдите в 'Новую сделку', чтобы добавить первую!")
        return

    # 2. Быстрые сводные метрики
    col1, col2 = st.columns(2)
    col1.metric("Всего клиентов в базе", len(df))
    col2.metric("Общая сумма всех договоров", f"{df['total_amount'].sum():,.0f} ₽")

    st.divider()

    # 3. Умный поиск и фильтрация
    search_query = st.text_input("🔍 Поиск (по ФИО, телефону или номеру договора):")
    
    if search_query:
        # Приводим всё к нижнему регистру для удобного поиска без учета заглавных букв
        mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
        display_df = df[mask]
    else:
        display_df = df

    # 4. Отображение красивой таблицы (DataFrame)
    # Переименуем колонки для вывода в интерфейс
    display_df = display_df.rename(columns={
        "id": "ID",
        "name": "ФИО Клиента",
        "phone": "Телефон",
        "contract_no": "№ Договора",
        "total_amount": "Сумма",
        "start_date": "Дата договора"
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Сумма": st.column_config.NumberColumn(format="%d ₽"),
            "Дата договора": st.column_config.DateColumn(format="DD.MM.YYYY")
        }
    )

    st.divider()

    # 5. Связка Реестра и Карточки клиента
    st.markdown("### ⚡ Быстрый переход в Карточку")
    
    if not display_df.empty:
        selected_client = st.selectbox("Выберите клиента для подробного просмотра:", display_df["ФИО Клиента"])
        
        if st.button("Перейти к профилю", type="primary"):
            # Сохраняем выбор пользователя в кэш
            st.session_state.det_sel = selected_client
            st.success(f"✅ Клиент **{selected_client}** зафиксирован! Теперь нажмите на пункт **'🔍 Карточка'** в левом боковом меню.")
