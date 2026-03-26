import re
import io
import pytesseract
from PIL import Image
import streamlit as st

@st.cache_data(show_spinner=False)
def process_document_image(image_bytes):
    """
    Принимает байты изображения, распознает текст и ищет паттерны документов.
    Результат кэшируется: одна и та же картинка не будет читаться дважды.
    """
    try:
        # Открываем изображение из байтов
        image = Image.open(io.BytesIO(image_bytes))
        
        # Распознаем текст
        text_ocr = pytesseract.image_to_string(image, lang='rus+eng')
        
        # Ищем совпадения по регулярным выражениям
        snils_match = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}', text_ocr)
        inn_match = re.search(r'\b\d{10,12}\b', text_ocr)
        pass_match = re.search(r'\b\d{2}\s?\d{2}\s?\d{6}\b', text_ocr)
        
        return {
            "success": True,
            "raw_text": text_ocr,
            "snils": snils_match.group(0) if snils_match else None,
            "inn": inn_match.group(0) if inn_match else None,
            "passport": pass_match.group(0) if pass_match else None
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
