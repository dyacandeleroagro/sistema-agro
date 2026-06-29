import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Configuración inicial
st.set_page_config(page_title="D&A Candelero Agro", layout="wide")

# Base de usuarios
USUARIOS = {
    "daniel": {"pass": "daniel2026", "rol": "Admin", "nombre": "Daniel Candelero"},
    "agustin": {"pass": "agustin2026", "rol": "Admin", "nombre": "Agustin Candelero"},
    "damian": {"pass": "damian123", "rol": "Empleado", "nombre": "Damian Acosta"}
}

# Inicializar estado de sesión
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False

def login():
    st.title("🚜 D&A Candelero Agro - Acceso")
    user = st.text_input("Usuario").lower()
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if user in USUARIOS and USUARIOS[user]["pass"] == pwd:
            st.session_state["autenticado"] = True
            st.session_state["user"] = user
            st.session_state["rol"] = USUARIOS[user]["rol"]
            st.session_state["nombre"] = USUARIOS[user]["nombre"]
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

if not st.session_state["autenticado"]:
    login()
    st.stop()

# --- PANEL DE CONTROL ---
st.sidebar.title(f"Bienvenido {st.session_state['nombre']}")
st.sidebar.info(f"Rol: {st.session_state['rol']}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()

st.header("🏢 Panel de Control General")

if st.session_state["rol"] == "Admin":
    st.success("Acceso total como Administrador")
    col1, col2 = st.columns(2)
    with col1: st.metric("Telemetría Cargada", "45 registros")
    with col2: st.metric("Gastos Totales", "$ 1.2M")
    
    # Aquí irían tus tablas reales
    st.subheader("Gestión de Datos")
    st.write("Configuración, usuarios y reportes financieros.")

else:
    st.warning("Acceso limitado: Panel de Empleado")
    st.write("Carga de datos diarios para operarios.")
    # Formulario simple para empleados
    with st.form("carga_empleado"):
        lote = st.text_input("Lote de trabajo")
        horas = st.number_input("Horas hombre")
        if st.form_submit_button("Enviar reporte"):
            st.write("Reporte enviado a la base de datos.")
    st.rerun()
