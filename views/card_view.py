import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, date

from utils.ocr_engine import process_document_image
from utils.pdf_generator import generate_contract_pdf
from utils.word_generator import get_client_context, generate_word_document, generate_mail_batch

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
        c_info_row = conn.execute(text("SELECT * FROM clients WHERE id = :id"), {"id": c_id}).fetchone()
        c_info = c_info_row._mapping if c_info_row else {}
        auth_bodies_list = pd.read_sql("SELECT id, name, address FROM authorized_bodies ORDER BY name", conn).to_dict('records')
        creditor_catalog = pd.read_sql("SELECT id, name, address FROM creditor_catalog ORDER BY name", conn).to_dict('records')
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📞 Телефон", c_info.get('phone') or "—")
    c2.metric("📄 Договор", f"№{c_info.get('contract_no')}" if c_info.get('contract_no') else "—")
    c3.metric("💰 Сумма", f"{c_info.get('total_amount') or 0:,.0f} ₽")
    st.divider()
    
    # 👇 ВОТ ЗДЕСЬ ДОБАВЛЕНА 6-Я ВКЛАДКА tab_mail 👇
    tab_main, tab_docs, tab_fin, tab_cred, tab_prop, tab_mail = st.tabs(["📝 Данные", "📎 Документы", "💳 Финансы", "🏦 Кредиторы", "🏠 Имущество", "✉️ Почта"])

    # --- Вкладка 1: Данные ---
    with tab_main:
        with st.form(f"f_edit_{c_id}"):
            st.markdown("### 👤 Основные данные")
            f_col1, f_col2, f_col3 = st.columns(3)
            ulast = f_col1.text_input("Фамилия", value=c_info.get('last_name') or "")
            ufirst = f_col2.text_input("Имя", value=c_info.get('first_name') or "")
            upat = f_col3.text_input("Отчество", value=c_info.get('patronymic') or "")
            
            uprev_names = st.text_input("Прежние ФИО (если менялись)", value=c_info.get('previous_names') or "", help="Укажите через запятую прежние фамилии или имена")

            p_col1, p_col2 = st.columns(2)
            up = p_col1.text_input("Телефон", value=c_info.get('phone') or "")
            uc = p_col2.text_input("Номер договора", value=c_info.get('contract_no') or "")

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🪪 Данные паспорта")
                upass = st.text_input("Серия и номер паспорта", value=c_info.get('passport_series') or c_info.get('passport') or "")
                upass_issued = st.text_input("Когда и кем выдан", value=c_info.get('passport_issued_by') or "")
                usnils = st.text_input("СНИЛС", value=c_info.get('snils') or "")
                uinn = st.text_input("ИНН", value=c_info.get('inn') or "")
            
            with col2:
                st.markdown("### 👨‍👩‍👧 Должник (Личные данные)")
                ubirthd = st.date_input("Дата рождения", value=c_info.get('birth_date') if c_info.get('birth_date') else date(1980, 1, 1))
                ubirthp = st.text_input("Место рождения", value=c_info.get('birth_place') or "")
                
                ms_list = ["Холост / Не замужем", "В браке", "В разводе", "Вдовец / Вдова"]
                ms_index = ms_list.index(c_info.get('marital_status')) if c_info.get('marital_status') in ms_list else 0
                umarital = st.selectbox("Семейное положение должника", ms_list, index=ms_index)
                udep = st.number_input("Иждивенцы (дети) должника", min_value=0, value=c_info.get('dependents') if c_info.get('dependents') else 0)

            st.divider()
            st.markdown("### 📍 Адрес регистрации")
            a_col1, a_col2, a_col3 = st.columns(3)
            azip = a_col1.text_input("Почтовый индекс", value=c_info.get('addr_zip') or "")
            areg = a_col2.text_input("Регион", value=c_info.get('addr_region') or "")
            adist = a_col3.text_input("Район", value=c_info.get('addr_district') or "")

            a_col4, a_col5, a_col6 = st.columns(3)
            acity = a_col4.text_input("Город", value=c_info.get('addr_city') or "")
            aset = a_col5.text_input("Населенный пункт", value=c_info.get('addr_settlement') or "")
            astr = a_col6.text_input("Улица", value=c_info.get('addr_street') or "")

            a_col7, a_col8, a_col9 = st.columns(3)
            ahouse = a_col7.text_input("Дом", value=c_info.get('addr_house') or "")
            acorp = a_col8.text_input("Корпус", value=c_info.get('addr_corpus') or "")
            aflat = a_col9.text_input("Квартира", value=c_info.get('addr_flat') or "")

            st.divider()
            b_col1, b_col2 = st.columns(2)
            with b_col1:
                st.markdown("### 🏛 Суд и СРО")
                ucourt = st.text_input("Арбитражный суд", value=c_info.get('court_name') or "", help="Например: Арбитражный суд г. Москвы")
                usro = st.text_area("Сведения о СРО", value=c_info.get('sro_name') or "", help="Введите полное название, адрес и данные СРО")
            with b_col2:
                st.markdown("### 💍 Сведения о супруге (бывшем)")
                uspouse_name = st.text_input("ФИО супруга(и)", value=c_info.get('spouse_name') or "")
                uspouse_addr = st.text_input("Адрес супруга(и)", value=c_info.get('spouse_address') or "")

            st.markdown("#### 🏢 Уполномоченный орган")
            ab_options = ["Не выбран"] + [ab['name'] for ab in auth_bodies_list] + ["➕ Добавить новый..."]
            current_ab_name = next((ab['name'] for ab in auth_bodies_list if ab['id'] == c_info.get('auth_body_id')), "Не выбран")
            sel_ab = st.selectbox("Выберите из списка или добавьте новый", ab_options, index=ab_options.index(current_ab_name) if current_ab_name in ab_options else 0)
            
            new_ab_name, new_ab_addr = "", ""
            if sel_ab == "➕ Добавить новый...":
                st.info("Орган сохранится в общую базу для всех клиентов.")
                new_ab_name = st.text_input("Наименование нового органа")
                new_ab_addr = st.text_input("Адрес нового органа")

            ucm = st.text_area("Комментарий", value=c_info.get('comment') or "")

            if st.form_submit_button("Сохранить изменения", type="primary"):
                full_name = f"{ulast} {ufirst} {upat}".strip()
                with engine.begin() as conn:
                    final_ab_id = c_info.get('auth_body_id')
                    if sel_ab == "➕ Добавить новый..." and new_ab_name:
                        res = conn.execute(text("INSERT INTO authorized_bodies (name, address) VALUES (:n, :a) RETURNING id"), {"n": new_ab_name, "a": new_ab_addr}).fetchone()
                        final_ab_id = res[0]
                    elif sel_ab != "Не выбран" and sel_ab != "➕ Добавить новый...":
                        final_ab_id = next((ab['id'] for ab in auth_bodies_list if ab['name'] == sel_ab), None)
                    elif sel_ab == "Не выбран":
                        final_ab_id = None

                    conn.execute(text("""
                        UPDATE clients 
                        SET name=:n, last_name=:ln, first_name=:fn, patronymic=:pat, previous_names=:prev, phone=:p, contract_no=:c, comment=:cm, 
                            passport_series=:pass, passport_issued_by=:pass_issued, snils=:snils, inn=:inn,
                            birth_date=:bd, birth_place=:bp, court_name=:court, sro_name=:sro,
                            marital_status=:ms, dependents=:dep, spouse_name=:sname, spouse_address=:saddr, auth_body_id=:ab_id,
                            addr_zip=:azip, addr_region=:areg, addr_district=:adist, addr_city=:acity, addr_settlement=:aset,
                            addr_street=:astr, addr_house=:ahouse, addr_corpus=:acorp, addr_flat=:aflat
                        WHERE id=:id
                    """), {
                        "n": full_name, "ln": ulast, "fn": ufirst, "pat": upat, "prev": uprev_names, "p": up, "c": uc, "cm": ucm, "pass": upass, "pass_issued": upass_issued, 
                        "snils": usnils, "inn": uinn, "bd": ubirthd, "bp": ubirthp, "court": ucourt, "sro": usro, "ms": umarital, "dep": udep, 
                        "sname": uspouse_name, "saddr": uspouse_addr, "ab_id": final_ab_id, "azip": azip, "areg": areg, "adist": adist, "acity": acity, "aset": aset,
                        "astr": astr, "ahouse": ahouse, "acorp": acorp, "aflat": aflat, "id": c_id
                    })
                st.success("Данные успешно сохранены")
                st.rerun()

        st.divider()
        with st.expander("⚠️ Опасная зона: Удаление клиента"):
            if st.button("🗑️ Удалить клиента навсегда", type="primary", use_container_width=True):
                with engine.begin() as conn: conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
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
                    result = process_document_image(uploaded_doc.getvalue())
                    if result["success"]:
                        with engine.begin() as conn:
                            if doc_type == "snils" and result["snils"]: conn.execute(text("UPDATE clients SET snils=:v WHERE id=:id"), {"v": result["snils"], "id": c_id})
                            if doc_type == "inn" and result["inn"]: conn.execute(text("UPDATE clients SET inn=:v WHERE id=:id"), {"v": result["inn"], "id": c_id})
                            if doc_type == "passport" and result["passport"]: conn.execute(text("UPDATE clients SET passport_series=:v WHERE id=:id"), {"v": result["passport"], "id": c_id})
                        st.rerun()
        with col2:
            if st.button("💾 Сохранить файл", key=f"save_file_{c_id}"):
                if uploaded_doc:
                    with engine.begin() as conn: conn.execute(text("INSERT INTO client_files (client_id, filename, file_type, file_data) VALUES (:cid, :name, :type, :data)"), {"cid": c_id, "name": uploaded_doc.name, "type": doc_type, "data": uploaded_doc.getvalue()})
                    st.rerun()

        st.divider()
        with engine.connect() as conn: files_df = pd.read_sql(text("SELECT id, filename, file_type FROM client_files WHERE client_id = :id"), conn, params={"id": c_id})
        if not files_df.empty:
            for _, f in files_df.iterrows():
                with st.expander(f"📄 {f['filename']}"):
                    file_data = conn.execute(text("SELECT file_data FROM client_files WHERE id=:id"), {"id": int(f['id'])}).scalar()
                    if f['filename'].lower().endswith(('png', 'jpg', 'jpeg')): st.image(file_data, use_container_width=True)
                    else: st.download_button("Скачать", data=file_data, file_name=f['filename'])
                    if st.button("🗑️ Удалить", key=f"del_{f['id']}", type="primary"):
                        with engine.begin() as conn_del: conn_del.execute(text("DELETE FROM client_files WHERE id=:id"), {"id": int(f['id'])})
                        st.rerun()

        st.divider()
        st.subheader("🖨️ Генерация документов (Банкротство)")
        col_w1, col_w2, col_w3 = st.columns(3)
        context = get_client_context(engine, c_id)
        with col_w1:
            if st.button("📄 Заявление", use_container_width=True):
                doc_bytes = generate_word_document("templates/zayavlenie.docx", context)
                if doc_bytes: st.download_button("📥 Скачать Заявление", data=doc_bytes, file_name=f"Заявление_{c_info.get('last_name')}.docx")
                else: st.error("Не найден шаблон templates/zayavlenie.docx")
        with col_w2:
            if st.button("🏦 Список кредиторов", use_container_width=True):
                doc_bytes = generate_word_document("templates/kreditory.docx", context)
                if doc_bytes: st.download_button("📥 Скачать Кредиторов", data=doc_bytes, file_name=f"Кредиторы_{c_info.get('last_name')}.docx")
                else: st.error("Не найден шаблон templates/kreditory.docx")
        with col_w3:
            if st.button("🏠 Опись", use_container_width=True):
                doc_bytes = generate_word_document("templates/opis.docx", context)
                if doc_bytes: st.download_button("📥 Скачать Опись", data=doc_bytes, file_name=f"Опись_{c_info.get('last_name')}.docx")
                else: st.error("Не найден шаблон templates/opis.docx")

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
            
            new_exp_col1, new_exp_col1a, new_exp_col2, new_exp_col3 = st.columns([2, 1.5, 1.5, 1.5])
            with new_exp_col1: new_e_desc = st.text_input("Описание нового расхода", key=f"new_e_desc_{c_id}")
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
                st.rerun()

        st.divider()
        st.subheader("📄 Договор услуг (PDF)")
        if st.button("Сгенерировать PDF", key=f"gen_pdf_{c_id}", type="primary"):
            with st.spinner("Создаем PDF..."):
                with engine.connect() as conn:
                    tpl = conn.execute(text("SELECT content FROM contract_templates LIMIT 1")).fetchone()
                    contract_text = tpl[0] if tpl else ""
                    
                    comp_row = conn.execute(text("SELECT * FROM company_profile LIMIT 1")).fetchone()
                    comp_profile = comp_row._mapping if comp_row else {}
                
                old_c_info = (
                    c_info.get('name', ''), c_info.get('phone', ''), c_info.get('contract_no', ''),
                    c_info.get('comment', ''), c_info.get('total_amount', 0), 
                    c_info.get('passport_series', ''), c_info.get('snils', ''), 
                    c_info.get('inn', ''), c_info.get('addr_city', '')
                )
                
                pdf_file = generate_contract_pdf(old_c_info, curr_payments, contract_text, comp_profile)
                
                st.download_button("📥 Скачать PDF договор", data=pdf_file, file_name=f"contract_{c_info.get('last_name')}.pdf", mime="application/pdf")

    # --- Вкладка 4: Кредиторы ---
    with tab_cred:
        st.subheader("🏦 Управление кредиторами")
        c_options = ["Не выбран"] + [c['name'] for c in creditor_catalog] + ["➕ Добавить нового кредитора..."]
        sel_creditor = st.selectbox("Выберите из базы или добавьте нового", c_options)

        c_name, c_addr = "", ""
        if sel_creditor == "➕ Добавить нового кредитора...":
            st.info("Введите данные нового кредитора. Он навсегда сохранится в общей базе.")
            c_name = st.text_input("Наименование кредитора (например: ПАО Сбербанк)")
            c_addr = st.text_input("Адрес кредитора")
        elif sel_creditor != "Не выбран":
            c_name = sel_creditor
            cat_match = next((c for c in creditor_catalog if c['name'] == sel_creditor), None)
            c_addr = st.text_input("Адрес кредитора (можно уточнить для этого дела)", value=cat_match['address'] if cat_match else "")

        c_contracts = st.text_area("Договоры (каждый с новой строки)", help="Пример:\n0607-Р-11838335560 от 19.01.2024\n1811950 от 20.09.2024")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        c_principal = col_c1.number_input("Основной долг, ₽", min_value=0.0, step=1000.0)
        c_penalty = col_c2.number_input("Неустойка (пени, штрафы), ₽", min_value=0.0, step=1000.0)
        c_total = col_c3.number_input("Общая сумма долга, ₽", min_value=0.0, value=c_principal+c_penalty, step=1000.0)

        if st.button("➕ Прикрепить кредитора к делу", type="primary"):
            if c_name:
                with engine.begin() as conn:
                    if sel_creditor == "➕ Добавить нового кредитора...":
                        conn.execute(text("INSERT INTO creditor_catalog (name, address) VALUES (:n, :a)"), {"n": c_name, "a": c_addr})
                    
                    conn.execute(text("""
                        INSERT INTO creditors (client_id, creditor_name, creditor_address, contracts_info, principal_debt, penalty_debt, debt_amount) 
                        VALUES (:cid, :name, :addr, :contracts, :prin, :pen, :tot)
                    """), {
                        "cid": c_id, "name": c_name, "addr": c_addr, "contracts": c_contracts,
                        "prin": c_principal, "pen": c_penalty, "tot": c_total
                    })
                st.success("Кредитор успешно добавлен!")
                st.rerun()

        st.divider()
        st.markdown("### Прикрепленные кредиторы")
        with engine.connect() as conn: 
            creditors_df = pd.read_sql(text("SELECT * FROM creditors WHERE client_id = :id"), conn, params={"id": c_id})
        
        if not creditors_df.empty:
            for _, row in creditors_df.iterrows():
                with st.expander(f"🏦 {row['creditor_name']} — {row['debt_amount']:,.0f} ₽"):
                    st.write(f"**Адрес:** {row['creditor_address']}")
                    st.write(f"**Основной долг:** {row.get('principal_debt', 0):,.0f} ₽ | **Неустойка:** {row.get('penalty_debt', 0):,.0f} ₽")
                    st.write("**Договоры:**")
                    if row.get('contracts_info'):
                        for line in row['contracts_info'].split('\n'):
                            if line.strip(): st.caption(f"• {line}")
                    if st.button("🗑️ Удалить", key=f"del_cred_{row['id']}"):
                        with engine.begin() as conn: conn.execute(text("DELETE FROM creditors WHERE id = :id"), {"id": row['id']})
                        st.rerun()
            st.info(f"Общая сумма всех долгов: **{creditors_df['debt_amount'].sum():,.0f} ₽**")
        else: st.write("Нет прикрепленных кредиторов.")

    # --- Вкладка 5: Имущество ---
    with tab_prop:
        st.subheader("🏠 Имущество и активы")
        with st.form(f"add_prop_{c_id}", clear_on_submit=True):
            col1, col2, col3, col4 = st.columns([1.5, 3, 1.5, 1])
            with col1: p_type = st.selectbox("Тип", ["Недвижимость", "Транспорт", "Счета/Вклады", "Иное"])
            with col2: p_desc = st.text_input("Описание (Адрес / Марка авто)")
            with col3: p_val = st.number_input("Оценочная стоимость, ₽", min_value=0.0, step=10000.0)
            with col4: p_pledged = st.checkbox("В залоге?")
            if st.form_submit_button("➕ Добавить имущество", type="primary"):
                if p_desc:
                    with engine.begin() as conn: conn.execute(text("INSERT INTO properties (client_id, property_type, description, estimated_value, is_pledged) VALUES (:cid, :ptype, :desc, :val, :pledged)"), {"cid": c_id, "ptype": p_type, "desc": p_desc, "val": p_val, "pledged": p_pledged})
                    st.rerun()

        st.divider()
        with engine.connect() as conn: props_df = pd.read_sql(text("SELECT id, property_type, description, estimated_value, is_pledged FROM properties WHERE client_id = :id"), conn, params={"id": c_id})
        if not props_df.empty:
            for _, row in props_df.iterrows():
                pc1, pc2, pc3, pc4, pc5 = st.columns([2, 3, 2, 1, 1])
                pc1.write(row['property_type'])
                pc2.write(f"**{row['description']}**")
                pc3.write(f"{row['estimated_value']:,.0f} ₽")
                pc4.write("🔒 Да" if row['is_pledged'] else "—")
                if pc5.button("🗑️", key=f"del_prop_{row['id']}"):
                    with engine.begin() as conn: conn.execute(text("DELETE FROM properties WHERE id = :id"), {"id": row['id']})
                    st.rerun()
        else: st.write("Имущество пока не добавлено.")

    # --- Вкладка 6: Почта и конверты ---
    with tab_mail:
        st.subheader("🖨️ Печать конвертов и уведомлений")
        st.markdown("Выберите адресатов, и система сгенерирует файл сразу со всеми конвертами для печати.")

        mail_data = []
        
        # 1. Суд
        if c_info.get('court_name'):
            mail_data.append({"Отправить": True, "Роль": "Суд", "Получатель": c_info.get('court_name'), "Адрес": ""})
        
        # 2. Уполномоченный орган
        ab_name = next((ab['name'] for ab in auth_bodies_list if ab['id'] == c_info.get('auth_body_id')), None)
        ab_addr = next((ab['address'] for ab in auth_bodies_list if ab['id'] == c_info.get('auth_body_id')), None)
        if ab_name:
            mail_data.append({"Отправить": True, "Роль": "Гос. орган", "Получатель": ab_name, "Адрес": ab_addr or ""})
            
        # 3. Кредиторы
        with engine.connect() as conn: 
            cred_df = pd.read_sql(text("SELECT creditor_name, creditor_address FROM creditors WHERE client_id = :id"), conn, params={"id": c_id})
        for _, r in cred_df.iterrows():
            mail_data.append({"Отправить": True, "Роль": "Кредитор", "Получатель": r['creditor_name'], "Адрес": r['creditor_address']})

        if not mail_data:
            st.info("У клиента пока нет прикрепленных кредиторов, суда или госорганов.")
        else:
            mail_df = pd.DataFrame(mail_data)
            edited_mail_df = st.data_editor(
                mail_df, 
                hide_index=True, 
                use_container_width=True,
                column_config={"Отправить": st.column_config.CheckboxColumn("Печатать?", default=True)}
            )
            
            st.divider()
            
            sender_type = st.radio("Отправитель (в левом верхнем углу):", ["Сам должник (Клиент)", "Представитель (Моя компания)"], horizontal=True)
            
            if sender_type == "Сам должник (Клиент)":
                s_name = c_info.get('name')
                s_address = get_client_context(engine, c_id)["full_address"]
            else:
                with engine.connect() as conn:
                    comp = conn.execute(text("SELECT company_name, address FROM company_profile LIMIT 1")).fetchone()
                s_name = comp[0] if comp else "Имя компании"
                s_address = comp[1] if comp else "Адрес компании"

            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                if st.button("✉️ Сгенерировать Конверты", use_container_width=True, type="primary"):
                    doc_bytes = generate_mail_batch("templates/envelope.docx", s_name, s_address, edited_mail_df)
                    if doc_bytes:
                        st.download_button("📥 Скачать Конверты", data=doc_bytes, file_name=f"Конверты_{c_info.get('last_name')}.docx")
                    else:
                        st.error("Ошибка генерации или не найден шаблон templates/envelope.docx")

            with col_m2:
                if st.button("📄 Сгенерировать Уведомления (ф.119)", use_container_width=True):
                    doc_bytes = generate_mail_batch("templates/form_119.docx", s_name, s_address, edited_mail_df)
                    if doc_bytes:
                        st.download_button("📥 Скачать ф.119", data=doc_bytes, file_name=f"Уведомления_{c_info.get('last_name')}.docx")
                    else:
                        st.error("Ошибка генерации или не найден шаблон templates/form_119.docx")
