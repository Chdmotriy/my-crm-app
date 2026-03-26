import os
from io import BytesIO
from datetime import datetime
from bs4 import BeautifulSoup
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import streamlit as st

# Константы компании можно позже вынести в config.py
COMPANY_NAME = "Чадов Дмитрий Вячеславович"
COMPANY_PASSPORT = "паспорт серия 1808 №248570"
COMPANY_ADDRESS = "г. Волгоград, ул. Шурухина, д.86/155"

def render_template(text, client_info):
    """Подставляет данные клиента в текст договора."""
    if not text:
        return ""
    return text \
        .replace("{client_name}", client_info[0]) \
        .replace("{passport}", str(client_info[5] or "")) \
        .replace("{address}", str(client_info[8] or "")) \
        .replace("{amount}", f"{client_info[4]:,.0f}")

def draw_page(canvas, doc):
    """Отрисовка колонтитулов и водяных знаков на каждой странице."""
    canvas.saveState()
    canvas.setFont("DejaVu", 9)
    canvas.drawString(40, 800, COMPANY_NAME)
    
    page_num = canvas.getPageNumber()
    canvas.drawRightString(550, 20, f"Стр. {page_num}")
    
    canvas.setFont("DejaVu", 40)
    canvas.setFillGray(0.9)
    canvas.drawCentredString(300, 400, "ДОГОВОР")
    
    canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
    canvas.rect(30, 30, 535, 780)
    
    canvas.setFont("DejaVu", 10)
    canvas.drawString(40, 60, "Исполнитель: ____________________")
    canvas.drawRightString(550, 60, "Заказчик: ____________________")
    canvas.restoreState()

def generate_contract_pdf(client_info, payments, contract_text):
    """Генерирует PDF-файл договора на основе переданного текста."""
    font_path = "DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVu', font_path))
    else:
        st.warning("Шрифт DejaVuSans.ttf не найден! В PDF могут быть проблемы с кириллицей.")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=50, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(name='Normal', fontName='DejaVu', fontSize=10, leading=16, spaceAfter=10)
    bold = ParagraphStyle(name='Bold', fontName='DejaVu', fontSize=11, leading=15, spaceAfter=8)
    title = ParagraphStyle(name='Title', fontName='DejaVu', fontSize=15, alignment=1, spaceAfter=14)
    right = ParagraphStyle(name='Right', fontName='DejaVu', fontSize=10, alignment=2)

    elements = []
    today = datetime.now().strftime("%d.%m.%Y")
    contract_no = client_info[2] or f"AUTO-{datetime.now().strftime('%Y%m%d%H%M')}"

    # Шапка
    header_text = Paragraph(f"<b>ДОГОВОР № {contract_no}</b><br/>от {today}", right)
    header_table = Table([["", header_text]], colWidths=[150, 300]) # Логотип пока убрал для надежности, можно вернуть Image()
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("ДОГОВОР ОКАЗАНИЯ ЮРИДИЧЕСКИХ УСЛУГ", title))
    elements.append(Paragraph(f"г. Волгоград, {today}", normal))
    elements.append(Spacer(1, 15))

    # Вводная часть
    intro = f"""
    <b>{client_info[0]}</b>, паспорт: {client_info[5] or '—'}, зарегистрированный по адресу:
    {client_info[8] or '—'}, именуемый «Заказчик», с одной стороны, и
    <b>{COMPANY_NAME}</b>, {COMPANY_PASSPORT}, адрес: {COMPANY_ADDRESS},
    именуемый «Исполнитель», с другой стороны, заключили настоящий договор:
    """
    elements.append(Paragraph(intro, normal))
    elements.append(Spacer(1, 12))

    # Парсинг HTML из базы
    if contract_text and contract_text.strip():
        rendered_text = render_template(contract_text, client_info)
        soup = BeautifulSoup(rendered_text, "html.parser")
        for el in soup.find_all(["p", "li"]):
            elements.append(Paragraph(el.text, normal))
    else:
        elements.append(Paragraph("Шаблон договора не заполнен", normal))

    elements.append(PageBreak())

    # Приложение: График платежей
    elements.append(Paragraph("Приложение №1", title))
    elements.append(Paragraph("График платежей", bold))
    elements.append(Spacer(1, 10))

    data = [["№", "Дата платежа", "Сумма"]]
    for i, (_, r) in enumerate(payments.iterrows(), start=1):
        data.append([i, str(r['date']), f"{r['amount']:,.0f} ₽"])

    table = Table(data, colWidths=[60, 180, 180])
    table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'DejaVu'),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2c2c2c")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey])
    ]))
    
    elements.append(table)
    doc.build(elements, onFirstPage=draw_page, onLaterPages=draw_page)
    
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
