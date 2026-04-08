# ... (начало файла без изменений)
    with tab_main:
        with st.form(f"f_edit_{c_id}"):
            st.markdown("### 👤 Основные данные")
            f_col1, f_col2, f_col3 = st.columns(3)
            ulast = f_col1.text_input("Фамилия", value=c_info.get('last_name') or "")
            ufirst = f_col2.text_input("Имя", value=c_info.get('first_name') or "")
            upat = f_col3.text_input("Отчество", value=c_info.get('patronymic') or "")
            
            # 👇 НОВОЕ ПОЛЕ ЗДЕСЬ 👇
            uprev_names = st.text_input("Прежние ФИО (если менялись)", value=c_info.get('previous_names') or "", help="Укажите через запятую прежние фамилии или имена")

            p_col1, p_col2 = st.columns(2)
            up = p_col1.text_input("Телефон", value=c_info.get('phone') or "")
            uc = p_col2.text_input("Номер договора", value=c_info.get('contract_no') or "")

            # ... (середина файла без изменений)

            st.divider()
            b_col1, b_col2 = st.columns(2)
            with b_col1:
                st.markdown("### 🏛 Суд и СРО")
                ucourt = st.text_input("Арбитражный суд", value=c_info.get('court_name') or "")
                # 👇 ИЗМЕНИЛИ НА TEXT_AREA 👇
                usro = st.text_area("Сведения о СРО", value=c_info.get('sro_name') or "", help="Введите полное название, адрес и данные СРО")
            # ... (сохранение данных)
            if st.form_submit_button("Сохранить изменения", type="primary"):
                full_name = f"{ulast} {ufirst} {upat}".strip()
                with engine.begin() as conn:
                    # ... (логика с AB)
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
                        "n": full_name, "ln": ulast, "fn": ufirst, "pat": upat, 
                        "prev": uprev_names, # 👈 Сохраняем новое поле
                        "p": up, "c": uc, "cm": ucm, "pass": upass, "pass_issued": upass_issued, 
                        "snils": usnils, "inn": uinn, "bd": ubirthd, "bp": ubirthp, "court": ucourt, "sro": usro, "ms": umarital, "dep": udep, 
                        "sname": uspouse_name, "saddr": uspouse_addr, "ab_id": final_ab_id, "azip": azip, "areg": areg, "adist": adist, "acity": acity, "aset": aset,
                        "astr": astr, "ahouse": ahouse, "acorp": acorp, "aflat": aflat, "id": c_id
                    })
                st.success("Данные успешно сохранены")
                st.rerun()
# ... (остальной файл)
