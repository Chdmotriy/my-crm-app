import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sqlalchemy
from sqlalchemy import text
import pytesseract
from PIL import Image
import io
import re
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from streamlit_quill import st_quill
import os
COMPANY_NAME = "Чадов Дмитрий Вячеславович"
COMPANY_PASSPORT = "паспорт серия 1808 №248570"
COMPANY_ADDRESS = "г. Волгоград, ул. Шурухина, д.86/155"
COMPANY_PHONE = "+79197920717"
# Для облака Streamlit путь указывать НЕ НУЖНО, 
# система найдет его сама после добавления packages.txt
def add_log(client_id, action, details=""):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO logs (client_id, action, details) 
            VALUES (:cid, :act, :det)
        """), {"cid": client_id, "act": action, "det": details})
def draw_page(canvas, doc):
    canvas.saveState()

    # --- ВЕРХНИЙ КОЛОНТИТУЛ ---
    canvas.setFont("DejaVu", 9)
    canvas.drawString(40, 800, COMPANY_NAME)

    # --- НИЖНИЙ КОЛОНТИТУЛ (номер страницы) ---
    page_num = canvas.getPageNumber()
    canvas.drawRightString(550, 20, f"Стр. {page_num}")

    # --- ВОДЯНОЙ ЗНАК ---
    canvas.setFont("DejaVu", 40)
    canvas.setFillGray(0.9)
    canvas.drawCentredString(300, 400, "ДОГОВОР")

    # --- РАМКА ---
    canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
    canvas.rect(30, 30, 535, 780)
    # --- ПОДПИСИ ВНИЗУ ---
    canvas.setFont("DejaVu", 10)
    
    canvas.drawString(40, 60, "Исполнитель: ____________________")
    canvas.drawRightString(550, 60, "Заказчик: ____________________")
    canvas.restoreState()
def generate_contract_pdf(client_info, payments):
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

def render_template(text, client_info):
    return text \
        .replace("{client_name}", client_info[0]) \
        .replace("{passport}", str(client_info[5] or "")) \
        .replace("{address}", str(client_info[8] or "")) \
        .replace("{amount}", f"{client_info[4]:,.0f}")
# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="CRM Interactive Pro", layout="wide")

# Безопасное получение пароля администратора
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except KeyError:
    st.error("⚠️ Ошибка: Пароль администратора (ADMIN_PASSWORD) не найден в секретах Streamlit.")
    st.stop()

with st.sidebar:
    st.title("🔐 Доступ")
    user_password = st.text_input("Введите пароль", type="password")
    
if user_password != ADMIN_PASSWORD:
    st.info("Введите пароль.")
    st.stop()

# --- 2. БАЗА ---
# Безопасное получение ссылки на базу данных
try:
    DB_URL = st.secrets["DB_URL"]
except KeyError:
    st.error("⚠️ Ошибка: Ссылка на базу данных (DB_URL) не найдена в секретах Streamlit.")
    st.stop()

engine = sqlalchemy.create_engine(DB_URL)
# --- ПОДКЛЮЧЕНИЕ ШРИФТА С КИРИЛЛИЦЕЙ ---
font_path = "DejaVuSans.ttf"
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))
else:
    st.warning("Шрифт DejaVuSans.ttf не найден!")
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS client_files (
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            filename TEXT,
            file_type TEXT,
            file_data BYTEA,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS contract_templates (
            id SERIAL PRIMARY KEY,
            content TEXT
        )
    """))
# --- 3. ГЛАВНЫЕ МЕТРИКИ (ИСПРАВЛЕНО) ---
st.title("🏦 Интерактивная CRM")

with engine.connect() as conn:
    # Доходы
    inc_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM schedule", conn)
    t_rev = float(inc_data['t'].fillna(0).iloc[0])
    p_rev = float(inc_data['p'].fillna(0).iloc[0])
    
    # Расходы
    exp_data = pd.read_sql("SELECT SUM(amount) as t, SUM(CASE WHEN status='ОПЛАЧЕНО' THEN amount ELSE 0 END) as p FROM expenses", conn)
    t_exp = float(exp_data['t'].fillna(0).iloc[0])
    p_exp = float(exp_data['p'].fillna(0).iloc[0])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Общий оборот", f"{t_rev:,.0f} ₽")
