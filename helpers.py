import pandas as pd
from sqlalchemy import text

def query_df(engine, sql, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)
