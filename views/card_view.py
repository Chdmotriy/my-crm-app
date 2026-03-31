import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

from utils.ocr_engine import process_document_image
from utils.pdf_generator import generate_contract_pdf
from utils.word_generator import get_client_context, generate_word_document

def render(engine):
    st.subheader("🔍 Карточка клиента")
    
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if cl_list.empty:
        st.info("База клиентов пуста.")
        return

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
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📞 Телефон", c_info[1] if c_info[1] else "—")
    c2.metric("📄 Договор", f"№{c_info[2]}" if c_info[2] else "—")
    c3.metric("💰 Сумма", f"{c_info[4]:,.0f} ₽")

    st.divider()
    
    # 👇 ТЕПЕРЬ У НАС 5 ВКЛАДОК 👇
    tab_main, tab_docs, tab_fin, tab_cred, tab_prop = st.tabs([
        "📝 Данные", "📎 Документы", "💳 Финансы", "🏦 Кредиторы", "🏠 Имущество"
    ])

    # --- Вкладка 1: Данные ---
    with tab_main:
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
                        "inn": uinn, "addr": uaddr, "id": c_id
                    })
                st.success("Данные успешно сохранены")
                st.rerun()

        st.divider()
        with st.expander("⚠️ Опасная зона: Удаление клиента"):
            st.warning("Внимание! Удаление клиента приведет к безвозвратному удалению всех его данных.")
            confirm_delete = st.checkbox("Я понимаю последствия и хочу удалить этого клиента", key=f"conf_del_{c_id}")
            if st.button("🗑️ Удалить клиента навсегда", type="primary", disabled=not confirm_delete, use_container_width=True):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                st.success("Клиент удален!")
                st.rerun()

    # --- Вкладка 2: Документы ---
    with tab_docs:
        st.subheader("📎 Загрузка документов")
        doc_type = st.selectbox("Тип документа", ["passport", "snils", "inn"], format_func=lambda x: {"passport": "Паспорт", "snils": "СНИЛС", "inn": "ИНН"}[x])
        uploaded_doc = st.file_uploader("Загрузить файл", type=["png", "jpg", "jpeg", "pdf"], key=f"upload_{c_id}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 Распознать (OCR)", key=f"ocr_{c_id}"):
                if uploaded_doc:
                    with st.spinner("Распознаем текст..."):
                        result = process_document_image(uploaded_doc.getvalue())
                        if result["success"]:
                            with engine.begin() as conn:
                                if doc_type == "snils" and result["snils"]: conn.execute(text("UPDATE clients SET snils=:v WHERE id=:id"), {"v": result["snils"], "id": c_id})
                                if doc_type == "inn" and result["inn"]: conn.execute(text("UPDATE clients SET inn=:v WHERE id=:id"), {"v": result["inn"], "id": c_id})
                                if doc_type == "passport" and result["passport"]: conn.execute(text("UPDATE clients SET passport=:v WHERE id=:id"), {"v": result["passport"], "id": c_id})
                            st.success("Распознано!")
                            st.rerun()
                        else: st.error("Ошибка чтения")
        with col2:
            if st.button("💾 Сохранить файл", key=f"save_file_{c_id}"):
                if uploaded_doc:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO client_files (client_id, filename, file_type, file_data) VALUES (:cid, :name, :type, :data)"),
                                     {"cid": c_id, "name": uploaded_doc.name, "type": doc_type, "data": uploaded_doc.getvalue()})
                    st.success("Сохранено")
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
                    for _, f in doc_files.iterrows():
                        with st.expander(f"📄 {f['filename']}"):
                            file_data = conn.execute(text("SELECT file_data FROM client_files WHERE id=:id"), {"id": int(f['id'])}).scalar()
                            if f['filename'].lower().endswith(('png', 'jpg', 'jpeg')): st.image(file_data, use_container_width=True)
                            else: st.download_button("Скачать", data=file_data, file_name=f['filename'], mime="application/pdf", key=f"dl_{f['id']}")
                            if st.button("🗑️ Удалить", key=f"del_{f['id']}", type="primary"):
                                with engine.begin() as conn_del: conn_del.execute(text("DELETE FROM client_files WHERE id=:id"), {"id": int(f['id'])})
                                st.rerun()
        else: st.info("Нет файлов")