c2.metric("Всего затрат", f"{t_exp:,.0f} ₽", delta=f"-{t_exp:,.0f}", delta_color="inverse")
c3.metric("Прибыль (план)", f"{(t_rev - t_exp):,.0f} ₽")
c4.metric("Касса (факт)", f"{(p_rev - p_exp):,.0f} ₽")

st.divider()

# --- 4. НАВИГАЦИЯ (САЙДБАР) ---
# Список страниц для удобства
pages_list = [
    "📅 Календарь", "📈 Аналитика", "📋 Реестр", 
    "🔍 Карточка", "➕ Новая сделка", "📄 Шаблон договора"
]

# Инициализируем страницу в памяти, если её там нет
if 'page' not in st.session_state:
    st.session_state.page = pages_list[0]

with st.sidebar:
    st.divider()
    # Функция для смены страницы через код
    def set_page():
        st.session_state.page = st.session_state.nav_radio

    page = st.radio(
        "📌 Главное меню",
        pages_list,
        key="nav_radio",
        index=pages_list.index(st.session_state.page),
        on_change=set_page
    )
    # Синхронизируем локальную переменную с памятью
    page = st.session_state.page

# --- СТРАНИЦА 1: Календарь ---
if page == "📅 Календарь":
    with engine.connect() as conn:
        # Тянем только неоплаченные
        cal_inc = pd.read_sql("SELECT s.id, c.name, s.date, s.amount FROM schedule s JOIN clients c ON s.client_id = c.id WHERE s.status = 'Ожидается'", conn)
        cal_exp = pd.read_sql("SELECT id, description as name, date, amount FROM expenses WHERE status = 'Планируется'", conn)
    
    events = []
    for _, row in cal_inc.iterrows():
        events.append({"id": f"inc_{row['id']}", "title": f"➕ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#28a745", "allDay": True})
    for _, row in cal_exp.iterrows():
        events.append({"id": f"exp_{row['id']}", "title": f"➖ {row['name']}: {int(row['amount'])}", "start": str(row['date']), "color": "#dc3545", "allDay": True})

    cal_res = st_calendar(events=events, options={"locale": "ru", "initialView": "dayGridMonth", "selectable": True}, key="main_calendar")
    
    if cal_res and cal_res.get("eventClick"):
        clicked_event = cal_res["eventClick"]["event"]
        ev_id_str = clicked_event["id"]
        ev_type, ev_id = ev_id_str.split("_")
        ev_title = clicked_event["title"]
        
        st.write("---")
        st.subheader("⚙️ Быстрое действие")
        st.info(f"Выбрано: **{ev_title}**")
        
        # УЛУЧШЕНИЕ: Добавлена защита от случайного клика
        confirm = st.checkbox("Подтверждаю получение / списание средств")
        
        if st.button("✅ Перевести в ОПЛАЧЕНО", use_container_width=True, type="primary", disabled=not confirm):
            target_table = "schedule" if ev_type == "inc" else "expenses"
            
            with engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {target_table} SET status = 'ОПЛАЧЕНО' WHERE id = :id"),
                    {"id": int(ev_id)}
                )
            st.success(f"Статус обновлен! Платеж отмечен как оплаченный.")
            st.rerun()

