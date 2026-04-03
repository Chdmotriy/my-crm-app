import io
import os
import pandas as pd
from sqlalchemy import text
from docxtpl import DocxTemplate, RichText
from datetime import datetime  # 👈 Добавили для работы с текущей датой

def get_client_context(engine, client_id):
    """Собирает все данные клиента из разных таблиц в один словарь для шаблона Word."""
    with engine.connect() as conn:
        client_row = conn.execute(text("SELECT * FROM clients WHERE id = :id"), {"id": client_id}).fetchone()
        client = client_row._mapping if client_row else {}
        
        creditors_df = pd.read_sql(text("SELECT * FROM creditors WHERE client_id = :id"), conn, params={"id": client_id})
        props_df = pd.read_sql(text("SELECT * FROM properties WHERE client_id = :id"), conn, params={"id": client_id})
        
        auth_body_name, auth_body_address = "", ""
        if client.get('auth_body_id'):
            ab_row = conn.execute(text("SELECT name, address FROM authorized_bodies WHERE id = :id"), {"id": client.get('auth_body_id')}).fetchone()
            if ab_row:
                auth_body_name, auth_body_address = ab_row[0], ab_row[1]

        # 1. Формируем умный полный адрес
        address_components = [
            client.get('addr_zip'), client.get('addr_region'), client.get('addr_district'),
            client.get('addr_city'), client.get('addr_settlement'), client.get('addr_street'),
            client.get('addr_house'), client.get('addr_corpus'), client.get('addr_flat')
        ]
        full_address_string = ", ".join([str(p).strip() for p in address_components if p and str(p).strip()])

        # 2. Формируем списки кредиторов для Word
        creditors_header_lines = []
        creditors_body_lines = []
        total_debt = 0

        for idx, row in enumerate(creditors_df.to_dict('records'), 1):
            c_name = row.get('creditor_name') or ""
            c_addr = row.get('creditor_address') or ""
            c_total = row.get('debt_amount') or 0
            c_contracts = row.get('contracts_info') or ""
            
            total_debt += c_total
            c_total_str = f"{c_total:,.2f}".replace(',', ' ')
            
            # 👇 ИСПРАВЛЕНО: Наименование, затем перенос строки и Адрес
            if c_addr:
                header_str = f"Кредитор {idx}: {c_name}\nАдрес: {c_addr}"
            else:
                header_str = f"Кредитор {idx}: {c_name}"
            creditors_header_lines.append(header_str)
            
            # Строка для тела
            contracts_formatted = ",\n".join([line.strip() for line in c_contracts.split('\n') if line.strip()])
            body_str = f"Требований Кредитора {idx} ({c_name}) в размере {c_total_str} рублей, которые в свою очередь вытекают из следующих заключенных договоров:\n{contracts_formatted}"
            creditors_body_lines.append(body_str)

        # Склеиваем всё. Между кредиторами в шапке делаем двойной отступ (\n\n) для красоты
        final_creditors_header = "\n\n".join(creditors_header_lines)
        final_creditors_body = "\n\n".join(creditors_body_lines)

        return {
            "client_name": client.get('name') or "",
            "last_name": client.get('last_name') or "",
            "first_name": client.get('first_name') or "",
            "patronymic": client.get('patronymic') or "",
            "phone": client.get('phone') or "",
            
            "passport_series": client.get('passport_series') or client.get('passport') or "",
            "passport_issued_by": client.get('passport_issued_by') or "",
            "snils": client.get('snils') or "",
            "inn": client.get('inn') or "",
            
            "birth_date": client.get('birth_date').strftime('%d.%m.%Y') if client.get('birth_date') else "",
            "birth_place": client.get('birth_place') or "",
            "court_name": client.get('court_name') or "",
            "sro_name": client.get('sro_name') or "",
            "marital_status": client.get('marital_status') or "",
            "dependents": client.get('dependents') or 0,
            
            "spouse_name": client.get('spouse_name') or "",
            "spouse_address": client.get('spouse_address') or "",
            
            "auth_body_name": auth_body_name,
            "auth_body_address": auth_body_address,
            
            "full_address": full_address_string,
            
            "total_debt": f"{total_debt:,.2f}".replace(',', ' '),
            
            # ⭐️ НОВЫЙ ТЕГ ДАТЫ (Формат: ДД.ММ.ГГГГ)
            "current_date": datetime.now().strftime('%d.%m.%Y'),
            
            "creditors_header_text": RichText(final_creditors_header) if final_creditors_header else "",
            "creditors_body_text": RichText(final_creditors_body) if final_creditors_body else "",
            
            "properties": props_df.to_dict('records')
        }

def generate_word_document(template_path, context):
    if not os.path.exists(template_path):
        return None
    doc = DocxTemplate(template_path)
    doc.render(context)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
