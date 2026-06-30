import streamlit as st
import pandas as pd
import os
from datetime import datetime
import psycopg2

@st.cache_resource
def get_conn():
    return psycopg2.connect(**st.secrets["db"])

def check_password(usuario, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT nombre, rol FROM usuarios WHERE usuario = %s AND password_hash = crypt(%s, password_hash)", (usuario, password))
    result = cur.fetchone()
    cur.close()
    if result:
        return result[0], result[1]
    return None, None

# ==========================================
# CONFIGURACIÓN DE LA INTERFAZ
# ==========================================
st.set_page_config(
    page_title="D&A Candelero Agro",
    layout="wide",
    page_icon="🚜"
)

st.markdown("""
    <style>
 .header-container {
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 25px;
        border: 3px solid #1E4620;
    }
 .main-title { font-size: 30pt; font-weight: 900; color: #1E4620; }
 .subtitle { font-size: 14pt; color: #8B733A; font-weight: 700; margin-top: 5px; }
 .card-box {
        padding: 20px;
        border-radius: 10px;
        border: 2px solid #1E4620;
        margin-bottom: 15px;
        background-color: rgba(30, 70, 32, 0.05);
    }
 .card-title-custom { font-size: 11pt; font-weight: bold; text-transform: uppercase; }
 .card-value-custom { font-size: 22pt; font-weight: 900; color: #1E4620; margin-top: 5px; }
 .stButton>button {
        background-color: #1E4620!important;
        color: #FFFFFF!important;
        font-weight: bold!important;
        border-radius: 8px!important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GESTIÓN DE USUARIOS REALES Y LOGIN
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = ""
    st.session_state["rol"] = ""
    st.session_state["nombre_usuario"] = ""

def formulario_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
