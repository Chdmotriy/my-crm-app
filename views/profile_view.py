import streamlit as st
import pandas as pd
from sqlalchemy import text

def render(engine):
    st.subheader("🏢 Профиль компании")
    st.markdown("Данные из этого профиля будут автоматически подставляться в генерируемые договоры и документы.")

    # Получаем текущие данные из базы
    with engine.connect() as conn:
        profile_row = conn.execute(text("SELECT * FROM company_profile LIMIT 1")).fetchone()
        profile = profile_row._mapping if profile_row else {}

    col_info, col_logo = st.columns([2, 1])

    with col_info:
        with st.form("company_profile_form"):
            st.markdown("#### 📝 Реквизиты исполнителя")
            
            c_name = st.text_input("Наименование (ФИО ИП / Название ООО)", value=profile.get('company_name') or "")
            c_req = st.text_input("Документ-основание / Реквизиты (Паспорт, ОГРНИП, ИНН)", value=profile.get('requisites') or "", help="Например: паспорт серия 1808 №248570 или ОГРНИП 123456789")
            c_addr = st.text_input("Юридический адрес", value=profile.get('address') or "")
            
            st.markdown("#### 📞 Контакты")
            c_phone = st.text_input("Контактный телефон", value=profile.get('phone') or "")
            c_email = st.text_input("Email", value=profile.get('email') or "")

            if st.form_submit_button("💾 Сохранить реквизиты", type="primary"):
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE company_profile 
                        SET company_name = :n, requisites = :req, address = :addr, phone = :p, email = :e
                    """), {
                        "n": c_name, "req": c_req, "addr": c_addr, "p": c_phone, "e": c_email
                    })
                st.success("Данные компании успешно обновлены!")
                st.rerun()

    with col_logo:
        st.markdown("#### 🖼️ Логотип для документов")
        if profile.get('logo_data'):
            # 👇 Конвертируем memoryview в обычные байты 👇
            logo_bytes = bytes(profile.get('logo_data'))
            st.image(logo_bytes, use_container_width=True, caption="Текущий логотип")
            if st.button("🗑️ Удалить логотип"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE company_profile SET logo_data = NULL"))
                st.rerun()
        else:
            st.info("Логотип не загружен")

        st.divider()
        uploaded_logo = st.file_uploader("Загрузить новый логотип", type=["png", "jpg", "jpeg"])
        if uploaded_logo and st.button("💾 Сохранить логотип"):
            with engine.begin() as conn:
                conn.execute(text("UPDATE company_profile SET logo_data = :logo"), {"logo": uploaded_logo.getvalue()})
            st.success("Логотип загружен!")
            st.rerun()
