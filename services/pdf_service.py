def generate_contract_pdf(client_info, payments, engine):
      from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from io import BytesIO
    from datetime import datetime

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # --- СТИЛИ ---
    normal = ParagraphStyle(
    name='Normal',
    fontName='DejaVu',
    fontSize=10,
    leading=16,
    spaceAfter=10,   # ← отступ между абзацами
)
    bold = ParagraphStyle(name='Bold', fontName='DejaVu', fontSize=11, leading=15, spaceAfter=8)
    title = ParagraphStyle(name='Title', fontName='DejaVu', fontSize=15, alignment=1, spaceAfter=14)
    right = ParagraphStyle(name='Right', fontName='DejaVu', fontSize=10, alignment=2)
    small = ParagraphStyle(name='Small', fontName='DejaVu', fontSize=9, leading=12)

    elements = []
        # --- ПОДГРУЗКА ШАБЛОНА ---
    with engine.connect() as conn:
        tpl = conn.execute(
            text("SELECT content FROM contract_templates LIMIT 1")
        ).fetchone()

    if tpl:
        contract_text = render_template(tpl[0], client_info).replace("\n", "<br/>")

    # --- ДАННЫЕ ---
    today = datetime.now().strftime("%d.%m.%Y")
    contract_no = client_info[2] or f"AUTO-{datetime.now().strftime('%Y%m%d%H%M')}"

    # --- ШАПКА ---
    try:
        logo = Image("logo.png", width=90, height=45)
    except:
        logo = Paragraph("", normal)

    header_text = Paragraph(f"<b>ДОГОВОР № {contract_no}</b><br/>от {today}", right)

    header_table = Table([[logo, header_text]], colWidths=[150, 300])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 25))

    # --- ЗАГОЛОВОК ---
    elements.append(Paragraph("ДОГОВОР ОКАЗАНИЯ ЮРИДИЧЕСКИХ УСЛУГ", title))
    elements.append(Paragraph(f"г. Волгоград, {today}", normal))
    elements.append(Spacer(1, 15))

    # --- СТОРОНЫ ---
    intro = f"""
    <b>{client_info[0]}</b>, паспорт: {client_info[5] or '—'}, зарегистрированный по адресу:
    {client_info[8] or '—'}, именуемый «Заказчик», с одной стороны, и
    <b>{COMPANY_NAME}</b>, {COMPANY_PASSPORT}, адрес: {COMPANY_ADDRESS},
    именуемый «Исполнитель», с другой стороны, заключили настоящий договор:
    """
    elements.append(Paragraph(intro, normal))
    elements.append(Spacer(1, 12))
# --- ТЕКСТ ДОГОВОРА ИЗ CRM ---
    from bs4 import BeautifulSoup

    if tpl and tpl[0] and tpl[0].strip():
        contract_text = render_template(tpl[0], client_info)
    
        soup = BeautifulSoup(contract_text, "html.parser")
    
        for el in soup.find_all(["p", "li"]):
            elements.append(Paragraph(el.text, normal))
    else:
        elements.append(Paragraph("Шаблон договора не заполнен", normal))


    # --- 🔥 НОВАЯ СТРАНИЦА ---
    elements.append(PageBreak())

    # --- ПРИЛОЖЕНИЕ ---
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
