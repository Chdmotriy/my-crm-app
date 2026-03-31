import io
import os
import pandas as pd
from sqlalchemy import text
from docxtpl import DocxTemplate

def get_client_context(engine, client_id):
    """Собирает все данные клиента из разных таблиц в один словарь для шаблона."""
    with engine.connect() as conn:
        # Данные клиента
        client = conn.execute(text("SELECT * FROM clients WHERE id = :id"), {"id": client_id}).fetchone()
        
        # Список кредиторов
        creditors_df = pd.read_sql(text("SELECT * FROM creditors WHERE client_id = :id"), conn, params={"id": client_id})
        creditors = creditors_df.to_dict(orient='records')
        
        # Список имущества
        props_df = pd.read_sql(text("SELECT * FROM properties WHERE client_id = :id"), conn, params={"id": client_id})
        properties = props_df.to_dict(orient='records')
        
        # Считаем общую сумму долга автоматически
        total_debt = creditors_df['debt_amount'].sum() if not creditors_df.empty else 0

        # Упаковываем всё в словарь (эти ключи будем писать в Word внутри {{ }})
        return {
            "client_name": client.name if client and client.name else "",
            "phone": client.phone if client and client.phone else "",
            "passport": client.passport if client and client.passport else "",
            "snils": client.snils if client and client.snils else "",
            "inn": client.inn if client and client.inn else "",
            "address": client.address if client and client.address else "",
            "total_debt": f"{total_debt:,.2f}".replace(',', ' '), # Форматируем красиво: 1 500 000.00
            "creditors": creditors,
            "properties": properties
        }

def generate_word_document(template_path, context):
    """Берет шаблон .docx, подставляет контекст и возвращает готовый файл в байтах."""
    if not os.path.exists(template_path):
        return None # Если файла шаблона нет, возвращаем пустоту
        
    doc = DocxTemplate(template_path)
    doc.render(context)
    
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
