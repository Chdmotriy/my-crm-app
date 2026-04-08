import streamlit as st
from sqlalchemy import create_engine, text

@st.cache_resource
def init_db_connection(db_url):
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    connect_args = {}
    if "postgresql" in db_url:
        connect_args = {"sslmode": "require", "keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 5}
    return create_engine(db_url, pool_pre_ping=True, pool_recycle=300, pool_timeout=30, max_overflow=5, connect_args=connect_args)

def setup_tables(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS clients (id SERIAL PRIMARY KEY, name TEXT, phone TEXT, contract_no TEXT, comment TEXT, total_amount NUMERIC, months INTEGER, start_date DATE, passport TEXT, snils TEXT, inn TEXT, address TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schedule (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, date DATE, amount NUMERIC, status TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, description TEXT, date DATE, amount NUMERIC, status TEXT)"))
        conn.execute(text("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'Прочее'"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS client_files (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, filename TEXT, file_type TEXT, file_data BYTEA)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS contract_templates (id SERIAL PRIMARY KEY, content TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS logs (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, action TEXT, details TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS properties (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, property_type TEXT, description TEXT, estimated_value NUMERIC, is_pledged BOOLEAN DEFAULT FALSE)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS authorized_bodies (id SERIAL PRIMARY KEY, name TEXT, address TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS creditor_catalog (id SERIAL PRIMARY KEY, name TEXT, address TEXT)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS creditors (id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, creditor_name TEXT, contract_info TEXT, debt_amount NUMERIC)"))
        conn.execute(text("ALTER TABLE creditors ADD COLUMN IF NOT EXISTS creditor_address TEXT"))
        conn.execute(text("ALTER TABLE creditors ADD COLUMN IF NOT EXISTS principal_debt NUMERIC DEFAULT 0"))
        conn.execute(text("ALTER TABLE creditors ADD COLUMN IF NOT EXISTS penalty_debt NUMERIC DEFAULT 0"))
        conn.execute(text("ALTER TABLE creditors ADD COLUMN IF NOT EXISTS contracts_info TEXT"))

        # Обновляем клиента - добавил previous_names
        new_columns = {
            "last_name": "TEXT", "first_name": "TEXT", "patronymic": "TEXT",
            "previous_names": "TEXT", # 👈 Новое поле
            "passport_series": "TEXT", "passport_issued_by": "TEXT",
            "birth_date": "DATE", "birth_place": "TEXT",
            "addr_zip": "TEXT", "addr_region": "TEXT", "addr_district": "TEXT", 
            "addr_city": "TEXT", "addr_settlement": "TEXT", "addr_street": "TEXT", 
            "addr_house": "TEXT", "addr_corpus": "TEXT", "addr_flat": "TEXT",
            "court_name": "TEXT", "marital_status": "TEXT", 
            "dependents": "INTEGER DEFAULT 0", "sro_name": "TEXT",
            "spouse_name": "TEXT", "spouse_address": "TEXT",
            "auth_body_id": "INTEGER"
        }
        
        for col_name, col_type in new_columns.items():
            conn.execute(text(f"ALTER TABLE clients ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
