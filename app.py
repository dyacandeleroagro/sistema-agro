import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURACIÓN DE LA INTERFAZ
# ==========================================
st.set_page_config(page_title="D&A Candelero Agro", layout="wide", page_icon="🚜")

st.markdown("""
    <style>
    .header-container { padding: 20px; border-radius: 12px; border: 3px solid #1E4620; margin-bottom: 25px; }
    .main-title { font-size: 30pt; font-weight: 900; color: #1E4620; }
    .card-box { padding: 20px; border: 2px solid #1E4620; background-color: #f9f9f9; border-radius: 10px; }
    .card-value { font-size: 20pt; font-weight: bold; color: #1E4620; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# SEGURIDAD Y LOGIN
# ==========================================
USUARIOS = {
    "daniel": {"pass": "daniel2026", "rol": "Administrador", "nombre": "Daniel Candelero"},
    "agustin": {"pass": "agustin2026", "rol": "Administrador", "nombre": "Agustin Candelero"},
    "damian": {"pass": "damian123", "rol": "Operario", "nombre": "Damian Acosta"}
}

if "autenticado" not in st.session_state: st.session_state["autenticado"] = False

def login():
    st.markdown('<div class="header-container"><h1 style="text-align:center;">🔐 Acceso al Sistema</h1></div>', unsafe_allow_html=True)
    user = st.text_input("Usuario").lower()
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user in USUARIOS and USUARIOS[user]["pass"] == pwd:
            st.session_state["autenticado"] = True
            st.session_state["user"] = user
            st.session_state["nombre"] = USUARIOS[user]["nombre"]
            st.session_state["rol"] = USUARIOS[user]["rol"]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

if not st.session_state["autenticado"]:
    login()
    st.stop()

# ==========================================
# CONEXIÓN Y DATOS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data(tab): return conn.read(worksheet=tab, ttl=0)

# ==========================================
# PANTALLA PRINCIPAL
# ==========================================
st.markdown(f'<div class="header-container"><div class="main-title">D&A CANDELERO AGRO</div><p>Bienvenido, {st.session_state["nombre"]}</p></div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Resumen", "🚜 Telemetría", "🧾 Gastos"])

with tab1:
    st.header("📊 Analíticas")
    # Ejemplo de resumen
    st.metric("Total Ingresos", "$ 0.00")

with tab2:
    st.header("🚜 Carga de Telemetría")
    with st.form("telemetria"):
        lote = st.text_input("Lote")
        has = st.number_input("Hectáreas")
        if st.form_submit_button("Guardar"):
            st.success(f"Datos de {lote} guardados")

with tab3:
    st.header("🧾 Gastos")
    df = get_data("datos_facturas")
    st.dataframe(df)

if st.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()