# --- СТРАНИЦА 2: Аналитика ---
elif page == "📈 Аналитика":
    with engine.connect() as conn:
        years_df = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date) as year FROM schedule ORDER BY year DESC", conn)
    
    available_years = [int(y) for y in years_df['year'].tolist()] if not years_df.empty else [datetime.now().year]
    sel_year = st.selectbox("Выберите год для графиков", available_years)
    
    with engine.connect() as conn:
        rev_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as rev FROM schedule WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
        exp_m = pd.read_sql(text("SELECT TO_CHAR(date, 'Month') as month, TO_CHAR(date, 'MM') as m_num, SUM(amount) as exp FROM expenses WHERE EXTRACT(YEAR FROM date) = :y GROUP BY month, m_num"), conn, params={"y": sel_year})
    
    if not rev_m.empty:
        st.subheader(f"Статистика за {sel_year} год")
        chart_data = pd.merge(rev_m, exp_m, on=['month', 'm_num'], how='outer').fillna(0).sort_values('m_num')
        st.plotly_chart(px.bar(chart_data, x='month', y=['rev', 'exp'], barmode='group', 
                               labels={'value': 'Сумма (₽)', 'month': 'Месяц'},
                               color_discrete_map={'rev':'#28a745','exp':'#dc3545'}), use_container_width=True)

    st.divider()
    
    st.subheader("🔮 Прогноз на ближайшие 30 дней")
    with engine.connect() as conn:
        f_rev_res = conn.execute(text("SELECT SUM(amount) FROM schedule WHERE status = 'Ожидается' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'")).scalar()
        forecast_rev = float(f_rev_res) if f_rev_res else 0.0
        
        f_exp_res = conn.execute(text("SELECT SUM(amount) FROM expenses WHERE status = 'Планируется' AND date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'")).scalar()
        forecast_exp = float(f_exp_res) if f_exp_res else 0.0

    f_c1, f_c2, f_c3 = st.columns(3)
    f_c1.metric("Ожидаемый приход", f"{forecast_rev:,.0f} ₽")
    f_c2.metric("Плановые расходы", f"{forecast_exp:,.0f} ₽", delta=f"-{forecast_exp:,.0f}", delta_color="inverse")
    f_c3.metric("Прогноз остатка", f"{(forecast_rev - forecast_exp):,.0f} ₽")
    
    if forecast_rev < forecast_exp:
        st.error("⚠️ Внимание: запланированные расходы превышают ожидаемые приходы в ближайшие 30 дней!")

