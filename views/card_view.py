import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# Импортируем наши новые утилиты
from utils.ocr_engine import process_document_image
from utils.pdf_generator import generate_contract_pdf

def render(engine):
    st.subheader("🔍 Карточка клиента")
    
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if cl_list.empty:
        st.info("База клиентов пуста.")
        return

    # Если мы перешли из "Реестра", в session_state мог сохраниться выбранный клиент
    default_index = 0
    if "det_sel" in st.session_state and st.session_state.det_sel in cl_list['name'].values:
        default_index = int(cl_list[cl_list['name'] == st.session_state.det_sel].index[0])

    sel_c = st.selectbox("👤 Выберите клиента", cl_list['name'], index=default_index, key="card_client_select")
    c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
    
    with engine.connect() as conn:
        c_info = conn.execute(text("""
            SELECT name, phone, contract_no, comment, total_amount, passport, snils, inn, address 
            FROM clients WHERE id = :id
        """), {"id": c_id}).fetchone()
    
    # Общие метрики сверху
    c1, c2, c3 = st.columns(3)
    c1.metric("📞 Телефон", c_info[1] if c_info[1] else "—")
    c2.metric("📄 Договор", f"№{c_info[2]}" if c_info[2] else "—")
    c3.metric("💰 Сумма", f"{c_info[4]:,.0f} ₽")

    st.divider()
    
    # Внутренние вкладки
    inner_tab1, inner_tab2, inner_tab3 = st.tabs(["📝 Данные клиента", "📎 Документы", "💳 Финансы и Договор"])

    # --- Вкладка 1: Редактирование ---
    with inner_tab1:
        with st.form(f"f_edit_{c_id}"):
            un = st.text_input("ФИО", value=c_info[0] or "")
            up = st.text_input("Телефон", value=c_info[1] or "")
            uc = st.text_input("Номер договора", value=c_info[2] or "")

            st.markdown("### 🪪 Документы (текст)")
            upass = st.text_input("Паспорт", value=c_info[5] or "")
            usnils = st.text_input("СНИЛС", value=c_info[6] or "")
            uinn = st.text_input("ИНН", value=c_info[7] or "")
            uaddr = st.text_input("Адрес", value=c_info[8] or "")

            ucm = st.text_area("Комментарий", value=c_info[3] or "")

            if st.form_submit_button("Сохранить изменения", type="primary"):
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE clients 
                        SET name=:n, phone=:p, contract_no=:c, comment=:cm,
                            passport=:pass, snils=:snils, inn=:inn, address=:addr
                        WHERE id=:id
                    """), {
                        "n": un, "p": up, "c": uc, "cm": ucm,
                        "pass": upass, "snils": usnils,
                        "inn": uinn, "addr": uaddr,
                        "id": c_id
                    })
                st.success("Данные успешно сохранены")
                st.rerun()

        st.divider()
        with st.expander("⚠️ Опасная зона: Удаление клиента"):
            st.warning("Внимание! Удаление клиента приведет к безвозвратному удалению всех его данных.")
            confirm_delete = st.checkbox("Я понимаю последствия и хочу удалить этого клиента", key=f"conf_del_{c_id}")
            
            if st.button("🗑️ Удалить клиента навсегда", type="primary", disabled=not confirm_delete, use_container_width=True):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM client_files WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM logs WHERE client_id = :id"), {"id": c_id})
                    conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                
                st.success("Клиент и все его данные успешно удалены!")
                st.rerun()

    # --- Вкладка 2: Файлы и OCR ---
    with inner_tab2:
        st.subheader("📎 Загрузка документов")

        doc_type = st.selectbox(
            "Тип документа",
            ["passport", "snils", "inn"],
            format_func=lambda x: {"passport": "Паспорт", "snils": "СНИЛС", "inn": "ИНН"}[x]
        )

        uploaded_doc = st.file_uploader("Загрузить файл", type=["png", "jpg", "jpeg", "pdf"], key=f"upload_{c_id}")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("🤖 Распознать (OCR)", key=f"ocr_{c_id}"):
                if uploaded_doc:
                    with st.spinner("Распознаем текст..."):
                        # ИСПОЛЬЗУЕМ НАШ НОВЫЙ МОДУЛЬ
                        result = process_document_image(uploaded_doc.getvalue())
                        
                        if result["success"]:
                            with engine.begin() as conn:
                                if doc_type == "snils" and result["snils"]:
                                    conn.execute(text("UPDATE clients SET snils=:v WHERE id=:id"), {"v": result["snils"], "id": c_id})
                                if doc_type == "inn" and result["inn"]:
                                    conn.execute(text("UPDATE clients SET inn=:v WHERE id=:id"), {"v": result["inn"], "id": c_id})
                                if doc_type == "passport" and result["passport"]:
                                    conn.execute(text("UPDATE clients SET passport=:v WHERE id=:id"), {"v": result["passport"], "id": c_id})
                            st.success("Распознано и сохранено в профиль!")
                            st.rerun()
                        else:
                            st.error(f"Ошибка при чтении: {result.get('error', 'Неизвестная ошибка')}")

        with col2:
            if st.button("💾 Сохранить файл в базу", key=f"save_file_{c_id}"):
                if uploaded_doc:
                    file_bytes = uploaded_doc.getvalue()
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO client_files (client_id, filename, file_type, file_data) VALUES (:cid, :name, :type, :data)"),
                                     {"cid": c_id, "name": uploaded_doc.name, "type": doc_type, "data": file_bytes})
                    st.success("Файл прикреплен")
                    st.rerun()

        st.divider()
        st.markdown("### 📂 Загруженные файлы")
        with engine.connect() as conn:
            files_df = pd.read_sql(text("SELECT id, filename, file_type FROM client_files WHERE client_id = :id"), conn, params={"id": c_id})
        
        if not files_df.empty and 'file_type' in files_df.columns:
            for doc in ["passport", "snils", "inn"]:
                doc_files = files_df[files_df['file_type'] == doc]
                if not doc_files.empty:
                    st.markdown(f"**{doc.upper()}**")
                    # 👇 ОБНОВЛЕННЫЙ ВЫВОД ФАЙЛОВ С ПРОСМОТРОМ 👇
                    for _, f in doc_files.iterrows():
                        with st.expander(f"📄 {f['filename']}"):
                            # Достаем сам файл из базы только при открытии спойлера (экономим память)
                            file_data = conn.execute(
                                text("SELECT file_data FROM client_files WHERE id=:id"), 
                                {"id": int(f['id'])}
                            ).scalar()
                            
                            # Показываем картинку
                            if f['filename'].lower().endswith(('png', 'jpg', 'jpeg')):
                                st.image(file_data, use_container_width=True)
                            else:
                                st.download_button("📥 Скачать PDF", data=file_data, file_name=f['filename'], mime="application/pdf", key=f"dl_{f['id']}")
                            
                            # Кнопка удаления
                            if st.button("🗑️ Удалить этот документ", key=f"del_{f['id']}", type="primary"):
                                with engine.begin() as conn_del:
                                    conn_del.execute(text("DELETE FROM client_files WHERE id=:id"), {"id": int(f['id'])})
                                st.rerun()
        else:
            st.info("Нет прикрепленных файлов")

    # --- Вкладка 3: Финансы и Договор ---
    with inner_tab3:
        st.info("💡 Здесь вы можете редактировать график платежей и расходы.")

        with engine.connect() as conn:
            curr_payments = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
            curr_expenses = pd.read_sql(text("SELECT id, description, date, amount, status FROM expenses WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})

        with st.form(key=f"fin_form_{c_id}"):
            st.subheader("💰 Доходы (График платежей)")
            updated_payments = []
            if not curr_payments.empty:
                for i, row in curr_payments.iterrows():
                    p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 0.5])
                    with p_col1:
                        d_val = st.date_input(f"Дата {i+1}", row["date"], key=f"d_inc_{row['id']}")
                    with p_col2:
                        a_val = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"a_inc_{row['id']}")
                    with p_col3:
                        s_val = st.selectbox(f"Статус {i+1}", ["Ожидается", "ОПЛАЧЕНО"], 
                                            index=0 if row["status"] == "Ожидается" else 1, key=f"s_inc_{row['id']}")
                    with p_col4:
                        del_p = st.checkbox("🗑️", key=f"del_inc_{row['id']}")
                    
                    if not del_p:
                        updated_payments.append({"id": row["id"], "date": d_val, "amount": a_val, "status": s_val})
            else:
                st.write("Платежей не найдено.")

            st.divider()

            st.subheader("💸 Расходы по сделке")
            updated_expenses = []
            if not curr_expenses.empty:
                for i, row in curr_expenses.iterrows():
                    e_col1, e_col2, e_col3, e_col4, e_col5 = st.columns([2, 1.5, 1.5, 1.5, 0.5])
                    with e_col1:
                        desc_v = st.text_input(f"Описание {i+1}", value=row["description"], key=f"e_desc_{row['id']}")
                    with e_col2:
                        ed_v = st.date_input(f"Дата {i+1}", row["date"], key=f"e_date_{row['id']}")
                    with e_col3:
                        ea_v = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"e_am_{row['id']}")
                    with e_col4:
                        es_v = st.selectbox(f"Статус {i+1}", ["Планируется", "ОПЛАЧЕНО"], 
                                           index=0 if row["status"] == "Планируется" else 1, key=f"e_st_{row['id']}")
                    with e_col5:
                        del_e = st.checkbox("🗑️", key=f"del_exp_{row['id']}")
                    
                    if not del_e:
                        updated_expenses.append({"id": row["id"], "desc": desc_v, "date": ed_v, "amount": ea_v, "status": es_v})
            
            st.markdown("**➕ Добавить новый расход**")
            new_exp_col1, new_exp_col2, new_exp_col3 = st.columns([3, 2, 2])
            with new_exp_col1:
                new_e_desc = st.text_input("Описание нового расхода", key=f"new_e_desc_{c_id}")
            with new_exp_col2:
                new_e_am = st.number_input("Сумма", value=0.0, key=f"new_e_am_{c_id}")
            with new_exp_col3:
                new_e_date = st.date_input("Дата", value=datetime.now(), key=f"new_e_date_{c_id}")

            submit_all = st.form_submit_button("💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ", use_container_width=True, type="primary")

            if submit_all:
                with engine.begin() as conn:
                    # Обновляем доходы
                    existing_p_ids = [p["id"] for p in updated_payments]
                    conn.execute(text("DELETE FROM schedule WHERE client_id = :cid AND id NOT IN :ids"), 
                                 {"cid": c_id, "ids": tuple(existing_p_ids) if existing_p_ids else (0,)})
                    for p in updated_payments:
                        conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:id"), 
                                     {"d": p["date"], "a": p["amount"], "s": p["status"], "id": p["id"]})

                    # Обновляем расходы
                    existing_e_ids = [e["id"] for e in updated_expenses]
                    conn.execute(text("DELETE FROM expenses WHERE client_id = :cid AND id NOT IN :ids"), 
                                 {"cid": c_id, "ids": tuple(existing_e_ids) if existing_e_ids else (0,)})
                    for e in updated_expenses:
                        conn.execute(text("UPDATE expenses SET description=:desc, date=:d, amount=:a, status=:s WHERE id=:id"), 
                                     {"desc": e["desc"], "d": e["date"], "a": e["amount"], "s": e["status"], "id": e["id"]})
                    
                    if new_e_desc:
                        conn.execute(text("INSERT INTO expenses (client_id, description, amount, date, status) VALUES (:cid, :desc, :am, :dt, 'Планируется')"),
                                     {"cid": c_id, "desc": new_e_desc, "am": new_e_am, "dt": new_e_date})

                st.success("Все финансовые данные обновлены!")
                st.rerun()

        # Генерация PDF
        st.divider()
        st.subheader("📄 Договор")
        if st.button("Сгенерировать PDF", key=f"gen_pdf_final_{c_id}"):
            with st.spinner("Создаем документ..."):
                with engine.connect() as conn:
                    tpl = conn.execute(text("SELECT content FROM contract_templates LIMIT 1")).fetchone()
                    contract_text = tpl[0] if tpl else ""
                
                # ИСПОЛЬЗУЕМ НАШ НОВЫЙ МОДУЛЬ
                pdf_file = generate_contract_pdf(c_info, curr_payments, contract_text)
                
                st.download_button("📥 Скачать PDF", data=pdf_file, file_name=f"contract_{c_info[0]}.pdf", mime="application/pdf")
