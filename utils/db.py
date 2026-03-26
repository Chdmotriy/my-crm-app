import streamlit as st
import sqlalchemy
from sqlalchemy import text

@st.cache_resource
def init_db_connection(db_url):
    """Инициализирует и кэширует подключение к БД."""
    return sqlalchemy.create_engine(db_url)

def setup_tables(engine):
    """Создает необходимые таблицы, если их нет."""
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

def add_log(engine, client_id, action, details=""):
    """Логирует действия пользователя."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO logs (client_id, action, details) 
            VALUES (:cid, :act, :det)
        """), {"cid": client_id, "act": action, "det": details})
