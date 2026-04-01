import io
import os
import pandas as pd
from sqlalchemy import text
from docxtpl import DocxTemplate

def get_client_context(engine, client_id):
    """Собирает все данные клиента из разных таблиц в один словарь для шаблона Word."""
    with engine.connect() as conn:
        client_row = conn.execute(text("SELECT * FROM clients WHERE id = :id"), {"id": client_id}).fetchone()
        client = client_row._mapping if client_row else {}
        
        creditors_df = pd.read_sql(text("SELECT * FROM creditors WHERE client_id = :id"), conn, params={"id": client_id})
        props_df = pd.read_sql(text("SELECT * FROM properties WHERE client_id = :id"), conn, params={"id": client_id})
        
        total_debt = creditors_df['debt_amount'].sum() if not creditors_df.empty else 0

        # Собираем умный полный адрес (игнорируя пустые поля)
        address_components = [
            client.get('addr_zip'),
            client.get('addr_region'),
            client.get('addr_district'),
            client.get('addr_city'),
            client.get('addr_settlement'),
            client.get('addr_street'),
            client.get('addr_house'),
            client.get('addr_corpus'),
            client.get('addr_flat')
        ]
        
        # Склеиваем только те элементы, которые не пустые, добавляя запятую и пробел
        valid_parts = [str(part).strip() for part in address_components if part and str(part).strip()]
        full_address_string = ", ".join(valid_parts)

        # Возвращаем словарь со всеми тегами для Word-шаблонов
        return {
            "client_name": client.get('name') or "",
            "phone": client.get('phone') or "",
            
            # Разделенное ФИО
            "last_name": client.get('last_name') or "",
            "first_name": client.get('first_name') or "",
            "patronymic": client.get('patronymic') or "",
            
            # Разделенный паспорт
            "passport_series": client.get('passport_series') or client.get('passport') or "",
            "passport_issued_by": client.get('passport_issued_by') or "",
            
            "snils": client.get('snils') or "",
            "inn": client.get('inn') or "",
            
            # Данные для банкротства
            "birth_date": client.get('birth_date').strftime('%d.%m.%Y') if client.get('birth_date') else "",
            "birth_place": client.get('birth_place') or "",
            "court_name": client.get('court_name') or "",
            "sro_name": client.get('sro_name') or "",
            
            # Индивидуальные теги адреса (если вдруг понадобятся отдельно)
            "addr_zip": client.get('addr_zip') or "",
            "addr_region": client.get('addr_region') or "",
            "addr_district": client.get('addr_district') or "",
            "addr_city": client.get('addr_city') or "",
            "addr_settlement": client.get('addr_settlement') or "",
            "addr_street": client.get('addr_street') or "",
            "addr_house": client.get('addr_house') or "",
            "addr_corpus": client.get('addr_corpus') or "",
            "addr_flat": client.get('addr_flat') or "",
            
            # ⭐️ Новый супер-тег: склеенный полный адрес
            "full_address": full_address_string,
            
            # Списки и суммы
            "total_debt": f"{total_debt:,.2f}".replace(',', ' '),
            "creditors": creditors_df.to_dict(orient='records'),
            "properties": props_df.to_dict(orient='records')
        }

def generate_word_document(template_path, context):
    """Берет шаблон .docx, подставляет контекст и возвращает готовый файл в байтах."""
    if not os.path.exists(template_path):
        return None
        
    doc = DocxTemplate(template_path)
    doc.render(context)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
