import streamlit as st
from sqlalchemy import create_engine, text

@st.cache_resource
def init_db_connection(db_url):
    """
    Создает и кэширует подключение к БД с максимальной защитой от обрывов связи в облаке.
    """
    # Важное исправление: современные версии SQLAlchemy требуют 'postgresql://', а не 'postgres://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    connect_args = {}
    
    # Настройки для удержания SSL-соединения (специально для psycopg2)
    if "postgresql" in db_url:
        connect_args = {
            "sslmode": "require",
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5
        }

    return create_engine(
        db_url,
        pool_pre_ping=True,   # Проверка соединения перед каждым запросом
        pool_recycle=300,     # Переподключение каждые 5 минут
        pool_timeout=30,      # Таймаут ожидания пула
        max_overflow=5,
        connect_args=connect_args
    )

def setup_tables(engine):
    """
    Создает все необходимые таблицы при первом запуске.
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
        
        # График платежей
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
