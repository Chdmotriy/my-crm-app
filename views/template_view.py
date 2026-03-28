import streamlit as st
from sqlalchemy import text
from streamlit_quill import st_quill

def render(engine):
    st.subheader("✍️ Редактор шаблона договора")
    
    # Удобная подсказка для пользователя
    with st.expander("ℹ️ Шпаргалка: Автоматические переменные"):
        st.markdown("""
        Вставьте эти теги прямо в текст договора. При генерации PDF для конкретного клиента, система автоматически заменит их на реальные данные:
        * `{client_name}` — ФИО клиента
        * `{passport}` — Серия, номер и кем выдан паспорт
        * `{address}` — Адрес регистрации
        * `{amount}` — Общая сумма договора (в рублях)
        """)

    # Загружаем текущий шаблон из базы данных
    with engine.connect() as conn:
        template = conn.execute(text("SELECT content FROM contract_templates LIMIT 1")).fetchone()

    default_text = template[0] if template else "<p>Введите текст договора...</p>"

    # Отрисовываем визуальный HTML-редактор
    st.markdown("**Текст договора:**")
    new_text = st_quill(value=default_text, html=True, key="quill_contract_editor")

    # Логика сохранения
    if st.button("💾 Сохранить шаблон", type="primary", use_container_width=True):
        if new_text:
            with engine.begin() as conn:
                # Проверяем, есть ли уже сохраненный шаблон в базе
                count = conn.execute(text("SELECT count(*) FROM contract_templates")).scalar()
                
                if count > 0:
                    # Если есть - обновляем его
                    conn.execute(text("UPDATE contract_templates SET content = :val"), {"val": new_text})
                else:
                    # Если база пустая - создаем первую запись
                    conn.execute(text("INSERT INTO contract_templates (content) VALUES (:val)"), {"val": new_text})
            
            st.success("✅ Шаблон договора успешно сохранен! Теперь он будет использоваться при генерации PDF.")
            st.rerun()
        else:
            st.warning("⚠️ Текст шаблона не может быть пустым.")