# --- СТРАНИЦА 3: Реестр ---
elif page == "📋 Реестр":
    with engine.connect() as conn:
        query = text("""
            SELECT c.id, c.name as "Клиент", c.contract_no as "Договор", c.total_amount as "Сумма договора", 
            COALESCE((SELECT SUM(amount) FROM schedule WHERE client_id = c.id AND status = 'ОПЛАЧЕНО'), 0) as "Получено",
            COALESCE((SELECT SUM(amount) FROM expenses WHERE client_id = c.id), 0) as "Затраты",
            EXISTS (SELECT 1 FROM schedule WHERE client_id = c.id AND date < CURRENT_DATE AND status = 'Ожидается') as "Есть_просрочка"
            FROM clients c ORDER BY "Есть_просрочка" DESC, c.name ASC
        """)
        df = pd.read_sql(query, conn)
    
    df["Остаток долга"] = df["Сумма договора"] - df["Получено"]
    df["Прибыль"] = df["Сумма договора"] - df["Затраты"]

    # --- ВЕРХНЯЯ ПАНЕЛЬ ФИЛЬТРОВ ---
    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        search = st.text_input("🔍 Поиск клиента или договора", "").lower()
    with col_s2:
        filter_mode = st.selectbox("Фильтр по статусу", ["Все", "Только должники", "Только оплаченные"])

    if search:
        df = df[df["Клиент"].str.lower().str.contains(search) | df["Договор"].str.lower().str.contains(search, na=False)]
    
    if filter_mode == "Только должники":
        df = df[df["Остаток долга"] > 0]
    elif filter_mode == "Только оплаченные":
        df = df[df["Остаток долга"] <= 0]

    # Метрики
    t_rec = df["Остаток долга"].sum()
    ov_c = int(df["Есть_просрочка"].sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("Общая дебиторка", f"{t_rec:,.0f} ₽")
    m2.metric("С просрочкой", f"{ov_c} чел.", delta=f"{ov_c}" if ov_c > 0 else None, delta_color="inverse")
    m3.metric("Всего сделок", len(df))

    st.divider()

    # --- ИНТЕРАКТИВНАЯ ТАБЛИЦА ---
    def style_rows(row):
        if row['Есть_просрочка']:
            return ['background-color: #ffebee; color: #b71c1c'] * len(row)
        if row['Остаток долга'] <= 0:
            return ['background-color: #e8f5e9; color: #1b5e20'] * len(row)
        return [''] * len(row)

    if not df.empty:
        st.write("💡 *Кликните на любую строку, чтобы мгновенно открыть карточку клиента*")
        
        # Используем selection_mode="single_row" для захвата клика
        event = st.dataframe(
            df.style.apply(style_rows, axis=1),
            use_container_width=True,
            height=500,
            selection_mode="single_row",
            on_select="rerun",  # Это заставляет приложение обновиться сразу при клике
            column_config={
                "id": None, "Есть_просрочка": None,
                "Сумма договора": st.column_config.NumberColumn(format="%d ₽"),
                "Получено": st.column_config.NumberColumn(format="%d ₽"),
                "Затраты": st.column_config.NumberColumn(format="%d ₽"),
                "Остаток долга": st.column_config.NumberColumn(format="%d ₽"),
                "Прибыль": st.column_config.NumberColumn(format="%d ₽")
            }
        )
        
        # ЛОГИКА ПЕРЕХОДА: Если пользователь кликнул на строку
        if event and event.selection.rows:
            selected_index = event.selection.rows[0]
            client_name = df.iloc[selected_index]["Клиент"]
            
            # 1. Запоминаем имя клиента для карточки
            st.session_state.det_sel = client_name
            # 2. Переключаем страницу в памяти
            st.session_state.page = "🔍 Карточка"
            # 3. Перезагружаем, чтобы сразу оказаться в карточке
            st.rerun()
    else:
        st.info("Данные отсутствуют.")
# --- СТРАНИЦА 4: Карточка (С ВНУТРЕННИМИ ВКЛАДКАМИ) ---
elif page == "🔍 Карточка":
    with engine.connect() as conn:
        cl_list = pd.read_sql("SELECT id, name FROM clients ORDER BY name", conn)
    
    if not cl_list.empty:
        sel_c = st.selectbox("👤 Выберите клиента", cl_list['name'], key="det_sel")
        c_id = int(cl_list[cl_list['name'] == sel_c]['id'].iloc[0])
        
        with engine.connect() as conn:
            c_info = conn.execute(text("""
                SELECT name, phone, contract_no, comment, total_amount, passport, snils, inn, address 
                FROM clients WHERE id = :id
            """), {"id":c_id}).fetchone()
        
        # Общие метрики сверху
        c1, c2, c3 = st.columns(3)
        c1.metric("📞 Телефон", c_info[1] if c_info[1] else "—")
        c2.metric("📄 Договор", f"№{c_info[2]}" if c_info[2] else "—")
        c3.metric("💰 Сумма", f"{c_info[4]:,.0f} ₽")

        st.divider()
        
        # УЛУЧШЕНИЕ: Внутренние вкладки для компактности!
        inner_tab1, inner_tab2, inner_tab3 = st.tabs(["📝 Данные клиента", "📎 Документы", "💳 Финансы и Договор"])

        # Внутренняя вкладка 1: Редактирование
        with inner_tab1:
            with st.form(f"f_edit_{c_id}"):
                un = st.text_input("ФИО", value=c_info[0] or "")
                up = st.text_input("Телефон", value=c_info[1] or "")
                uc = st.text_input("Номер договора", value=c_info[2] or "")

                st.markdown("### 🪪 Документы (текст)")
                upass = st.text_input("Паспорт", value=c_info[5] or "")
                usnils = st.text_input("СНИЛС", value=c_info[6] or "")
                uinn = st.text_input("ИНН", value=c_info[7] or "")
                uaddr = st.text_input("Адрес", value=c_info[8] or "")

                ucm = st.text_area("Комментарий", value=c_info[3] or "")

                if st.form_submit_button("Сохранить изменения", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text("""
                            UPDATE clients 
                            SET name=:n, phone=:p, contract_no=:c, comment=:cm,
                                passport=:pass, snils=:snils, inn=:inn, address=:addr
                            WHERE id=:id
                        """), {
                            "n":un, "p":up, "c":uc, "cm":ucm,
                            "pass":upass, "snils":usnils,
                            "inn":uinn, "addr":uaddr,
                            "id":c_id
                        })
                    st.success("Данные успешно сохранены")
                    st.rerun()
# --- НОВАЯ ФУНКЦИЯ: Удаление клиента ---
            st.divider()
            with st.expander("⚠️ Опасная зона: Удаление клиента"):
                st.warning("Внимание! Удаление клиента приведет к безвозвратному удалению всех его данных: графика платежей, загруженных документов и самой карточки.")
                
                # Галочка-предохранитель от случайного нажатия
                confirm_delete = st.checkbox("Я понимаю последствия и хочу удалить этого клиента", key=f"conf_del_{c_id}")
                
                if st.button("🗑️ Удалить клиента навсегда", type="primary", disabled=not confirm_delete, use_container_width=True):
                    with engine.begin() as conn:
                        # 1. Удаляем связанные файлы
                        conn.execute(text("DELETE FROM client_files WHERE client_id = :id"), {"id": c_id})
                        # 2. Удаляем график платежей
                        conn.execute(text("DELETE FROM schedule WHERE client_id = :id"), {"id": c_id})
                        # 3. Удаляем логи (если они есть)
                        conn.execute(text("DELETE FROM logs WHERE client_id = :id"), {"id": c_id})
                        # 4. Удаляем самого клиента
                        conn.execute(text("DELETE FROM clients WHERE id = :id"), {"id": c_id})
                    
                    st.success("Клиент и все его данные успешно удалены!")
                    st.rerun()
        # Внутренняя вкладка 2: Файлы и OCR
        with inner_tab2:
            st.subheader("📎 Загрузка документов")

            doc_type = st.selectbox(
                "Тип документа",
                ["passport", "snils", "inn"],
                format_func=lambda x: {"passport": "Паспорт", "snils": "СНИЛС", "inn": "ИНН"}[x]
            )

            uploaded_doc = st.file_uploader("Загрузить файл", type=["png", "jpg", "jpeg", "pdf"], key=f"upload_{c_id}")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("🤖 Распознать (OCR)", key=f"ocr_{c_id}"):
                    if uploaded_doc:
                        try:
                            image = Image.open(uploaded_doc)
                            text_ocr = pytesseract.image_to_string(image, lang='rus+eng')
                            
                            snils_match = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}', text_ocr)
                            inn_match = re.search(r'\b\d{10,12}\b', text_ocr)
                            pass_match = re.search(r'\b\d{2}\s?\d{2}\s?\d{6}\b', text_ocr)

                            with engine.begin() as conn:
                                if doc_type == "snils" and snils_match:
                                    conn.execute(text("UPDATE clients SET snils=:v WHERE id=:id"), {"v": snils_match.group(0), "id": c_id})
                                if doc_type == "inn" and inn_match:
                                    conn.execute(text("UPDATE clients SET inn=:v WHERE id=:id"), {"v": inn_match.group(0), "id": c_id})
                                if doc_type == "passport" and pass_match:
                                    conn.execute(text("UPDATE clients SET passport=:v WHERE id=:id"), {"v": pass_match.group(0), "id": c_id})
                            st.success("Распознано и сохранено в профиль!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка при чтении: {e}")

            with col2:
                if st.button("💾 Сохранить файл в базу", key=f"save_file_{c_id}"):
                    if uploaded_doc:
                        file_bytes = uploaded_doc.read()
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO client_files (client_id, filename, file_type, file_data) VALUES (:cid, :name, :type, :data)"),
                                         {"cid": c_id, "name": uploaded_doc.name, "type": doc_type, "data": file_bytes})
                        st.success("Файл прикреплен")
                        st.rerun()

            st.divider()
            st.markdown("### 📂 Загруженные файлы")
            with engine.connect() as conn:
                files_df = pd.read_sql(text("SELECT id, filename, file_type FROM client_files WHERE client_id = :id"), conn, params={"id": c_id})
            
            if not files_df.empty and 'file_type' in files_df.columns:
                for doc in ["passport", "snils", "inn"]:
                    doc_files = files_df[files_df['file_type'] == doc]
                    if not doc_files.empty:
                        st.markdown(f"**{doc.upper()}**")
                        for _, f in doc_files.iterrows():
                            fc1, fc2 = st.columns([4, 1])
                            fc1.write(f"📄 {f['filename']}")
                            if fc2.button("🗑️", key=f"del_{f['id']}"):
                                with engine.begin() as conn:
                                    conn.execute(text("DELETE FROM client_files WHERE id=:id"), {"id": int(f['id'])})
                                st.rerun()
            else:
                st.info("Нет прикрепленных файлов")

        # Внутренняя вкладка 3: Финансы и Договор
        with inner_tab3:
            st.info("💡 Здесь вы можете редактировать график платежей и расходы. Нажмите «Сохранить все изменения» внизу, чтобы применить правки.")

            # --- ИНИЦИАЛИЗАЦИЯ ДАННЫХ ---
            with engine.connect() as conn:
                curr_payments = pd.read_sql(text("SELECT id, date, amount, status FROM schedule WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})
                curr_expenses = pd.read_sql(text("SELECT id, description, date, amount, status FROM expenses WHERE client_id = :id ORDER BY date"), conn, params={"id": c_id})

            # Используем форму для единого сохранения
            with st.form(key=f"fin_form_{c_id}"):
                
                # --- СЕКЦИЯ 1: ДОХОДЫ ---
                st.subheader("💰 Доходы (График платежей)")
                updated_payments = []
                
                if not curr_payments.empty:
                    for i, row in curr_payments.iterrows():
                        p_col1, p_col2, p_col3, p_col4 = st.columns([2, 2, 2, 0.5])
                        with p_col1:
                            d_val = st.date_input(f"Дата {i+1}", row["date"], key=f"d_inc_{row['id']}")
                        with p_col2:
                            a_val = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"a_inc_{row['id']}")
                        with p_col3:
                            s_val = st.selectbox(f"Статус {i+1}", ["Ожидается", "ОПЛАЧЕНО"], 
                                                index=0 if row["status"] == "Ожидается" else 1, key=f"s_inc_{row['id']}")
                        with p_col4:
                            del_p = st.checkbox("🗑️", key=f"del_inc_{row['id']}", help="Удалить этот платеж")
                        
                        if not del_p:
                            updated_payments.append({"id": row["id"], "date": d_val, "amount": a_val, "status": s_val})
                else:
                    st.write("Платежей не найдено.")

                st.divider()

                # --- СЕКЦИЯ 2: РАСХОДЫ ---
                st.subheader("💸 Расходы по сделке")
                updated_expenses = []

                if not curr_expenses.empty:
                    for i, row in curr_expenses.iterrows():
                        e_col1, e_col2, e_col3, e_col4, e_col5 = st.columns([2, 1.5, 1.5, 1.5, 0.5])
                        with e_col1:
                            desc_v = st.text_input(f"Описание {i+1}", value=row["description"], key=f"e_desc_{row['id']}")
                        with e_col2:
                            ed_v = st.date_input(f"Дата {i+1}", row["date"], key=f"e_date_{row['id']}")
                        with e_col3:
                            ea_v = st.number_input(f"Сумма {i+1}", value=float(row["amount"]), key=f"e_am_{row['id']}")
                        with e_col4:
                            es_v = st.selectbox(f"Статус {i+1}", ["Планируется", "ОПЛАЧЕНО"], 
                                               index=0 if row["status"] == "Планируется" else 1, key=f"e_st_{row['id']}")
                        with e_col5:
                            del_e = st.checkbox("🗑️", key=f"del_exp_{row['id']}", help="Удалить этот расход")
                        
                        if not del_e:
                            updated_expenses.append({"id": row["id"], "desc": desc_v, "date": ed_v, "amount": ea_v, "status": es_v})
                
                # Добавление новой строки расхода (пустая заготовка)
                st.markdown("**➕ Добавить новый расход**")
                new_exp_col1, new_exp_col2, new_exp_col3 = st.columns([3, 2, 2])
                with new_exp_col1:
                    new_e_desc = st.text_input("Описание нового расхода", key=f"new_e_desc_{c_id}")
                with new_exp_col2:
                    new_e_am = st.number_input("Сумма", value=0.0, key=f"new_e_am_{c_id}")
                with new_exp_col3:
                    new_e_date = st.date_input("Дата", value=datetime.now(), key=f"new_e_date_{c_id}")

                st.divider()

                # --- КНОПКА СОХРАНЕНИЯ ВСЕГО ---
                submit_all = st.form_submit_button("💾 СОХРАНИТЬ ВСЕ ИЗМЕНЕНИЯ", use_container_width=True, type="primary")

                if submit_all:
                    with engine.begin() as conn:
                        # 1. Обновляем/удаляем Доходы
                        existing_p_ids = [p["id"] for p in updated_payments]
                        conn.execute(text("DELETE FROM schedule WHERE client_id = :cid AND id NOT IN :ids"), 
                                     {"cid": c_id, "ids": tuple(existing_p_ids) if existing_p_ids else (0,)})
                        for p in updated_payments:
                            conn.execute(text("UPDATE schedule SET date=:d, amount=:a, status=:s WHERE id=:id"), 
                                         {"d": p["date"], "a": p["amount"], "s": p["status"], "id": p["id"]})

                        # 2. Обновляем/удаляем Расходы
                        existing_e_ids = [e["id"] for e in updated_expenses]
                        conn.execute(text("DELETE FROM expenses WHERE client_id = :cid AND id NOT IN :ids"), 
                                     {"cid": c_id, "ids": tuple(existing_e_ids) if existing_e_ids else (0,)})
                        for e in updated_expenses:
                            conn.execute(text("UPDATE expenses SET description=:desc, date=:d, amount=:a, status=:s WHERE id=:id"), 
                                         {"desc": e["desc"], "d": e["date"], "a": e["amount"], "s": e["status"], "id": e["id"]})
                        
                        # 3. Добавляем новый расход, если заполнено описание
                        if new_e_desc:
                            conn.execute(text("INSERT INTO expenses (client_id, description, amount, date, status) VALUES (:cid, :desc, :am, :dt, 'Планируется')"),
                                         {"cid": c_id, "desc": new_e_desc, "am": new_e_am, "dt": new_e_date})

                    st.success("Все финансовые данные обновлены!")
                    st.rerun()

            # --- СЕКЦИЯ 3: ГЕНЕРАЦИЯ ДОГОВОРА (Вне формы) ---
            st.divider()
            st.subheader("📄 Договор")
            if st.button("Сгенерировать PDF", key=f"gen_pdf_final_{c_id}"):
                pdf_file = generate_contract_pdf(c_info, curr_payments)
                st.download_button("📥 Скачать PDF", data=pdf_file, file_name=f"contract_{c_info[0]}.pdf", mime="application/pdf")

    else:
        st.info("База клиентов пуста.")

# --- СТРАНИЦА 5: Новая сделка ---
elif page == "➕ Новая сделка":
    st.subheader("🤖 Автоматическое распознавание документов")
    
    if 'ocr_inn' not in st.session_state: st.session_state.ocr_inn = ""
    if 'ocr_snils' not in st.session_state: st.session_state.ocr_snils = ""
    if 'ocr_pass' not in st.session_state: st.session_state.ocr_pass = ""

    uploaded_file = st.file_uploader("Загрузить скан или фото (Паспорт, ИНН, СНИЛС)", type=['png', 'jpg', 'jpeg'])
    if uploaded_file is not None:
        if st.button("✨ Распознать текст", type="primary"):
            with st.spinner('Читаем документ...'):
                image = Image.open(uploaded_file)
                text = pytesseract.image_to_string(image, lang='rus+eng')
                
                snils_match = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}', text)
                if snils_match: st.session_state.ocr_snils = snils_match.group(0)
                
                inn_match = re.search(r'\b\d{10,12}\b', text)
                if inn_match: st.session_state.ocr_inn = inn_match.group(0)
                
                pass_match = re.search(r'\b\d{2}\s?\d{2}\s?\d{6}\b', text)
                if pass_match: st.session_state.ocr_pass = pass_match.group(0)
                
            st.success("Документ обработан! Проверьте поля.")
            
    # УЛУЧШЕНИЕ: Добавлен clear_on_submit=True для автоматической очистки полей после добавления
    with st.form("new_deal", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            n = st.text_input("ФИО клиента")
            p = st.text_input("Телефон")

        with col2:
            t = st.number_input("Сумма договора", value=100000.0)
            c_no = st.text_input("Номер договора")

        st.markdown("##### 🪪 Документы")
        doc1, doc2 = st.columns(2)

        with doc1:
            passp = st.text_input("Паспортные данные", value=st.session_state.ocr_pass)
            snils_val = st.text_input("СНИЛС", value=st.session_state.ocr_snils)

        with doc2:
            inn_val = st.text_input("ИНН", value=st.session_state.ocr_inn)
            addr = st.text_input("Адрес регистрации")

        st.markdown("##### ⚙️ Условия")
        tp = st.radio("Тип оплаты", ["Рассрочка", "Сразу"], horizontal=True)
        m = st.number_input("Кол-во платежей (месяцев)", min_value=1, value=1)
        d = st.date_input("Дата первого платежа", datetime.now())
        comm = st.text_area("Комментарий к сделке")

        if st.form_submit_button("Создать сделку", type="primary"):
            if n:
                with engine.begin() as conn:
                    cid = conn.execute(text("""
                        INSERT INTO clients (name, total_amount, months, start_date, phone, contract_no, comment, passport, snils, inn, address) 
                        VALUES (:n, :t, :m, :d, :p, :c_no, :comm, :passp, :snils, :inn, :addr) RETURNING id
                    """), {
                        "n": n, "t": t, "m": int(m), "d": d,
                        "p": p, "c_no": c_no, "comm": comm,
                        "passp": passp, "snils": snils_val,
                        "inn": inn_val, "addr": addr
                    }).scalar()

                    steps = 1 if tp == "Сразу" else int(m)
                    amount_per_step = round(t / steps, 2)
                    from dateutil.relativedelta import relativedelta

                    for i in range(steps):
                        p_date = d + relativedelta(months=i)
                        conn.execute(text("INSERT INTO schedule (client_id, date, amount, status) VALUES (:cid, :dt, :am, 'Ожидается')"), 
                                     {"cid": cid, "dt": p_date, "am": amount_per_step})

                # Сбрасываем кэш OCR
                st.session_state.ocr_inn = ""
                st.session_state.ocr_snils = ""
                st.session_state.ocr_pass = ""

                st.success(f"Клиент {n} успешно добавлен! Форма очищена.")
                st.rerun()

# --- СТРАНИЦА 6: Шаблон договора ---
elif page == "📄 Шаблон договора":
    st.subheader("✍️ Редактор договора")

    with engine.connect() as conn:
        template = conn.execute(text("SELECT content FROM contract_templates LIMIT 1")).fetchone()

    default_text = template[0] if template else "Введите текст договора..."

    new_text = st_quill(value=default_text, html=True)

    if st.button("💾 Сохранить шаблон", type="primary"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM contract_templates"))
            conn.execute(text("INSERT INTO contract_templates (content) VALUES (:c)"), {"c": new_text})
        st.success("Шаблон сохранён")
