import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configuración inicial
st.set_page_config(page_title="D&A Candelero Agro", layout="wide")

# Conexión a Google Sheets (usando el nombre 'gsheets')
conn = st.connection("gsheets", type=GSheetsConnection)

# Seguridad y Login
USUARIOS = {
    "daniel": {"pass": "daniel2026", "rol": "Admin", "nombre": "Daniel Candelero"},
    "agustin": {"pass": "agustin2026", "rol": "Admin", "nombre": "Agustin Candelero"}
}

if "autenticado" not in st.session_state: st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Acceso al Sistema")
    user = st.text_input("Usuario").lower()
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user in USUARIOS and USUARIOS[user]["pass"] == pwd:
            st.session_state["autenticado"] = True
            st.session_state["nombre"] = USUARIOS[user]["nombre"]
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# Si está autenticado, mostramos el sistema completo
st.title(f"Bienvenido, {st.session_state['nombre']}")

# Pestañas principales
tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumen", "🧾 Facturas", "🚜 Lotes y Seguros", "👥 Empleados"])

with tab1:
    st.header("Resumen General")
    st.write("Acá verás los datos de cosecha y gastos.")
    # Aquí iría tu lógica de datos
with tab2:
    st.header("Gestión de Facturas")
    try:
        df = conn.read(worksheet="datos_facturas", ttl=0)
        st.dataframe(df)
    except:
        st.error("No se puede conectar a la hoja de Facturas. Configurá los 'Secrets'!")
with tab3:
    st.header("Lotes y Seguros")
    st.write("Información sobre el estado de cada lote.")
with tab4:
    st.header("Empleados")
    st.write("Registro y pago de personal.")

if st.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()
