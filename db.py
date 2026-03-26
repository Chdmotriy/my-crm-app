import streamlit as st
import sqlalchemy

@st.cache_resource
def get_engine():
    return sqlalchemy.create_engine(st.secrets["DB_URL"])
