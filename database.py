import streamlit as st
import psycopg2

@st.cache_resource
def get_conn():
    return psycopg2.connect(**st.secrets["db"])