# 👇 ДОБАВЛЯЕМ БЛОК ГЕНЕРАЦИИ WORD-ДОКУМЕНТОВ 👇
        st.divider()
        st.subheader("🖨️ Генерация документов (Банкротство)")
        st.info("💡 Убедитесь, что в папке `templates/` в корне проекта лежат файлы шаблонов (zayavlenie.docx, kreditory.docx, opis.docx).")
        
        # Импортируем наш новый генератор (лучше добавить этот импорт в самый верх файла card_view.py)
        from utils.word_generator import get_client_context, generate_word_document
        
        col_w1, col_w2, col_w3 = st.columns(3)
        
        # Подготавливаем данные один раз, чтобы не дергать базу трижды
        context = get_client_context(engine, c_id)
        
        with col_w1:
            if st.button("📄 Заявление", use_container_width=True):
                doc_bytes = generate_word_document("templates/zayavlenie.docx", context)
                if doc_bytes:
                    st.download_button("📥 Скачать Заявление", data=doc_bytes, file_name=f"Заявление_{c_info[0]}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                else:
                    st.error("Шаблон templates/zayavlenie.docx не найден!")
                    
        with col_w2:
            if st.button("🏦 Список кредиторов", use_container_width=True):
                doc_bytes = generate_word_document("templates/kreditory.docx", context)
                if doc_bytes:
                    st.download_button("📥 Скачать Кредиторов", data=doc_bytes, file_name=f"Кредиторы_{c_info[0]}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                else:
                    st.error("Шаблон templates/kreditory.docx не найден!")
                    
        with col_w3:
            if st.button("🏠 Опись имущества", use_container_width=True):
                doc_bytes = generate_word_document("templates/opis.docx", context)
                if doc_bytes:
                    st.download_button("📥 Скачать Опись", data=doc_bytes, file_name=f"Опись_{c_info[0]}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                else:
                    st.error("Шаблон templates/opis.docx не найден!")
    # --- Вкладка 3: Финансы ---
    with tab_fin:
        with engine.connect() as conn:
            curr_payments = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
            curr_expenses = pd.read_sql(text("SELECT id, description, category, date, amount, status FROM expenses WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})

        with st.form(key=f"fin_form_{c_id}"):
            st.subheader("💰 Доходы")
            updated_payments = []
            if not curr_payments.empty:
                for i, row in curr_payments.iterrows():
                    p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 0.5])
                    with p_col1: d_val = st.date_input(f"Дата {i+1}", row["date"], key=f"d_inc_{row['id']}")
                    with p_col2: a_val = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"a_inc_{row['id']}")
                    with p_col3: s_val = st.selectbox(f"Статус {i+1}", ["Ожидается", "ОПЛАЧЕНО"], index=0 if row["status"] == "Ожидается" else 1, key=f"s_inc_{row['id']}")
                    with p_col4: del_p = st.checkbox("🗑️", key=f"del_inc_{row['id']}")
                    if not del_p: updated_payments.append({"id": row["id"], "date": d_val, "amount": a_val, "status": s_val})
            
            st.divider()
            st.subheader("💸 Расходы")
            categories_list = ["Налоги", "Реклама", "Офис", "Пошлины", "Прочее"]
            updated_expenses = []
            if not curr_expenses.empty:
                for i, row in curr_expenses.iterrows():
                    e_col1, e_col1a, e_col2, e_col3, e_col4, e_col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 0.5])
                    with e_col1: desc_v = st.text_input(f"Описание {i+1}", value=row["description"], key=f"e_desc_{row['id']}")
                    with e_col1a: cat_v = st.selectbox(f"Категория {i+1}", categories_list, index=categories_list.index(row["category"] if row["category"] in categories_list else "Прочее"), key=f"e_cat_{row['id']}")
                    with e_col2: ed_v = st.date_input(f"Дата {i+1}", row["date"], key=f"e_date_{row['id']}")
                    with e_col3: ea_v = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"e_am_{row['id']}")
                    with e_col4: es_v = st.selectbox(f"Статус {i+1}", ["Планируется", "ОПЛАЧЕНО"], index=0 if row["status"] == "Планируется" else 1, key=f"e_st_{row['id']}")
                    with e_col5: del_e = st.checkbox("🗑️", key=f"del_exp_{row['id']}")
                    if not del_e: updated_expenses.append({"id": row["id"], "desc": desc_v, "cat": cat_v, "date": ed_v, "amount": ea_v, "status": es_v})
            
            st.markdown("**➕ Новый расход**")
            new_exp_col1, new_exp_col1a, new_exp_col2, new_exp_col3 = st.columns([2, 1.5, 1.5, 1.5])
            with new_exp_col1: new_e_desc = st.text_input("Описание", key=f"new_e_desc_{c_id}")
            with new_exp_col1a: new_e_cat = st.selectbox("Категория", categories_list, index=4, key=f"new_e_cat_{c_id}")
            with new_exp_col2: new_e_am = st.number_input("Сумма", value=0.0, key=f"new_e_am_{c_id}")
            with new_exp_col3: new_e_date = st.date_input("Дата", value=datetime.now(), key=f"new_e_date_{c_id}")

            if st.form_submit_button("💾 СОХРАНИТЬ ФИНАНСЫ", type="primary", use_container_width=True):
                with engine.begin() as conn:
                    existing_p_ids = [p["id"] for p in updated_payments]
                    conn.execute(text("DELETE FROM schedule WHERE client_id = :cid AND id NOT IN :ids"), {"cid": c_id, "ids": tuple(existing_p_ids) if existing_p_ids else (0,)})
                    for p in updated_payments: conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:id"), {"d": p["date"], "a": p["amount"], "s": p["status"], "id": p["id"]})
                    existing_e_ids = [e["id"] for e in updated_expenses]
                    conn.execute(text("DELETE FROM expenses WHERE client_id = :cid AND id NOT IN :ids"), {"cid": c_id, "ids": tuple(existing_e_ids) if existing_e_ids else (0,)})
                    for e in updated_expenses: conn.execute(text("UPDATE expenses SET description=:desc, category=:cat, date=:d, amount=:a, status=:s WHERE id=:id"), {"desc": e["desc"], "cat": e["cat"], "d": e["date"], "a": e["amount"], "s": e["status"], "id": e["id"]})
                    if new_e_desc: conn.execute(text("INSERT INTO expenses (client_id, description, category, amount, date, status) VALUES (:cid, :desc, :cat, :am, :dt, 'Планируется')"), {"cid": c_id, "desc": new_e_desc, "cat": new_e_cat, "am": new_e_am, "dt": new_e_date})
                st.success("Финансы обновлены!")
                st.rerun()

        st.divider()
        st.subheader("📄 Договор услуг")
        if st.button("Сгенерировать PDF", key=f"gen_pdf_{c_id}"):
            with engine.connect() as conn:
                tpl = conn.execute(text("SELECT content FROM contract_templates LIMIT 1")).fetchone()
            pdf_file = generate_contract_pdf(c_info, curr_payments, tpl[0] if tpl else "")
            st.download_button("📥 Скачать PDF", data=pdf_file, file_name=f"contract_{c_info[0]}.pdf", mime="application/pdf")

    # 👇 НОВЫЕ ВКЛАДКИ ДЛЯ БАНКРОТСТВА 👇

    # --- Вкладка 4: Кредиторы ---
    with tab_cred:
        st.subheader("🏦 Список кредиторов (Банки, МФО, физ. лица)")
        
        # Форма добавления кредитора
        with st.form(f"add_creditor_{c_id}", clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1: c_name = st.text_input("Наименование кредитора (например: ПАО Сбербанк)")
            with col2: c_info_doc = st.text_input("Основание (№ договора, дата)")
            with col3: c_amount = st.number_input("Сумма долга, ₽", min_value=0.0, step=1000.0)
            
            if st.form_submit_button("➕ Добавить кредитора", type="primary"):
                if c_name:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO creditors (client_id, creditor_name, contract_info, debt_amount) 
                            VALUES (:cid, :name, :info, :amt)
                        """), {"cid": c_id, "name": c_name, "info": c_info_doc, "amt": c_amount})
                    st.success("Кредитор добавлен!")
                    st.rerun()

        st.divider()
        # Вывод кредиторов
        with engine.connect() as conn:
            creditors_df = pd.read_sql(text("SELECT id, creditor_name, contract_info, debt_amount FROM creditors WHERE client_id = :id"), conn, params={"id": c_id})
        
        if not creditors_df.empty:
            for _, row in creditors_df.iterrows():
                cc1, cc2, cc3, cc4 = st.columns([3, 3, 2, 1])
                cc1.write(f"**{row['creditor_name']}**")
                cc2.caption(f"Договор: {row['contract_info']}")
                cc3.write(f"**{row['debt_amount']:,.0f} ₽**")
                if cc4.button("🗑️", key=f"del_cred_{row['id']}"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM creditors WHERE id = :id"), {"id": row['id']})
                    st.rerun()
            
            st.info(f"Итого долгов: **{creditors_df['debt_amount'].sum():,.0f} ₽**")
        else:
            st.write("Кредиторы пока не добавлены.")

    # --- Вкладка 5: Имущество ---
    with tab_prop:
        st.subheader("🏠 Имущество и активы")
        
        # Форма добавления имущества
        with st.form(f"add_prop_{c_id}", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns([1.5, 3, 1.5, 1])
            with col1: p_type = st.selectbox("Тип", ["Недвижимость", "Транспорт", "Счета/Вклады", "Иное"])
            with col2: p_desc = st.text_input("Описание (Адрес / Марка авто)")
            with col3: p_val = st.number_input("Оценочная стоимость, ₽", min_value=0.0, step=10000.0)
            with col4: p_pledged = st.checkbox("В залоге?")
            
            if st.form_submit_button("➕ Добавить имущество", type="primary"):
                if p_desc:
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO properties (client_id, property_type, description, estimated_value, is_pledged) 
                            VALUES (:cid, :ptype, :desc, :val, :pledged)
                        """), {"cid": c_id, "ptype": p_type, "desc": p_desc, "val": p_val, "pledged": p_pledged})
                    st.success("Имущество добавлено!")
                    st.rerun()

        st.divider()
        # Вывод имущества
        with engine.connect() as conn:
            props_df = pd.read_sql(text("SELECT id, property_type, description, estimated_value, is_pledged FROM properties WHERE client_id = :id"), conn, params={"id": c_id})
        
        if not props_df.empty:
            for _, row in props_df.iterrows():
                pc1, pc2, pc3, pc4, pc5 = st.columns([2, 3, 2, 1, 1])
                pc1.write(row['property_type'])
                pc2.write(f"**{row['description']}**")
                pc3.write(f"{row['estimated_value']:,.0f} ₽")
                pc4.write("🔒 Да" if row['is_pledged'] else "—")
                if pc5.button("🗑️", key=f"del_prop_{row['id']}"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM properties WHERE id = :id"), {"id": row['id']})
                    st.rerun()
        else:
            st.write("Имущество пока не добавлено.")
