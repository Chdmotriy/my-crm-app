import streamlit as st
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Импортируем нашу утилиту для распознавания документов
from utils.ocr_engine import process_document_image

def render(engine):
    st.subheader("➕ Новая сделка")
    st.markdown("### 🤖 Автоматическое распознавание документов")
    
    # Инициализация стейта для хранения распознанных данных
    if 'ocr_inn' not in st.session_state: st.session_state.ocr_inn = ""
    if 'ocr_snils' not in st.session_state: st.session_state.ocr_snils = ""
    if 'ocr_pass' not in st.session_state: st.session_state.ocr_pass = ""

    # Секция OCR
    uploaded_file = st.file_uploader("Загрузить скан или фото (Паспорт, ИНН, СНИЛС)", type=['png', 'jpg', 'jpeg'])
    if uploaded_file is not None:
        if st.button("✨ Распознать текст", type="primary"):
            with st.spinner('Читаем документ...'):
                # Вызываем нашу оптимизированную функцию
                result = process_document_image(uploaded_file.getvalue())
                
                if result["success"]:
                    if result["snils"]: st.session_state.ocr_snils = result["snils"]
                    if result["inn"]: st.session_state.ocr_inn = result["inn"]
                    if result["passport"]: st.session_state.ocr_pass = result["passport"]
                    st.success("Документ обработан! Проверьте поля.")
                else:
                    st.error(f"Ошибка при чтении: {result.get('error', 'Неизвестная ошибка')}")
            
    # Форма создания сделки (clear_on_submit автоматически очистит поля после сохранения)
    with st.form("new_deal", clear_on_submit=True):
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

        if st.form_submit_button("Создать сделку", type="primary"):
            if n:
                with engine.begin() as conn:
                    # 1. Добавляем клиента и получаем его ID
                    cid = conn.execute(text("""
                        INSERT INTO clients (name, total_amount, months, start_date, phone, contract_no, comment, passport, snils, inn, address) 
                        VALUES (:n, :t, :m, :d, :p, :c_no, :comm, :passp, :snils, :inn, :addr) RETURNING id
                    """), {
                        "n": n, "t": t, "m": int(m), "d": d,
                        "p": p, "c_no": c_no, "comm": comm,
                        "passp": passp, "snils": snils_val,
                        "inn": inn_val, "addr": addr
                    }).scalar()

                    # 2. Формируем график платежей
                    steps = 1 if tp == "Сразу" else int(m)
                    amount_per_step = round(t / steps, 2)

                    for i in range(steps):
                        p_date = d + relativedelta(months=i)
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:cid, :dt, :am, 'Ожидается')"), 
                                     {"cid": cid, "dt": p_date, "am": amount_per_step})

                # 3. Сбрасываем кэш распознанных данных для следующего клиента
                st.session_state.ocr_inn = ""
                st.session_state.ocr_snils = ""
                st.session_state.ocr_pass = ""

                st.success(f"Клиент {n} успешно добавлен! График платежей сформирован.")
                st.rerun()
            else:
                st.warning("⚠️ Пожалуйста, укажите ФИО клиента.")
