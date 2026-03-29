import streamlit as st
from sqlalchemy import create_engine, text

@st.cache_resource
@st.cache_resource
def init_db_connection(db_url):
    """
    Создает и кэширует подключение к базе данных с защитой от обрывов связи.
    """
    connect_args = {}
    
    # Если это PostgreSQL, принудительно включаем SSL
    if db_url.startswith("postgres"):
        connect_args = {"sslmode": "require"}
        
    return create_engine(
        db_url,
        pool_pre_ping=True,   # Пингует базу перед каждым запросом (защита от "уснувших" соединений)
        pool_recycle=300,     # Переподключается каждые 5 минут, чтобы облако не сбросило связь
        connect_args=connect_args
    )

def setup_tables(engine):
    """
    Проверяет наличие нужных таблиц в базе и создает их, если они отсутствуют.
    """
    with engine.begin() as conn:
        # Таблица клиентов
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                name TEXT,
                phone TEXT,
                contract_no TEXT,
                comment TEXT,
                total_amount NUMERIC,
                months INTEGER,
                start_date DATE,
                passport TEXT,
                snils TEXT,
                inn TEXT,
                address TEXT
            )
        """))
        
        # График платежей (доходы)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schedule (
                id SERIAL PRIMARY KEY,
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                date DATE,
                amount NUMERIC,
                status TEXT
            )
        """))
        
        # Расходы
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                description TEXT,
                date DATE,
                amount NUMERIC,
                status TEXT
            )
        """))
        
        # Файлы
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS client_files (
                id SERIAL PRIMARY KEY,
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                filename TEXT,
                file_type TEXT,
                file_data BYTEA
            )
        """))
        
        # Шаблоны договоров
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contract_templates (
                id SERIAL PRIMARY KEY,
                content TEXT
            )
        """))
        
        # Логи
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
