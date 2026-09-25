import streamlit as st
import pandas as pd
import os
import datetime
import psycopg2
import os
import re
import hashlib
import time

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from pages.ingresos import pantalla_ingresos
from pages.clientes import pantalla_clientes
from pages.servicios import pantalla_servicios
from pages.campanas import pantalla_campanas
from pages.combustible import pantalla_combustible
from pages.agenda import pantalla_agenda
from pages.facturacion import pantalla_facturacion
from pages.mantenimiento import pantalla_mantenimiento
from pages.administracion import pantalla_administracion
from pages.panel_dueno import pantalla_panel_dueno
from database import get_conn

def check_password(usuario, password):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT nombre, rol, activo
        FROM usuarios
        WHERE usuario = %s
          AND password = %s
    """, (usuario, password))

    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        nombre, rol, activo = result

        if not activo:
            return None, "DESHABILITADO"

        return nombre, rol.strip()

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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="header-container" style="text-align: center;">', unsafe_allow_html=True)
        st.markdown('<div class="main-title" style="font-size: 22pt;">🔐 Acceso al Sistema</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">D&A Candelero Agro</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            txt_user = st.text_input("Usuario (en minúsculas)").strip().lower()
            txt_pass = st.text_input("Contraseña", type="password").strip()
            btn_login = st.form_submit_button("Ingresar al Sistema")

            if btn_login:
                nombre, rol = check_password(txt_user, txt_pass)

                if rol == "DESHABILITADO":
                    st.error("⛔ Este usuario está deshabilitado. Contacte al administrador.")

                elif nombre:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = txt_user
                    st.session_state["rol"] = rol
                    st.session_state["nombre_usuario"] = nombre
                    st.success(f"¡Bienvenido {nombre}!")
                    st.rerun()

                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
# ==========================================
# SI NO ESTA LOGUEADO MOSTRAR LOGIN
# ==========================================

if not st.session_state["autenticado"]:
    formulario_login()
    st.stop()
# ==========================================
# VERIFICACIÓN Y CARGA DE BASES DE DATOS (CSV)
# ==========================================
if not os.path.exists("comprobantes"):
    os.makedirs("comprobantes")

# ==========================================================
# CARGA DE GASTOS COMERCIALES DESDE NEON
# ==========================================================

columnas_facturas = {
    "ID": "",
    "Fecha Registro": "",
    "Proveedor": "",
    "Monto Original": 0.0,
    "Moneda": "ARS",
    "Monto (ARS)": 0.0,
    "Categoría": "",
    "Lote Asignado": "",
    "Estado Pago": "",
    "Archivo Comprobante": ""
}


def cargar_gastos_desde_neon():

    try:

        conn = get_conn()

        query = """
            SELECT
                id_gasto,
                fecha_registro,
                proveedor,
                monto_original,
                moneda,
                monto_ars,
                categoria,
                lote_asignado,
                estado_pago,
                archivo_comprobante
            FROM gastos_comerciales
            ORDER BY fecha_registro, id
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        conn.close()

        if df.empty:
            return pd.DataFrame()

        df = df.rename(
            columns={
                "id_gasto": "ID",
                "fecha_registro": "Fecha Registro",
                "proveedor": "Proveedor",
                "monto_original": "Monto Original",
                "moneda": "Moneda",
                "monto_ars": "Monto (ARS)",
                "categoria": "Categoría",
                "lote_asignado": "Lote Asignado",
                "estado_pago": "Estado Pago",
                "archivo_comprobante": "Archivo Comprobante"
            }
        )

        return df

    except Exception as e:

        st.warning(
            f"⚠️ No se pudieron cargar los gastos desde Neon: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# CARGAR GASTOS
# ==========================================================

df_facturas = cargar_gastos_desde_neon()


# ==========================================================
# RESPALDO / MIGRACIÓN DESDE CSV
# ==========================================================

if (
    df_facturas.empty
    and os.path.exists("datos_facturas.csv")
):

    df_csv_facturas = pd.read_csv(
        "datos_facturas.csv"
    )

    if not df_csv_facturas.empty:

        for columna, valor in columnas_facturas.items():

            if columna not in df_csv_facturas.columns:

                df_csv_facturas[columna] = valor

        df_facturas = df_csv_facturas.copy()


# ==========================================================
# ASEGURAR COLUMNAS
# ==========================================================

for columna, valor in columnas_facturas.items():

    if columna not in df_facturas.columns:

        df_facturas[columna] = valor


# ==========================================================
# ASEGURAR ID COMO TEXTO
# ==========================================================

df_facturas["ID"] = (
    df_facturas["ID"]
    .fillna("")
    .astype(str)
)
# ==========================================================
# GUARDAR GASTO EN NEON
# ==========================================================

def guardar_gasto_en_neon(gasto):

    conn = None
    cursor = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        query = """
            INSERT INTO gastos_comerciales (
                id_gasto,
                fecha_registro,
                proveedor,
                monto_original,
                moneda,
                monto_ars,
                categoria,
                lote_asignado,
                estado_pago,
                archivo_comprobante
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """

        valores = (
            str(gasto.get("ID", "")),
            gasto.get("Fecha Registro") or None,
            gasto.get("Proveedor", ""),
            float(gasto.get("Monto Original", 0) or 0),
            gasto.get("Moneda", "ARS"),
            float(gasto.get("Monto (ARS)", 0) or 0),
            gasto.get("Categoría", ""),
            gasto.get("Lote Asignado", ""),
            gasto.get("Estado Pago", ""),
            gasto.get("Archivo Comprobante", "")
        )

        cursor.execute(
            query,
            valores
        )

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        st.error(
            f"❌ Error guardando gasto en Neon: {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()
if not os.path.exists("registro_telemetria.csv"):
    pd.DataFrame(columns=["Fecha", "Maquinaria", "Lote", "Has Trabajadas", "Gasoil Consumido (L)", "Eficiencia (L/Ha)"]).to_csv("registro_telemetria.csv", index=False)
df_telemetria = pd.read_csv("registro_telemetria.csv")

if not os.path.exists("registro_empleados.csv"):
    df_inicial_emp = pd.DataFrame([
        {"Nombre": "Damian Acosta", "Puesto": "Tractorista", "Porcentaje (%)": 0.0},
        {"Nombre": "German Posseto", "Puesto": "Maquinista Cosechadora", "Porcentaje (%)": 0.0},
        {"Nombre": "Gonzalo Vega", "Puesto": "Tractorista", "Porcentaje (%)": 0.0}
    ])
    df_inicial_emp.to_csv("registro_empleados.csv", index=False)
df_empleados = pd.read_csv("registro_empleados.csv")

if not os.path.exists("registro_pagos_empleados.csv"):

    pd.DataFrame(columns=[
        "ID_Pago",
        "Fecha Pago",
        "Nombre Empleado",
        "Fecha Trabajo",
        "Hora Entrada",
        "Hora Salida",
        "Horas Trabajadas",
        "Valor Hora",
        "Monto (ARS)",
        "Tipo Registro",
        "Estado Pago",
        "Concepto"
    ]).to_csv(
        "registro_pagos_empleados.csv",
        index=False
    )

ARCHIVO_PAGOS_EMPLEADOS = "registro_pagos_empleados.csv"

# ==========================================================
# CARGA DE PAGOS DE EMPLEADOS DESDE NEON
# ==========================================================

columnas_pagos = {
    "ID_Pago": "",
    "Fecha Pago": "",
    "Nombre Empleado": "",
    "Fecha Trabajo": "",
    "Hora Entrada": "",
    "Hora Salida": "",
    "Horas Trabajadas": 0.0,
    "Valor Hora": 0.0,
    "Monto (ARS)": 0.0,
    "Tipo Registro": "",
    "Estado Pago": "",
    "Concepto": "",
    "Porcentaje Bonificacion": 0.0,
    "Monto Bonificacion (ARS)": 0.0,
    "Porcentaje Descuento": 0.0,
    "Monto Descuento (ARS)": 0.0,
    "Monto Trabajado (ARS)": 0.0,
    "Monto Pagado (ARS)": 0.0,
    "Monto Final Trabajo (ARS)": 0.0,
    "Adelanto Generado (ARS)": 0.0,
    "Monto Compensado (ARS)": 0.0,
    "Saldo Adelanto (ARS)": 0.0,
    "Saldo Pendiente Pago (ARS)": 0.0,
    "Comprobantes": "",
    "PDF Liquidacion": ""
}


def cargar_pagos_desde_neon():

    try:

        conn = get_conn()

        query = """
            SELECT
                id_pago,
                fecha_pago,
                nombre_empleado,
                fecha_trabajo,
                hora_entrada,
                hora_salida,
                horas_trabajadas,
                valor_hora,
                monto_ars,
                tipo_registro,
                estado_pago,
                concepto,
                porcentaje_bonificacion,
                monto_bonificacion,
                porcentaje_descuento,
                monto_descuento,
                monto_trabajado_ars,
                monto_pagado_ars,
                monto_final_trabajo_ars,
                adelanto_generado_ars,
                monto_compensado_ars,
                saldo_adelanto_ars,
                saldo_pendiente_pago_ars,
                comprobantes,
                pdf_liquidacion
            FROM pagos_empleados
            ORDER BY fecha_pago, id
        """

        df = pd.read_sql_query(
            query,
            conn
        )

        conn.close()

        if df.empty:

            return pd.DataFrame()

        df = df.rename(
            columns={
                "id_pago": "ID_Pago",
                "fecha_pago": "Fecha Pago",
                "nombre_empleado": "Nombre Empleado",
                "fecha_trabajo": "Fecha Trabajo",
                "hora_entrada": "Hora Entrada",
                "hora_salida": "Hora Salida",
                "horas_trabajadas": "Horas Trabajadas",
                "valor_hora": "Valor Hora",
                "monto_ars": "Monto (ARS)",
                "tipo_registro": "Tipo Registro",
                "estado_pago": "Estado Pago",
                "concepto": "Concepto",
                "porcentaje_bonificacion": "Porcentaje Bonificacion",
                "monto_bonificacion": "Monto Bonificacion (ARS)",
                "porcentaje_descuento": "Porcentaje Descuento",
                "monto_descuento": "Monto Descuento (ARS)",
                "monto_trabajado_ars": "Monto Trabajado (ARS)",
                "monto_pagado_ars": "Monto Pagado (ARS)",
                "monto_final_trabajo_ars": "Monto Final Trabajo (ARS)",
                "adelanto_generado_ars": "Adelanto Generado (ARS)",
                "monto_compensado_ars": "Monto Compensado (ARS)",
                "saldo_adelanto_ars": "Saldo Adelanto (ARS)",
                "saldo_pendiente_pago_ars": "Saldo Pendiente Pago (ARS)",
                "comprobantes": "Comprobantes",
                "pdf_liquidacion": "PDF Liquidacion"
            }
        )

        return df

    except Exception as e:

        st.warning(
            f"⚠️ No se pudo cargar pagos desde Neon: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# CARGAR PAGOS
# ==========================================================

df_pagos_empleados = cargar_pagos_desde_neon()


# ==========================================================
# RESPALDO / MIGRACIÓN AUTOMÁTICA DESDE CSV
# ==========================================================

if (
    df_pagos_empleados.empty
    and os.path.exists(ARCHIVO_PAGOS_EMPLEADOS)
):

    df_csv_pagos = pd.read_csv(
        ARCHIVO_PAGOS_EMPLEADOS,
        encoding="utf-8-sig"
    )

    if not df_csv_pagos.empty:

        for columna, valor in columnas_pagos.items():

            if columna not in df_csv_pagos.columns:

                df_csv_pagos[columna] = valor

        df_pagos_empleados = df_csv_pagos.copy()


# ==========================================================
# ASEGURAR COLUMNAS
# ==========================================================

for columna, valor in columnas_pagos.items():

    if columna not in df_pagos_empleados.columns:

        df_pagos_empleados[columna] = valor


# ==========================================================
# ASEGURAR ID COMO TEXTO
# ==========================================================

df_pagos_empleados["ID_Pago"] = (
    df_pagos_empleados["ID_Pago"]
    .fillna("")
    .astype(str)
)
# ==========================================================
# GUARDAR PAGO EN NEON
# ==========================================================

def guardar_pago_en_neon(pago):

    conn = None
    cursor = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        query = """
            INSERT INTO pagos_empleados (
                id_pago,
                fecha_pago,
                nombre_empleado,
                fecha_trabajo,
                hora_entrada,
                hora_salida,
                horas_trabajadas,
                valor_hora,
                monto_ars,
                tipo_registro,
                estado_pago,
                concepto,
                porcentaje_bonificacion,
                monto_bonificacion,
                porcentaje_descuento,
                monto_descuento,
                monto_trabajado_ars,
                monto_pagado_ars,
                monto_final_trabajo_ars,
                adelanto_generado_ars,
                monto_compensado_ars,
                saldo_adelanto_ars,
                saldo_pendiente_pago_ars,
                comprobantes,
                pdf_liquidacion
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
        """

        valores = (
            str(pago.get("ID_Pago", "")),
            pago.get("Fecha Pago") or None,
            pago.get("Nombre Empleado", ""),
            pago.get("Fecha Trabajo", ""),
            pago.get("Hora Entrada", ""),
            pago.get("Hora Salida", ""),
            float(pago.get("Horas Trabajadas", 0) or 0),
            float(pago.get("Valor Hora", 0) or 0),
            float(pago.get("Monto (ARS)", 0) or 0),
            pago.get("Tipo Registro", ""),
            pago.get("Estado Pago", ""),
            pago.get("Concepto", ""),
            float(pago.get("Porcentaje Bonificacion", 0) or 0),
            float(pago.get("Monto Bonificacion (ARS)", 0) or 0),
            float(pago.get("Porcentaje Descuento", 0) or 0),
            float(pago.get("Monto Descuento (ARS)", 0) or 0),
            float(pago.get("Monto Trabajado (ARS)", 0) or 0),
            float(pago.get("Monto Pagado (ARS)", 0) or 0),
            float(pago.get("Monto Final Trabajo (ARS)", 0) or 0),
            float(pago.get("Adelanto Generado (ARS)", 0) or 0),
            float(pago.get("Monto Compensado (ARS)", 0) or 0),
            float(pago.get("Saldo Adelanto (ARS)", 0) or 0),
            float(pago.get("Saldo Pendiente Pago (ARS)", 0) or 0),
            pago.get("Comprobantes", ""),
            pago.get("PDF Liquidacion", "")
        )

        cursor.execute(query, valores)

        conn.commit()

        return True

    except Exception as e:

        if conn:
            conn.rollback()

        st.error(
            f"❌ Error guardando el pago en Neon: {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

if not os.path.exists("registro_ingresos.csv"):
    pd.DataFrame(columns=["ID_Ingreso", "Fecha", "Cliente", "Tipo Servicio", "Lote/Establecimiento", "Hectáreas", "Monto Total (ARS)", "Detalle"]).to_csv("registro_ingresos.csv", index=False)
df_ingresos = pd.read_csv("registro_ingresos.csv")
df_ingresos["ID_Ingreso"] = df_ingresos["ID_Ingreso"].astype(str)

if not os.path.exists("registro_seguros.csv"):
    pd.DataFrame(columns=["ID_Seguro", "Compañía", "Tipo Cobertura", "Bien Asegurado", "Vencimiento", "Monto Prima (ARS)", "Estado Pago"]).to_csv("registro_seguros.csv", index=False)
df_seguros = pd.read_csv("registro_seguros.csv")
df_seguros["ID_Seguro"] = df_seguros["ID_Seguro"].astype(str)

TIPO_CAMBIO_OFICIAL = 950.0

# ==========================================
# ENCABEZADO PRINCIPAL (CON LOGOUT)
# ==========================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)
col_logo, col_titulo, col_user = st.columns([1, 3, 1])
with col_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=130)
    else: st.markdown("<h1 style='font-size: 40pt; margin: 0;'>🚜</h1>", unsafe_allow_html=True)
with col_titulo:
    st.markdown('<div class="main-title">D&A CANDELERO AGRO</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">Sesión iniciada: <b>{st.session_state["nombre_usuario"]}</b> ({st.session_state["rol"]})</div>', unsafe_allow_html=True)
with col_user:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", key="btn_logout"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = ""
        st.session_state["rol"] = ""
        st.session_state["nombre_usuario"] = ""
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN FILTRADA DE PESTAÑAS POR ROL
# ==========================================
rol_actual = st.session_state["rol"]
nombre_actual = st.session_state["nombre_usuario"]

# ===============================
# ROLES DEL USUARIO
# ===============================

roles_usuario = [
    r.strip()
    for r in rol_actual.split(",")
    if r.strip()
]

def tiene_rol(*roles):
    return any(r in roles_usuario for r in roles)

# Si está deshabilitado y NO es dueño
if (
    "Deshabilitado" in roles_usuario
    and
    "Dueño" not in roles_usuario
):
    st.error("⛔ Este usuario está deshabilitado.")
    st.stop()

opciones_menu = []

if rol_actual == "Dueño":

    opciones = [
        "📈 ANALÍTICAS CENTRALES",
        "🚜 LABORES Y LOTES",
        "💰 INGRESOS POR TRABAJOS",
        "🧾 GASTOS COMERCIALES",
        "🔍 CUENTAS PENDIENTES",
        "👥 SISTEMA DE TRIPULACIÓN",
        "📋 RENDICIÓN POR OPERARIO",
        "👥 CLIENTES",
        "🧾 FACTURACIÓN",
        "🛠 SERVICIOS",
        "⚙ ADMINISTRACIÓN",
        "🛡 SEGUROS Y COBERTURAS",
        "🗄 CONTROL DE ERRORES"
    ]

elif rol_actual == "Administrador":

    opciones = [
        "📈 ANALÍTICAS CENTRALES",
        "🚜 LABORES Y LOTES",
        "💰 INGRESOS POR TRABAJOS",
        "🧾 GASTOS COMERCIALES",
        "🔍 CUENTAS PENDIENTES",
        "👥 SISTEMA DE TRIPULACIÓN",
        "📋 RENDICIÓN POR OPERARIO",
        "👥 CLIENTES",
        "🧾 FACTURACIÓN",
        "🛠 SERVICIOS",
        "⚙ ADMINISTRACIÓN",
        "🛡 SEGUROS Y COBERTURAS"
    ]

else:

    opciones = [
        "🚜 LABORES Y LOTES",
        "📋 RENDICIÓN POR OPERARIO"
    ]

opciones = []

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("📈 ANALÍTICAS CENTRALES")

if tiene_rol("Dueño","Administrador","Encargado","Operario","Maquinista"):
    opciones.append("🚜 LABORES Y LOTES")

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("💰 INGRESOS POR TRABAJOS")

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("🧾 GASTOS COMERCIALES")

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("🔍 CUENTAS PENDIENTES")

if tiene_rol("Dueño","Administrador","Encargado"):
    opciones.append("👥 SISTEMA DE TRIPULACIÓN")

if tiene_rol("Dueño","Administrador","Encargado","Operario","Maquinista"):
    opciones.append("📋 RENDICIÓN POR OPERARIO")

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("👥 CLIENTES")

if tiene_rol("Dueño","Administrador","Contador"):
    opciones.append("🧾 FACTURACIÓN")

if tiene_rol("Dueño","Administrador"):
    opciones.append("🛠 SERVICIOS")

if tiene_rol("Dueño","Administrador","Encargado"):
    opciones.append("🌱 CAMPAÑAS AGRÍCOLAS")

if tiene_rol("Dueño","Administrador","Encargado"):
    opciones.append("🔧 MANTENIMIENTO DE MAQUINARIA")

if tiene_rol("Dueño","Administrador","Encargado","Operario"):
    opciones.append("⛽ CONTROL DE COMBUSTIBLE")

if tiene_rol("Dueño","Administrador","Encargado"):
    opciones.append("📅 AGENDA Y VENCIMIENTOS")

if tiene_rol("Dueño","Administrador"):
    opciones.append("⚙ ADMINISTRACIÓN")

if tiene_rol("Dueño","Administrador"):
    opciones.append("🛡 SEGUROS Y COBERTURAS")

if tiene_rol("Dueño"):
    opciones.append("🗄 CONTROL DE ERRORES")

if tiene_rol("Dueño"):
    opciones.append("👑 PANEL DEL DUEÑO")

menu = st.sidebar.radio(
    "📂 Menú",
    opciones
)

# ----------------------------------------------------
# PESTAÑA: ANALÍTICAS CENTRALES
# ----------------------------------------------------

if menu == "📈 ANALÍTICAS CENTRALES":

    st.header("Resumen General del Negocio")

    total_gasto_facturas = (
        df_facturas["Monto (ARS)"].sum()
        if not df_facturas.empty else 0.0
    )

    total_pendiente_facturas = (
        df_facturas[
            df_facturas["Estado Pago"].str.contains(
                "Pendiente",
                case=False,
                na=False
            )
        ]["Monto (ARS)"].sum()
        if not df_facturas.empty else 0.0
    )

    total_tripulacion_global = (
        df_pagos_empleados["Monto (ARS)"].sum()
        if not df_pagos_empleados.empty else 0.0
    )

    total_ingresos_global = (
        df_ingresos["Monto Total (ARS)"].sum()
        if not df_ingresos.empty else 0.0
    )

    total_has_global = (
        df_telemetria["Has Trabajadas"].sum()
        if not df_telemetria.empty else 0.0
    )

    total_litros_global = (
        df_telemetria["Gasoil Consumido (L)"].sum()
        if not df_telemetria.empty else 0.0
    )

    eficiencia_flota = (
        total_litros_global / total_has_global
        if total_has_global > 0 else 0.0
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    💰 Facturación Total Ingresos
                </div>
                <div class="card-value-custom">
                    $ {total_ingresos_global:,.2f}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    🧾 Gastos Comerciales
                </div>
                <div class="card-value-custom">
                    $ {total_gasto_facturas:,.2f}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    👥 Total Costo Tripulación
                </div>
                <div class="card-value-custom">
                    $ {total_tripulacion_global:,.2f}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    🔴 Cuentas Proveedores Pendientes
                </div>
                <div class="card-value-custom">
                    $ {total_pendiente_facturas:,.2f}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    c5, c6 = st.columns(2)

    with c5:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    🌾 Superficie Total Operada
                </div>
                <div class="card-value-custom">
                    {total_has_global:,.1f} Has
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c6:
        st.markdown(
            f"""
            <div class="card-box">
                <div class="card-title-custom">
                    ⛽ Promedio Gasoil Flota
                </div>
                <div class="card-value-custom">
                    {eficiencia_flota:.2f} L/Ha
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ----------------------------------------------------
# PESTAÑA: LABORES Y LOTES
# ----------------------------------------------------

if menu == "🚜 LABORES Y LOTES":

    st.header("🚜 Partes Diarios de Labores")

    with st.form("form_labores"):

        col_la1, col_la2, col_la3 = st.columns(3)

        with col_la1:

            fecha_labor = st.date_input(
                "Fecha de Labor",
                value=datetime.date.today()
            )

            lote_labor = st.text_input(
                "Nombre del Campo / Lote"
            )

        with col_la2:

            maquina_labor = st.selectbox(
                "Maquinaria Activa",
                [
                    "Cosechadora CR 7.90",
                    "Tractor Valtra",
                    "Pulverizadora",
                    "Camión"
                ]
            )

            has_labor = st.number_input(
                "Hectáreas Trabajadas",
                min_value=0.0,
                step=1.0
            )

        with col_la3:

            eficiencia_labor = st.number_input(
                "Consumo Gasoil (Litros por Ha)",
                min_value=0.0,
                step=0.1
            )

            btn_lab = st.form_submit_button(
                "💾 Guardar Trabajo"
            )


    if btn_lab and lote_labor and has_labor > 0:

        litros_totales = round(
            has_labor * eficiencia_labor,
            2
        )

        nueva_labor = {

            "Fecha": fecha_labor.strftime("%Y-%m-%d"),

            "Maquinaria": maquina_labor,

            "Lote": lote_labor.strip(),

            "Has Trabajadas": has_labor,

            "Gasoil Consumido (L)": litros_totales,

            "Eficiencia (L/Ha)": round(
                eficiencia_labor,
                2
            )
        }


        df_telemetria = pd.concat(
            [
                df_telemetria,
                pd.DataFrame([nueva_labor])
            ],
            ignore_index=True
        )


        df_telemetria.to_csv(
            "registro_telemetria.csv",
            index=False
        )


        st.success(
            "✅ Trabajo guardado correctamente"
        )

        st.rerun()



    st.divider()


    st.subheader(
        "📋 Partes diarios registrados"
    )


    if not df_telemetria.empty:

        st.dataframe(
            df_telemetria,
            use_container_width=True
        )


        st.divider()


        st.subheader(
            "✏️ Editar o eliminar parte diario"
        )


        labor = st.selectbox(

            "Seleccionar trabajo",

            df_telemetria.index,

            format_func=lambda x:
                f"{df_telemetria.loc[x,'Fecha']} - {df_telemetria.loc[x,'Lote']}"

        )


        fila = df_telemetria.loc[labor]


        fecha_edit = st.date_input(

            "Fecha",

            value=pd.to_datetime(
                fila["Fecha"]
            )

        )


        maquinas = [

            "Cosechadora CR 7.90",

            "Tractor Valtra",

            "Pulverizadora",

            "Camión"

        ]


        maquina_edit = st.selectbox(

            "Maquinaria",

            maquinas,

            index=maquinas.index(
                fila["Maquinaria"]
            )
            if fila["Maquinaria"] in maquinas
            else 0

        )


        lote_edit = st.text_input(

            "Lote",

            value=fila["Lote"]

        )


        has_edit = st.number_input(

            "Hectáreas",

            value=float(
                fila["Has Trabajadas"]
            )

        )


        eficiencia_edit = st.number_input(

            "Litros por Ha",

            value=float(
                fila["Eficiencia (L/Ha)"]
            )

        )


        col1, col2 = st.columns(2)


        with col1:


            if st.button(
                "💾 Guardar cambios",
                key="guardar_parte_diario"
            ):


                df_telemetria.loc[
                    labor,
                    "Fecha"
                ] = fecha_edit.strftime("%Y-%m-%d")


                df_telemetria.loc[
                    labor,
                    "Maquinaria"
                ] = maquina_edit


                df_telemetria.loc[
                    labor,
                    "Lote"
                ] = lote_edit


                df_telemetria.loc[
                    labor,
                    "Has Trabajadas"
                ] = has_edit


                df_telemetria.loc[
                    labor,
                    "Eficiencia (L/Ha)"
                ] = eficiencia_edit


                df_telemetria.loc[
                    labor,
                    "Gasoil Consumido (L)"
                ] = round(
                    has_edit * eficiencia_edit,
                    2
                )


                df_telemetria.to_csv(
                    "registro_telemetria.csv",
                    index=False
                )


                st.success(
                    "✅ Parte diario actualizado"
                )

                st.rerun()



        with col2:


            if st.button(
                "🗑 Eliminar parte diario",
                key="eliminar_parte_diario"
            ):


                df_telemetria = df_telemetria.drop(
                    labor
                )


                df_telemetria.to_csv(
                    "registro_telemetria.csv",
                    index=False
                )


                st.success(
                    "✅ Parte diario eliminado"
                )

                st.rerun()


    else:

        st.info(
            "Todavía no hay partes diarios cargados"
        )
# ----------------------------------------------------
# PESTAÑA: GASTOS COMERCIALES
# ----------------------------------------------------
if menu == "🧾 GASTOS COMERCIALES":

    st.header("🧾 Gastos Comerciales")

    with st.form("form_gastos"):

        c1, c2 = st.columns(2)

        with c1:

            fecha = st.date_input(
                "Fecha",
                value=datetime.date.today()
            )

            proveedor = st.text_input(
                "Proveedor"
            )

            categoria = st.selectbox(
                "Categoría",
                [
                    "Combustible",
                    "Repuestos",
                    "Insumos",
                    "Servicios",
                    "Impuestos",
                    "Otros"
                ]
            )

        with c2:

            monto = st.number_input(
                "Monto ($)",
                min_value=0.0,
                step=1000.0
            )

            estado = st.selectbox(
                "Estado",
                [
                    "Pendiente de Pago",
                    "Pagado"
                ]
            )

            lote = st.text_input(
                "Lote / Destino"
            )

            archivo_adjunto = st.file_uploader(
                "📎 Subir comprobante",
                type=["pdf", "png", "jpg", "jpeg"]
            )

        guardar = st.form_submit_button(
            "💾 Guardar gasto"
        )

    if guardar:

        os.makedirs("comprobantes", exist_ok=True)

        nombre_archivo_guardado = ""

        if archivo_adjunto is not None:

            nombre_archivo_guardado = (
                f"{int(datetime.datetime.now().timestamp())}_"
                f"{archivo_adjunto.name}"
            )

            ruta_comprobante = os.path.join(
                "comprobantes",
                nombre_archivo_guardado
            )

            with open(
                ruta_comprobante,
                "wb"
            ) as archivo:

                archivo.write(
                    archivo_adjunto.getbuffer()
                )

        nuevo = {

            "ID": str(int(datetime.datetime.now().timestamp())),

            "Fecha Registro": fecha.strftime("%Y-%m-%d"),

            "Proveedor": proveedor,

            "Monto Original": monto,

            "Moneda": "ARS",

            "Monto (ARS)": monto,

            "Categoría": categoria,

            "Lote Asignado": lote,

            "Estado Pago": estado,

            "Archivo Comprobante": nombre_archivo_guardado

        }

        df_facturas = pd.concat(
            [
                df_facturas,
                pd.DataFrame([nuevo])
            ],
            ignore_index=True
        )

        guardar_gasto_en_neon(nuevo)

        df_facturas.to_csv(
            "datos_facturas.csv",
            index=False
        )

        st.success("Gasto guardado correctamente")

        st.rerun()

    st.divider()

    st.subheader("📋 Gastos registrados")

    if not df_facturas.empty:

        st.dataframe(
            df_facturas,
            use_container_width=True
        )

        total = df_facturas["Monto (ARS)"].sum()

        pendientes = df_facturas[
            df_facturas["Estado Pago"] == "Pendiente de Pago"
        ]["Monto (ARS)"].sum()

        c1, c2 = st.columns(2)

        with c1:
            st.metric(
                "💰 Total Gastos",
                f"$ {total:,.2f}"
            )

        with c2:
            st.metric(
                "🔴 Pendiente de Pago",
                f"$ {pendientes:,.2f}"
            )

    else:

        st.info("Todavía no hay gastos cargados.")        
# ----------------------------------------------------
# PESTAÑA: CUENTAS PENDIENTES
# ----------------------------------------------------
if menu == "🔍 CUENTAS PENDIENTES":
        st.header("🔍 Cuentas Pendientes de Proveedores")
        df_solo_pendientes = df_facturas[df_facturas["Estado Pago"] == "Pendiente de Pago"]
        if not df_solo_pendientes.empty:
            for idx, fila in df_solo_pendientes.iterrows():
                with st.expander(f"❌ {fila['Proveedor']} — {fila['Monto Original']}"):
                    with st.form(key=f"form_liquidar_{fila['ID']}_{idx}"):
                        archivo_pendiente = st.file_uploader("Adjuntar Comprobante:", type=["pdf", "png", "jpg", "jpeg"], key=f"file_pend_{fila['ID']}_{idx}")
                        btn_cerrar_caso = st.form_submit_button("🟢 Marcar como PAGADO")
                        if btn_cerrar_caso and archivo_pendiente:
                            nombre_archivo_guardado = f"liquidado_{int(datetime.datetime.now().timestamp())}_{archivo_pendiente.name}"
                            with open(os.path.join("comprobantes", nombre_archivo_guardado), "wb") as f:
                                f.write(archivo_pendiente.getbuffer())
                            df_facturas.loc[df_facturas["ID"] == str(fila["ID"]), "Estado Pago"] = "Pagado"
                            df_facturas.loc[df_facturas["ID"] == str(fila["ID"]), "Archivo Comprobante"] = nombre_archivo_guardado
                            df_facturas.to_csv("datos_facturas.csv", index=False)
                            st.success("¡Liquidado!")
                            st.rerun()
        else: st.success("👌 ¡Ningún gasto pendiente!")

# ============================================================
# FUNCIONES PARA LIQUIDACIONES
# ============================================================

import io


def guardar_comprobantes(archivos, nuevo_id):

    nombres = []

    if not archivos:
        return nombres

    carpeta = "comprobantes_pagos"

    os.makedirs(
        carpeta,
        exist_ok=True
    )

    for archivo in archivos:

        if archivo is None:
            continue

        extension = os.path.splitext(
            archivo.name
        )[1]

        nombre_archivo = (
            f"liquidacion_{nuevo_id}_"
            f"{len(nombres) + 1}"
            f"{extension}"
        )

        ruta = os.path.join(
            carpeta,
            nombre_archivo
        )

        with open(
            ruta,
            "wb"
        ) as f:

            f.write(
                archivo.getbuffer()
            )

        nombres.append(
            nombre_archivo
        )

    return nombres


def generar_pdf_liquidacion(
    nuevo_id,
    empleado,
    fecha,
    horas,
    valor_hora,
    monto_trabajado,
    bonificacion,
    descuento,
    monto_final,
    adelanto_anterior,
    pendiente_anterior,
    compensado,
    neto_pagar,
    monto_pagado,
    adelanto_final,
    pendiente_final,
    concepto
):

    buffer = io.BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    estilos = getSampleStyleSheet()

    elementos = []

    elementos.append(
        Paragraph(
            "<b>D&A CANDELERO AGRO</b>",
            estilos["Title"]
        )
    )

    elementos.append(
        Spacer(
            1,
            8
        )
    )

    elementos.append(
        Paragraph(
            "<b>LIQUIDACIÓN DE PERSONAL</b>",
            estilos["Heading2"]
        )
    )

    elementos.append(
        Spacer(
            1,
            10
        )
    )

    datos = [
        ["Empleado", str(empleado)],
        ["Fecha", str(fecha)],
        ["ID Liquidación", str(nuevo_id)],
        ["Concepto", str(concepto)],
        ["Horas trabajadas", f"{horas:,.2f}"],
        ["Valor hora", f"$ {valor_hora:,.2f}"],
        ["Monto trabajado", f"$ {monto_trabajado:,.2f}"],
        ["Bonificación", f"$ {bonificacion:,.2f}"],
        ["Descuento", f"$ {descuento:,.2f}"],
        ["Total final trabajo", f"$ {monto_final:,.2f}"],
        ["Adelanto anterior", f"$ {adelanto_anterior:,.2f}"],
        ["Pendiente anterior", f"$ {pendiente_anterior:,.2f}"],
        ["Adelanto compensado", f"$ {compensado:,.2f}"],
        ["Neto a pagar", f"$ {neto_pagar:,.2f}"],
        ["Monto realmente pagado", f"$ {monto_pagado:,.2f}"],
        ["Adelanto final", f"$ {adelanto_final:,.2f}"],
        ["Pendiente final", f"$ {pendiente_final:,.2f}"],
    ]

    tabla = Table(
        datos,
        colWidths=[
            75 * mm,
            95 * mm
        ]
    )

    tabla.setStyle(
        TableStyle([
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.lightgrey
            ),
            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "Helvetica-Bold"
            ),
            (
                "FONTNAME",
                (1, 0),
                (1, -1),
                "Helvetica"
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                6
            ),
        ])
    )

    elementos.append(
        tabla
    )

    elementos.append(
        Spacer(
            1,
            20
        )
    )

    elementos.append(
        Paragraph(
            "Firma del empleado: ______________________________",
            estilos["Normal"]
        )
    )

    elementos.append(
        Spacer(
            1,
            15
        )
    )

    elementos.append(
        Paragraph(
            "Firma responsable: ________________________________",
            estilos["Normal"]
        )
    )

    documento.build(
        elementos
    )

    buffer.seek(0)

    return buffer.getvalue()


def obtener_saldos_empleado(
    df_pagos,
    empleado
):

    if df_pagos.empty:

        return {
            "adelanto": 0.0,
            "pendiente": 0.0
        }

    df_emp = df_pagos[
        df_pagos["Nombre Empleado"].astype(str).str.strip()
        == str(empleado).strip()
    ].copy()

    if df_emp.empty:

        return {
            "adelanto": 0.0,
            "pendiente": 0.0
        }

    # ==========================================
    # ORDENAR LOS MOVIMIENTOS
    # ==========================================

    if "Fecha Pago" in df_emp.columns:

        df_emp["_orden_fecha"] = pd.to_datetime(
            df_emp["Fecha Pago"],
            errors="coerce"
        )

    else:

        df_emp["_orden_fecha"] = pd.NaT

    df_emp["_orden_id"] = pd.to_numeric(
        df_emp["ID_Pago"],
        errors="coerce"
    ).fillna(0)

    df_emp = df_emp.sort_values(
        by=[
            "_orden_fecha",
            "_orden_id"
        ]
    )

    # ==========================================
    # TOMAR EL ÚLTIMO SALDO REAL
    # ==========================================

    ultima_fila = df_emp.iloc[-1]

    saldo_adelanto = pd.to_numeric(
        ultima_fila.get(
            "Saldo Adelanto (ARS)",
            0
        ),
        errors="coerce"
    )

    saldo_pendiente = pd.to_numeric(
        ultima_fila.get(
            "Saldo Pendiente Pago (ARS)",
            0
        ),
        errors="coerce"
    )

    if pd.isna(
        saldo_adelanto
    ):

        saldo_adelanto = 0.0

    if pd.isna(
        saldo_pendiente
    ):

        saldo_pendiente = 0.0

    return {
        "adelanto": float(
            max(
                saldo_adelanto,
                0.0
            )
        ),
        "pendiente": float(
            max(
                saldo_pendiente,
                0.0
            )
        )
    }


def obtener_saldo_adelanto(
    df_pagos,
    empleado
):

    saldos = obtener_saldos_empleado(
        df_pagos,
        empleado
    )

    return saldos["adelanto"]
# ----------------------------------------------------
# PESTAÑA: SISTEMA DE TRIPULACIÓN
# ----------------------------------------------------

if menu == "👥 SISTEMA DE TRIPULACIÓN":

    st.header("👤 Personal y Comisiones de la Tripulación")

    emp_col1, emp_col2 = st.columns(2)

    # ==================================================
    # COLUMNA 1 - PERSONAL
    # ==================================================

    with emp_col1:

        st.subheader("1. Gestión del Personal Fijo")

        if not df_empleados.empty:

            st.dataframe(
                df_empleados,
                use_container_width=True
            )

        st.markdown("---")

        st.subheader(
            "Agregar Nuevo Integrante "
            "(si ingresa alguien nuevo)"
        )

        with st.form("form_alta_empleado"):

            n_nombre = st.text_input(
                "Nombre Completo (Ej: Juan Perez)"
            )

            n_puesto = st.selectbox(
                "Rol",
                [
                    "Maquinista Cosechadora",
                    "Tractorista",
                    "Ayudante / Mecánico"
                ]
            )

            n_porcentaje = st.number_input(
                "Comisión (%)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                value=0.0
            )

            btn_alta_emp = st.form_submit_button(
                "💾 Guardar Nuevo Operario"
            )

            if btn_alta_emp and n_nombre:

                nuevo_emp = {
                    "Nombre": n_nombre.strip(),
                    "Puesto": n_puesto,
                    "Porcentaje (%)": n_porcentaje
                }

                df_empleados = pd.concat(
                    [
                        df_empleados,
                        pd.DataFrame([nuevo_emp])
                    ],
                    ignore_index=True
                )

                df_empleados.to_csv(
                    "registro_empleados.csv",
                    index=False
                )

                st.success(
                    "✔ Operario agregado correctamente."
                )

                st.rerun()

    # ==================================================
    # COLUMNA 2 - MOVIMIENTOS DE CUENTA
    # ==================================================

    with emp_col2:

        st.subheader(
            "2. Cargar Movimiento de Cuenta"
        )

        tipo_carga = st.radio(
           "Tipo de carga:",
        [
            "🕐 Jornada por día",
            "📋 Liquidación por horas totales",
            "🌾 Pago por hectárea"
        ],
        horizontal=True
        )

        # ==================================================
        # JORNADA POR DÍA
        # ==================================================

        if tipo_carga == "🕐 Jornada por día":

            with st.form(
                "form_pago_empleado_diario"
            ):

                if not df_empleados.empty:

                    emp_seleccionado = st.selectbox(
                        "Seleccionar Operario",
                        df_empleados["Nombre"].tolist()
                    )

                    tipo_registro = st.radio(
                        "Tipo:",
                        [
                            "Liquidación / Pago",
                            "Reintegro / Devolución"
                        ]
                    )

                    st.markdown(
                        "### 🕐 Jornada trabajada"
                    )

                    p_fecha_trabajo = st.date_input(
                        "📅 Día trabajado",
                        value=datetime.datetime.today()
                    )

                    col_hora1, col_hora2 = st.columns(2)

                    with col_hora1:

                        p_hora_entrada = st.time_input(
                            "🟢 Hora de entrada"
                        )

                    with col_hora2:

                        p_hora_salida = st.time_input(
                            "🔴 Hora de salida"
                        )

                    p_valor_hora = st.number_input(
                        "💰 Valor por hora ($ ARS)",
                        min_value=0.0,
                        step=100.0,
                        value=0.0
                    )

                    entrada_minutos = (
                        p_hora_entrada.hour * 60
                        + p_hora_entrada.minute
                    )

                    salida_minutos = (
                        p_hora_salida.hour * 60
                        + p_hora_salida.minute
                    )

                    if salida_minutos >= entrada_minutos:

                        minutos_trabajados = (
                            salida_minutos
                            - entrada_minutos
                        )

                    else:

                        minutos_trabajados = (
                            (24 * 60 - entrada_minutos)
                            + salida_minutos
                        )

                    horas_trabajadas = (
                        minutos_trabajados / 60
                    )

                    monto_calculado = (
                        horas_trabajadas
                        * p_valor_hora
                    )

                    st.info(
                        f"⏱️ Horas trabajadas: "
                        f"**{horas_trabajadas:.2f} h**\n\n"
                        f"💰 Total calculado: "
                        f"**$ {monto_calculado:,.2f}**"
                    )

                    p_estado = st.radio(
                        "Estado:",
                        [
                            "Pagado",
                            "Pendiente"
                        ],
                        horizontal=True
                    )

                    p_concepto = st.text_input(
                        "Detalle",
                        value="Jornada trabajada"
                    )

                    p_comprobante = st.file_uploader(
                        "📎 Comprobante de pago (opcional)",
                        type=[
                            "pdf",
                            "png",
                            "jpg",
                            "jpeg",
                            "webp"
                        ]
                    )

                    btn_pago_emp = st.form_submit_button(
                        "💳 Guardar Movimiento"
                    )

                    if btn_pago_emp:

                        if p_valor_hora <= 0:

                            st.error(
                                "❌ Tenés que ingresar "
                                "un valor por hora."
                            )

                        elif minutos_trabajados <= 0:

                            st.error(
                                "❌ La hora de salida debe "
                                "ser posterior a la entrada."
                            )

                        else:

                            nuevo_id = str(
                                int(
                                    datetime.datetime.now().timestamp()
                                    * 1000
                                )
                            )

                            nombre_comprobante = ""

                            if p_comprobante is not None:

                                carpeta = (
                                    "comprobantes_pagos"
                                )

                                os.makedirs(
                                    carpeta,
                                    exist_ok=True
                                )

                                extension = os.path.splitext(
                                    p_comprobante.name
                                )[1]

                                nombre_comprobante = (
                                    f"{nuevo_id}{extension}"
                                )

                                ruta_comprobante = os.path.join(
                                    carpeta,
                                    nombre_comprobante
                                )

                                with open(
                                    ruta_comprobante,
                                    "wb"
                                ) as archivo:

                                    archivo.write(
                                        p_comprobante.getbuffer()
                                    )

                            nuevo_pago = {

                                "ID_Pago": nuevo_id,

                                "Fecha Pago":
                                    datetime.datetime.now().strftime(
                                        "%Y-%m-%d"
                                    ),

                                "Nombre Empleado":
                                    emp_seleccionado,

                                "Fecha Trabajo":
                                    p_fecha_trabajo.strftime(
                                        "%Y-%m-%d"
                                    ),

                                "Hora Entrada":
                                    p_hora_entrada.strftime(
                                        "%H:%M"
                                    ),

                                "Hora Salida":
                                    p_hora_salida.strftime(
                                        "%H:%M"
                                    ),

                                "Horas Trabajadas":
                                    round(
                                        horas_trabajadas,
                                        2
                                    ),

                                "Valor Hora":
                                    round(
                                        p_valor_hora,
                                        2
                                    ),

                                "Monto (ARS)":
                                    round(
                                        monto_calculado,
                                        2
                                    ),

                                "Tipo Registro":
                                    tipo_registro,

                                "Estado Pago":
                                    p_estado,

                                "Concepto":
                                    p_concepto
                            }

                            if nombre_comprobante:

                                nuevo_pago["Concepto"] += (
                                    f" | Comprobante: "
                                    f"{nombre_comprobante}"
                                )

                            df_pagos_empleados = pd.concat(
                                [
                                    df_pagos_empleados,
                                    pd.DataFrame([nuevo_pago])
                                ],
                                ignore_index=True
                            )
                            
                            guardar_pago_en_neon(nuevo_pago)

                            df_pagos_empleados.to_csv(
                             ARCHIVO_PAGOS_EMPLEADOS,
                             index=False,
                             encoding="utf-8-sig"
                            )

                            st.success(
                                "✔ Movimiento registrado "
                                "correctamente."
                            )

                            st.rerun()

                else:

                    st.warning(
                        "No hay operarios registrados."
                    )

                                                # ==================================================
                # PAGO POR HECTÁREA
                # ==================================================

        elif tipo_carga == "🌾 Pago por hectárea":

                    st.markdown(
                        "### 🌾 Pago por hectárea"
                    )

                    st.info(
                        "Cargá una campaña y las hectáreas trabajadas. "
                        "El total se calcula automáticamente."
                    )

                    # ==========================================
                    # CAMPAÑA Y LOTE
                    # ==========================================

                    col1, col2 = st.columns(2)

                    with col1:

                        campaña_hectareas = st.text_input(
                            "🌾 Campaña",
                            placeholder="Ej: Campaña 2026/27",
                            key="campaña_pago_hectareas"
                        )

                    with col2:

                        lote_hectareas = st.text_input(
                            "📍 Lote",
                            placeholder="Ej: Lote 12",
                            key="lote_pago_hectareas"
                        )

                    # ==========================================
                    # FECHA
                    # ==========================================

                    usar_rango_fechas = st.checkbox(
                        "📅 Usar rango de fechas",
                        value=False,
                        key="usar_rango_fechas_hectareas"
                    )

                    if usar_rango_fechas:

                        col1, col2 = st.columns(2)

                        with col1:

                            fecha_desde_hectareas = st.date_input(
                                "📅 Fecha desde",
                                value=datetime.date.today(),
                                key="fecha_desde_pago_hectareas"
                            )

                        with col2:

                            fecha_hasta_hectareas = st.date_input(
                                "📅 Fecha hasta",
                                value=datetime.date.today(),
                                key="fecha_hasta_pago_hectareas"
                            )

                        fecha_pago_hectareas = fecha_desde_hectareas

                    else:

                        fecha_pago_hectareas = st.date_input(
                            "📅 Fecha",
                            value=datetime.date.today(),
                            key="fecha_pago_hectareas"
                        )

                        fecha_desde_hectareas = fecha_pago_hectareas
                        fecha_hasta_hectareas = fecha_pago_hectareas

                                        # ==========================================
                    # HECTÁREAS, VALOR Y PORCENTAJE
                    # ==========================================

                    col1, col2, col3 = st.columns(3)

                    with col1:

                        hectareas_trabajadas = st.number_input(
                            "🌱 Hectáreas trabajadas",
                            min_value=0.0,
                            step=0.1,
                            value=0.0,
                            key="hectareas_trabajadas"
                        )

                    with col2:

                        valor_hectarea = st.number_input(
                            "💰 Valor por hectárea ($ ARS)",
                            min_value=0.0,
                            step=100.0,
                            value=0.0,
                            key="valor_hectarea_pago"
                        )

                    with col3:

                        porcentaje_hectarea = st.number_input(
                            "📊 Porcentaje a cobrar (%)",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.5,
                            value=5.0,
                            key="porcentaje_hectarea_pago"
                        )

                    # ==========================================
                    # CÁLCULO AUTOMÁTICO
                    # ==========================================

                    ganancia_total_hectareas = (
                        hectareas_trabajadas
                        * valor_hectarea
                    )

                    total_pagar_hectareas = (
                        ganancia_total_hectareas
                        * porcentaje_hectarea
                        / 100
                    )

                    col1, col2 = st.columns(2)

                    with col1:

                        st.metric(
                            "💵 Ganancia total",
                            f"$ {ganancia_total_hectareas:,.2f}"
                        )

                    with col2:

                        st.metric(
                            "💰 Total a pagar",
                            f"$ {total_pagar_hectareas:,.2f}"
                        )
                    # ==========================================
                    # ESTADO
                    # ==========================================

                    estado_pago_hectareas = st.selectbox(
                        "📌 Estado del pago",
                        [
                            "Pagado",
                            "Pendiente",
                            "Pago parcial"
                        ],
                        key="estado_pago_hectareas"
                    )

                    # ==========================================
                    # COMPROBANTE
                    # ==========================================

                    comprobantes_hectareas = st.file_uploader(
                     "📎 Comprobantes de pago (opcional)",
                     type=[
                          "pdf",
                          "png",
                          "jpg",
                          "jpeg",
                          "webp"
                        ],
                        accept_multiple_files=True,
                        key="comprobantes_pago_hectareas"
                        )

                    # ==========================================
                    # RESUMEN
                    # ==========================================

                    st.markdown("### 📋 Resumen")

                    st.write(
                        f"**Campaña:** "
                        f"{campaña_hectareas or '-'}"
                    )

                    st.write(
                        f"**Lote:** "
                        f"{lote_hectareas or '-'}"
                    )

                    if usar_rango_fechas:

                        st.write(
                            f"**Período:** "
                            f"{fecha_desde_hectareas.strftime('%d/%m/%Y')} "
                            f"al "
                            f"{fecha_hasta_hectareas.strftime('%d/%m/%Y')}"
                        )

                    else:

                        st.write(
                            f"**Fecha:** "
                            f"{fecha_pago_hectareas.strftime('%d/%m/%Y')}"
                        )

                    st.write(
                        f"**Hectáreas:** "
                        f"{hectareas_trabajadas:,.2f} ha"
                    )

                    st.write(
                        f"**Valor por hectárea:** "
                        f"$ {valor_hectarea:,.2f}"
                    )

                    st.write(
                        f"**Total a pagar:** "
                        f"**$ {total_pagar_hectareas:,.2f}**"
                    )

                    # ==========================================
                    # GUARDAR
                    # ==========================================

                    guardar_pago_hectareas = st.button(
                        "💾 Guardar pago por hectárea",
                        use_container_width=True,
                        key="btn_guardar_pago_hectareas"
                    )

                    if guardar_pago_hectareas:

                        # ======================================
                        # VALIDACIONES
                        # ======================================

                        if not campaña_hectareas.strip():

                            st.error(
                                "❌ Tenés que ingresar la campaña."
                            )
                            st.stop()

                        if not lote_hectareas.strip():

                            st.error(
                                "❌ Tenés que ingresar el lote."
                            )
                            st.stop()

                        if hectareas_trabajadas <= 0:

                            st.error(
                                "❌ Tenés que ingresar las hectáreas trabajadas."
                            )
                            st.stop()

                        if valor_hectarea <= 0:

                            st.error(
                                "❌ Tenés que ingresar el valor por hectárea."
                            )
                            st.stop()

                        if (
                            usar_rango_fechas
                            and fecha_hasta_hectareas
                            < fecha_desde_hectareas
                        ):

                            st.error(
                                "❌ La fecha hasta no puede ser anterior "
                                "a la fecha desde."
                            )
                            st.stop()

                        # ======================================
                        # GENERAR ID
                        # ======================================

                        if df_pagos_empleados.empty:

                            nuevo_id_hectareas = 1

                        else:

                            ids_hectareas = pd.to_numeric(
                                df_pagos_empleados["ID_Pago"],
                                errors="coerce"
                            ).dropna()

                            if ids_hectareas.empty:

                                nuevo_id_hectareas = 1

                            else:

                                nuevo_id_hectareas = (
                                    int(ids_hectareas.max()) + 1
                                )

                                                # ======================================
                        # GUARDAR COMPROBANTES
                        # ======================================

                        nombres_comprobantes_hectareas = []

                        if comprobantes_hectareas:

                            carpeta_comprobantes = (
                                "comprobantes_pagos"
                            )

                            os.makedirs(
                                carpeta_comprobantes,
                                exist_ok=True
                            )

                            for numero, comprobante in enumerate(
                                comprobantes_hectareas,
                                start=1
                            ):

                                extension = os.path.splitext(
                                    comprobante.name
                                )[1]

                                nombre_comprobante = (
                                    f"hectareas_"
                                    f"{nuevo_id_hectareas}_"
                                    f"{numero}"
                                    f"{extension}"
                                )

                                ruta_comprobante = os.path.join(
                                    carpeta_comprobantes,
                                    nombre_comprobante
                                )

                                with open(
                                    ruta_comprobante,
                                    "wb"
                                ) as archivo:

                                    archivo.write(
                                        comprobante.getbuffer()
                                    )

                                nombres_comprobantes_hectareas.append(
                                    nombre_comprobante
                                )
                        # ======================================
                        # FECHAS PARA GUARDAR
                        # ======================================

                        if usar_rango_fechas:

                            fecha_trabajo_guardada = (
                                f"{fecha_desde_hectareas}"
                                f" al "
                                f"{fecha_hasta_hectareas}"
                            )

                        else:

                            fecha_trabajo_guardada = str(
                                fecha_pago_hectareas
                            )

                        # ======================================
                        # NUEVO MOVIMIENTO
                        # ======================================

                        nuevo_pago_hectareas = {

                            "ID_Pago":
                                str(nuevo_id_hectareas),

                            "Fecha Pago":
                                str(
                                    datetime.date.today()
                                ),

                            "Nombre Empleado":
                                "Pago general por hectárea",

                            "Fecha Trabajo":
                                fecha_trabajo_guardada,

                            "Hora Entrada":
                                "",

                            "Hora Salida":
                                "",

                            "Horas Trabajadas":
                                0.0,

                            "Valor Hora":
                                0.0,

                            "Monto (ARS)":
                                round(
                                    total_pagar_hectareas,
                                    2
                                ),

                            "Tipo Registro":
                                "Pago por hectárea",

                            "Estado Pago":
                                estado_pago_hectareas,

                            "Concepto":
                            (
                              f"Campaña: "
                              f"{campaña_hectareas.strip()} "
                              f"| Lote: "
                              f"{lote_hectareas.strip()} "
                              f"| "
                              f"{hectareas_trabajadas:,.2f} ha "
                              f"x $ "
                              f"{valor_hectarea:,.2f}/ha "
                              f"| "
                              f"{porcentaje_hectarea:,.2f}%"
                            ),
                            "Porcentaje Bonificacion":
                                0.0,

                            "Monto Bonificacion (ARS)":
                                0.0,

                            "Porcentaje Descuento":
                                0.0,

                            "Monto Descuento (ARS)":
                                0.0,

                            "Monto Trabajado (ARS)":
                                round(
                                    total_pagar_hectareas,
                                    2
                                ),

                            "Monto Pagado (ARS)":
                                (
                                    round(
                                        total_pagar_hectareas,
                                        2
                                    )
                                    if estado_pago_hectareas
                                    == "Pagado"
                                    else 0.0
                                ),

                            "Monto Final Trabajo (ARS)":
                                round(
                                    total_pagar_hectareas,
                                    2
                                ),

                            "Adelanto Generado (ARS)":
                                0.0,

                            "Monto Compensado (ARS)":
                                0.0,

                            "Saldo Adelanto (ARS)":
                                0.0,

                            "Saldo Pendiente Pago (ARS)":
                                (
                                    round(
                                        total_pagar_hectareas,
                                        2
                                    )
                                    if estado_pago_hectareas
                                    != "Pagado"
                                    else 0.0
                                ),

                            "Comprobantes":
                             ", ".join(nombres_comprobantes_hectareas),

                            "PDF Liquidacion":
                                ""
                        }

                        # ======================================
                        # GUARDAR EN TABLA
                        # ======================================

                        df_pagos_empleados = pd.concat(
                            [
                                df_pagos_empleados,
                                pd.DataFrame(
                                    [nuevo_pago_hectareas]
                                )
                            ],
                            ignore_index=True
                        )

                        guardar_pago_en_neon(nuevo_pago_hectareas)

                        df_pagos_empleados.to_csv(
                            ARCHIVO_PAGOS_EMPLEADOS,
                            index=False,
                            encoding="utf-8-sig"
                        )

                        st.success(
                            "✅ Pago por hectárea guardado correctamente."
                        )

                        if nombres_comprobantes_hectareas:

                            st.success(
                                f"✅ Se guardaron "
                                f"{len(nombres_comprobantes_hectareas)} "
                                f"comprobante(s) correctamente."
                            )

                            st.markdown(
                                "### 📎 Comprobantes guardados"
                            )

                            for indice, nombre_archivo in enumerate(
                                nombres_comprobantes_hectareas,
                                start=1
                            ):

                                st.write(
                                    f"📎 Comprobante {indice}: "
                                    f"`{str(nombre_archivo)}`"
                                )
                                
        # ==================================================
        # LIQUIDACIÓN ESPECIAL POR HORAS TOTALES
        # ==================================================

        else:

                    st.markdown(
                        "### 📋 Liquidación por horas totales"
                    )

                    st.info(
                        "Esta modalidad permite liquidar varias horas juntas, "
                        "aplicando bonificaciones, descuentos, adelantos y saldos."
                    )

                    if not df_empleados.empty:

                        # ==========================================
                        # EMPLEADO
                        # ==========================================

                        emp_liquidacion = st.selectbox(
                            "👤 Empleado",
                            df_empleados["Nombre"].tolist(),
                            key="empleado_liquidacion_especial"
                        )
                        # Detectar cambio de empleado
                        empleado_actual = emp_liquidacion

                        if "empleado_liquidacion_anterior" not in st.session_state:
                          st.session_state["empleado_liquidacion_anterior"] = empleado_actual

                        elif st.session_state["empleado_liquidacion_anterior"] != empleado_actual:
                         st.session_state["empleado_liquidacion_anterior"] = empleado_actual

                         # Limpiar los valores anteriores
                         for clave in [
                         "horas_totales_liquidacion",
                         "valor_hora_total_liquidacion",
                         "porcentaje_bonificacion_liquidacion",
                         "porcentaje_descuento_liquidacion",
                         "monto_pagado_liquidacion"
                        ]:
                          if clave in st.session_state:
                             del st.session_state[clave]
                        # ==========================================
                        # FECHA
                        # ==========================================

                        fecha_liquidacion = st.date_input(
                            "📅 Fecha de liquidación",
                            value=datetime.date.today(),
                            key="fecha_liquidacion_especial"
                        )

                        # ==========================================
                        # HORAS Y VALOR HORA
                        # ==========================================

                        col1, col2 = st.columns(2)

                        with col1:

                            horas_totales = st.number_input(
                                "⏱️ Horas totales trabajadas",
                                min_value=0.0,
                                step=0.5,
                                value=0.0,
                                key="horas_totales_liquidacion"
                            )

                        with col2:

                            valor_hora_total = st.number_input(
                                "💰 Valor por hora",
                                min_value=0.0,
                                step=100.0,
                                value=0.0,
                                key="valor_hora_total_liquidacion"
                            )

                        # ==========================================
                        # MONTO BASE
                        # ==========================================

                        monto_base_trabajado = (
                            horas_totales * valor_hora_total
                        )

                        st.metric(
                            "💵 Monto trabajado",
                            f"$ {monto_base_trabajado:,.2f}"
                        )

                        # ==========================================
                        # BONIFICACIÓN
                        # ==========================================

                        st.markdown("#### ➕ Bonificación")

                        porcentaje_bonificacion = st.number_input(
                            "Bonificación (%)",
                            min_value=0.0,
                            max_value=100.0,
                            step=1.0,
                            value=0.0,
                            key="porcentaje_bonificacion_liquidacion"
                        )

                        monto_bonificacion = (
                            monto_base_trabajado
                            * porcentaje_bonificacion
                            / 100
                        )

                        st.write(
                            f"Bonificación: "
                            f"**$ {monto_bonificacion:,.2f}**"
                        )

                        # ==========================================
                        # DESCUENTO
                        # ==========================================

                        st.markdown("#### ➖ Descuento")

                        porcentaje_descuento = st.number_input(
                            "Descuento (%)",
                            min_value=-100.0,
                            max_value=100.0,
                            step=1.0,
                            value=0.0,
                            key="porcentaje_descuento_liquidacion"
                        )

                        monto_descuento = (
                            monto_base_trabajado
                            * porcentaje_descuento
                            / -100
                        )

                        st.write(
                            f"Descuento: "
                            f"**$ {monto_descuento:,.2f}**"
                        )

                        # ==========================================
                        # TOTAL FINAL DEL TRABAJO
                        # ==========================================

                        monto_final_trabajo = (
                            monto_base_trabajado
                            + monto_bonificacion
                            - monto_descuento
                        )

                        st.metric(
                            "💰 Total final del trabajo",
                            f"$ {monto_final_trabajo:,.2f}"
                        )

                        # ==========================================
                        # SALDOS ANTERIORES
                        # ==========================================

                        saldos = obtener_saldos_empleado(
                            df_pagos_empleados,
                            emp_liquidacion
                        )

                        saldo_adelanto_anterior = float(
                            saldos["adelanto"]
                        )

                        saldo_pendiente_anterior = float(
                            saldos["pendiente"]
                        )

                        st.markdown(
                            "#### 📊 Saldos anteriores"
                        )

                        col1, col2 = st.columns(2)

                        with col1:

                            st.metric(
                                "Adelanto pendiente",
                                f"$ {saldo_adelanto_anterior:,.2f}"
                            )

                        with col2:

                            st.metric(
                                "Pago pendiente",
                                f"$ {saldo_pendiente_anterior:,.2f}"
                            )

                        # ==========================================
                        # TOTAL ADEUDADO
                        # ==========================================

                        total_debido = (
                            saldo_pendiente_anterior
                            + monto_final_trabajo
                        )

                        # ==========================================
                        # COMPENSAR ADELANTO
                        # ==========================================

                        monto_compensado = min(
                            saldo_adelanto_anterior,
                            total_debido
                        )

                        monto_neto_a_pagar = (
                            total_debido
                            - monto_compensado
                        )

                        st.markdown(
                            "#### 🧮 Compensación"
                        )

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            st.metric(
                                "Total adeudado",
                                f"$ {total_debido:,.2f}"
                            )

                        with col2:

                            st.metric(
                                "Adelanto compensado",
                                f"$ {monto_compensado:,.2f}"
                            )

                        with col3:

                            st.metric(
                                "Neto a pagar",
                                f"$ {monto_neto_a_pagar:,.2f}"
                            )

                        # ==========================================
                        # MONTO REALMENTE PAGADO
                        # ==========================================

                        st.markdown(
                            "#### 💵 Pago realizado"
                        )

                        monto_pagado = st.number_input(
                            "💵 Monto realmente pagado",
                            min_value=0.0,
                            step=100.0,
                            value=0.0,
                            key="monto_pagado_liquidacion"
                        )

                        # ==========================================
                        # DIFERENCIA
                        # ==========================================

                        diferencia_pago = (
                            monto_pagado
                            - monto_neto_a_pagar
                        )

                        if diferencia_pago < 0:

                            saldo_pendiente_nuevo = abs(
                                diferencia_pago
                            )

                            adelanto_nuevo = 0.0

                        elif diferencia_pago > 0:

                            saldo_pendiente_nuevo = 0.0

                            adelanto_nuevo = (
                                diferencia_pago
                            )

                        else:

                            saldo_pendiente_nuevo = 0.0

                            adelanto_nuevo = 0.0

                        # ==========================================
                        # SALDO FINAL ADELANTO
                        # ==========================================

                        saldo_adelanto_final = (
                            saldo_adelanto_anterior
                            - monto_compensado
                            + adelanto_nuevo
                        )

                        saldo_adelanto_final = max(
                            saldo_adelanto_final,
                            0.0
                        )

                        # ==========================================
                        # RESULTADO
                        # ==========================================

                        st.markdown(
                            "#### 📌 Resultado de la liquidación"
                        )

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            st.metric(
                                "Adelanto final",
                                f"$ {saldo_adelanto_final:,.2f}"
                            )

                        with col2:

                            st.metric(
                                "Pendiente de pago",
                                f"$ {saldo_pendiente_nuevo:,.2f}"
                            )

                        with col3:

                            st.metric(
                                "Realmente pagado",
                                f"$ {monto_pagado:,.2f}"
                            )

                        # ==========================================
                        # ESTADO Y CONCEPTO
                        # ==========================================

                        col1, col2 = st.columns(2)

                        with col1:

                            estado_liquidacion = st.selectbox(
                                "📌 Estado",
                                [
                                    "Pagado",
                                    "Pago parcial",
                                    "Pendiente"
                                ],
                                key="estado_liquidacion_especial"
                            )

                        with col2:

                            concepto_liquidacion = st.text_input(
                                "📝 Concepto",
                                value="Liquidación por horas totales",
                                key="concepto_liquidacion_especial"
                            )

                        # ==========================================
                        # COMPROBANTES
                        # ==========================================

                        archivos_comprobantes = st.file_uploader(
                            "📎 Comprobantes",
                            accept_multiple_files=True,
                            type=[
                                "pdf",
                                "png",
                                "jpg",
                                "jpeg",
                                "webp"
                            ],
                            key="comprobantes_liquidacion_especial"
                        )

                        # ==========================================
                        # RESUMEN
                        # ==========================================

                        st.markdown("### 📋 Resumen")

                        st.write(
                            f"**Empleado:** {emp_liquidacion}"
                        )

                        st.write(
                            f"**Horas:** {horas_totales:,.2f}"
                        )

                        st.write(
                            f"**Valor hora:** "
                            f"$ {valor_hora_total:,.2f}"
                        )

                        st.write(
                            f"**Monto trabajado:** "
                            f"$ {monto_base_trabajado:,.2f}"
                        )

                        st.write(
                            f"**Bonificación:** "
                            f"$ {monto_bonificacion:,.2f}"
                        )

                        st.write(
                            f"**Descuento:** "
                            f"$ {monto_descuento:,.2f}"
                        )

                        st.write(
                            f"**Total final trabajo:** "
                            f"$ {monto_final_trabajo:,.2f}"
                        )

                        st.write(
                            f"**Adelanto compensado:** "
                            f"$ {monto_compensado:,.2f}"
                        )

                        st.write(
                            f"**Neto a pagar:** "
                            f"$ {monto_neto_a_pagar:,.2f}"
                        )

                        st.write(
                            f"**Monto realmente pagado:** "
                            f"$ {monto_pagado:,.2f}"
                        )

                        st.write(
                            f"**Adelanto final:** "
                            f"$ {saldo_adelanto_final:,.2f}"
                        )

                        st.write(
                            f"**Pendiente de pago:** "
                            f"$ {saldo_pendiente_nuevo:,.2f}"
                        )

                                                # ==========================================
                        # GUARDAR LIQUIDACIÓN
                        # ==========================================

                        guardar_liquidacion = st.button(
                            "💾 Guardar liquidación",
                            use_container_width=True,
                            key="btn_guardar_liquidacion_especial"
                        )

                        if guardar_liquidacion:

                            # ======================================
                            # VALIDACIONES
                            # ======================================

                            if horas_totales <= 0:
                                st.error(
                                    "❌ Tenés que ingresar las horas trabajadas."
                                )
                                st.stop()

                            if valor_hora_total <= 0:
                                st.error(
                                    "❌ Tenés que ingresar el valor por hora."
                                )
                                st.stop()

                            # ======================================
                            # GENERAR ID
                            # ======================================

                            if df_pagos_empleados.empty:

                                nuevo_id = 1

                            else:

                                ids = pd.to_numeric(
                                    df_pagos_empleados["ID_Pago"],
                                    errors="coerce"
                                )

                                ids = ids.dropna()

                                if ids.empty:
                                    nuevo_id = 1
                                else:
                                    nuevo_id = int(ids.max()) + 1

                            # ======================================
                            # COMPROBANTES
                            # ======================================

                            nombres_comprobantes = guardar_comprobantes(
                                archivos_comprobantes,
                                nuevo_id
                            )
                            st.write("DEBUG - ID:", nuevo_id)
                            st.write("DEBUG - Archivos recibidos:", archivos_comprobantes)
                            st.write("DEBUG - Nombres guardados:", nombres_comprobantes)
                            st.write(
                             "DEBUG - Carpeta existe:",
                             os.path.exists("comprobantes_pagos")
                            )

                            if os.path.exists("comprobantes_pagos"):
                                st.write(
                                 "DEBUG - Archivos en carpeta:",
                                 os.listdir("comprobantes_pagos")
                            )
                            
                            # ======================================
                            # GENERAR PDF
                            # ======================================

                            pdf_bytes = generar_pdf_liquidacion(
                                nuevo_id=nuevo_id,
                                empleado=emp_liquidacion,
                                fecha=fecha_liquidacion,
                                horas=horas_totales,
                                valor_hora=valor_hora_total,
                                monto_trabajado=monto_base_trabajado,
                                bonificacion=monto_bonificacion,
                                descuento=monto_descuento,
                                monto_final=monto_final_trabajo,
                                adelanto_anterior=saldo_adelanto_anterior,
                                pendiente_anterior=saldo_pendiente_anterior,
                                compensado=monto_compensado,
                                neto_pagar=monto_neto_a_pagar,
                                monto_pagado=monto_pagado,
                                adelanto_final=saldo_adelanto_final,
                                pendiente_final=saldo_pendiente_nuevo,
                                concepto=concepto_liquidacion
                            )

                            nombre_pdf = (
                                f"liquidacion_{nuevo_id}.pdf"
                            )

                            # ======================================
                            # GUARDAR PDF EN CARPETA
                            # ======================================

                            carpeta_pdfs = "liquidaciones_pdf"

                            os.makedirs(
                                carpeta_pdfs,
                                exist_ok=True
                            )

                            ruta_pdf = os.path.join(
                                carpeta_pdfs,
                                nombre_pdf
                            )

                            with open(
                                ruta_pdf,
                                "wb"
                            ) as archivo_pdf:

                                archivo_pdf.write(pdf_bytes)

                            # ======================================
                            # NUEVO MOVIMIENTO
                            # ======================================

                            nuevo_pago = {

                                "ID_Pago":
                                    str(nuevo_id),

                                "Fecha Pago":
                                    str(fecha_liquidacion),

                                "Nombre Empleado":
                                    emp_liquidacion,

                                "Fecha Trabajo":
                                    str(fecha_liquidacion),

                                "Hora Entrada":
                                    "",

                                "Hora Salida":
                                    "",

                                "Horas Trabajadas":
                                    round(
                                        horas_totales,
                                        2
                                    ),

                                "Valor Hora":
                                    round(
                                        valor_hora_total,
                                        2
                                    ),

                                # IMPORTANTE:
                                # ESTE ES EL MONTO QUE
                                # REALMENTE INGRESÓ EL USUARIO
                                "Monto (ARS)":
                                    round(
                                        monto_pagado,
                                        2
                                    ),

                                "Tipo Registro":
                                    "Liquidación / Pago",

                                "Estado Pago":
                                    estado_liquidacion,

                                "Concepto":
                                    concepto_liquidacion,

                                "Porcentaje Bonificacion":
                                    round(
                                        porcentaje_bonificacion,
                                        2
                                    ),

                                "Monto Bonificacion (ARS)":
                                    round(
                                        monto_bonificacion,
                                        2
                                    ),

                                "Porcentaje Descuento":
                                    round(
                                        porcentaje_descuento,
                                        2
                                    ),

                                "Monto Descuento (ARS)":
                                    round(
                                        monto_descuento,
                                        2
                                    ),

                                "Monto Trabajado (ARS)":
                                    round(
                                        monto_base_trabajado,
                                        2
                                    ),

                                "Monto Pagado (ARS)":
                                    round(
                                        monto_pagado,
                                        2
                                    ),

                                "Monto Final Trabajo (ARS)":
                                    round(
                                        monto_final_trabajo,
                                        2
                                    ),

                                "Adelanto Generado (ARS)":
                                    round(
                                        adelanto_nuevo,
                                        2
                                    ),

                                "Monto Compensado (ARS)":
                                    round(
                                        monto_compensado,
                                        2
                                    ),

                                "Saldo Adelanto (ARS)":
                                    round(
                                        saldo_adelanto_final,
                                        2
                                    ),

                                "Saldo Pendiente Pago (ARS)":
                                    round(
                                        saldo_pendiente_nuevo,
                                        2
                                    ),

                                "Comprobantes":
                                    ", ".join(
                                        str(x)
                                        for x in nombres_comprobantes
                                    ),

                                "PDF Liquidacion":
                                    nombre_pdf
                            }

                            # ======================================
                            # AGREGAR A LA TABLA
                            # ======================================

                            df_pagos_empleados = pd.concat(
                                [
                                    df_pagos_empleados,
                                    pd.DataFrame([nuevo_pago])
                                ],
                                ignore_index=True
                            )

                            guardar_pago_en_neon(nuevo_pago)

                            # ======================================
                            # GUARDAR CSV
                            # ======================================

                            df_pagos_empleados.to_csv(
                                ARCHIVO_PAGOS_EMPLEADOS,
                                index=False,
                                encoding="utf-8-sig"
                            )

                            # ======================================
                            # GUARDAR ID PARA MOSTRAR CONFIRMACIÓN
                            # ======================================

                            st.session_state[
                                "ultima_liquidacion_guardada"
                            ] = nuevo_id

                            st.session_state[
                                "ultimo_pdf_liquidacion"
                            ] = pdf_bytes

                            st.session_state[
                                "ultimo_nombre_pdf"
                            ] = nombre_pdf

                            st.success(
                                f"✅ Liquidación #{nuevo_id} "
                                f"guardada correctamente."
                            )
                            st.success(
                                f"✅ Liquidación #{nuevo_id} "
                                f"guardada correctamente."
                            )

                            # ======================================
                            # MOSTRAR COMPROBANTES RECIÉN GUARDADOS
                            # ======================================

                            if nombres_comprobantes:

                                st.markdown(
                                    "### 📎 Comprobante de la liquidación"
                                )

                                for nombre_comprobante in nombres_comprobantes:

                                    ruta_comprobante = os.path.join(
                                        "comprobantes_pagos",
                                        nombre_comprobante
                                    )

                                    if os.path.isfile(
                                        ruta_comprobante
                                    ):

                                        with open(
                                            ruta_comprobante,
                                            "rb"
                                        ) as archivo:

                                            datos_comprobante = (
                                                archivo.read()
                                            )

                                        st.download_button(
                                            label=(
                                                "📎 Ver / descargar "
                                                f"{nombre_comprobante}"
                                            ),
                                            data=datos_comprobante,
                                            file_name=(
                                                nombre_comprobante
                                            ),
                                            key=(
                                                f"comprobante_guardado_"
                                                f"{nuevo_id}_"
                                                f"{nombre_comprobante}"
                                            ),
                                            use_container_width=True
                                        )

                                    else:

                                        st.error(
                                            f"❌ El comprobante "
                                            f"{nombre_comprobante} "
                                            f"no se encuentra en la carpeta."
                                        )
# ----------------------------------------------------
# PESTAÑA: RENDICIÓN POR OPERARIO
# ----------------------------------------------------

if menu == "📋 RENDICIÓN POR OPERARIO":

    st.header("📋 Historial de Cuenta por Operario")

    # ==========================================
    # FILTRO DE PRIVACIDAD
    # ==========================================

    # Un operario solamente puede ver su propia cuenta.
    # Dueño, Administrador, Encargado y Contador
    # pueden seleccionar cualquier operario.

    if tiene_rol("Operario") and not tiene_rol(
        "Dueño",
        "Administrador",
        "Encargado",
        "Contador"
    ):

        lista_para_filtrar = [nombre_actual]

        st.info(
            f"👤 Visualizando la cuenta de: **{nombre_actual}**"
        )

    else:

        lista_para_filtrar = (
            df_empleados["Nombre"].tolist()
            if not df_empleados.empty
            else ["No hay personal registrado"]
        )

    # ==========================================
    # SELECCIONAR OPERARIO
    # ==========================================

    op_filtro = st.selectbox(
        "Seleccionar Operario para revisar:",
        lista_para_filtrar
    )

    # ==========================================
    # FILTRAR MOVIMIENTOS
    # ==========================================

    if not df_pagos_empleados.empty:

        df_op = df_pagos_empleados[
            df_pagos_empleados["Nombre Empleado"] == op_filtro
        ]

    else:

        df_op = pd.DataFrame()

    # ==========================================
    # COLUMNAS
    # ==========================================

    col_r1, col_r2 = st.columns(2)

    # ==========================================
    # LIQUIDACIONES Y PAGOS
    # ==========================================

    with col_r1:

        st.markdown(
            "### 💰 LIQUIDACIONES Y PAGOS EN EFECTIVO"
        )

        if not df_op.empty:

            df_pagos = df_op[
                df_op["Tipo Registro"] == "Liquidación / Pago"
            ]

            if not df_pagos.empty:

                st.dataframe(
             df_pagos[
            [
             "Fecha Trabajo",
             "Hora Entrada",
             "Hora Salida",
             "Horas Trabajadas",
             "Valor Hora",
             "Monto Trabajado (ARS)",
             "Porcentaje Bonificacion",
             "Monto Bonificacion (ARS)",
             "Porcentaje Descuento",
             "Monto Descuento (ARS)",
             "Monto Final Trabajo (ARS)",
             "Monto Pagado (ARS)",
             "Adelanto Generado (ARS)",
             "Monto Compensado (ARS)",
             "Saldo Adelanto (ARS)",
             "Saldo Pendiente Pago (ARS)",
             "Estado Pago",
             "Concepto"
            ]
        ],
         use_container_width=True,
         hide_index=True
        )
                # Total de pagos
                total_pagos = df_pagos[
                    "Monto (ARS)"
                ].sum()

                st.metric(
                    "💰 Total Liquidaciones",
                    f"$ {total_pagos:,.2f}"
                )
                                # ==========================================
                # COMPROBANTES AUTOMÁTICOS DE LIQUIDACIÓN
                # ==========================================

                st.markdown(
                    "### 📄 Comprobantes de liquidación"
                )

                carpeta_pdfs = "liquidaciones_pdf"

                if os.path.exists(carpeta_pdfs):

                    pdfs_mostrados = False

                    for _, fila_pago in df_pagos.iterrows():

                        nombre_pdf = fila_pago.get(
                            "PDF Liquidacion",
                            ""
                        )

                        if pd.isna(nombre_pdf):
                            nombre_pdf = ""

                        nombre_pdf = str(
                            nombre_pdf
                        ).strip()

                        if not nombre_pdf:
                            continue

                        ruta_pdf = os.path.join(
                            carpeta_pdfs,
                            nombre_pdf
                        )

                        if os.path.isfile(ruta_pdf):

                            pdfs_mostrados = True

                            id_numerico = pd.to_numeric(
                                fila_pago.get(
                                    "ID_Pago",
                                    ""
                                ),
                                errors="coerce"
                            )

                            if pd.notna(id_numerico):

                                id_liquidacion = str(
                                    int(id_numerico)
                                )

                            else:

                                id_liquidacion = str(
                                    fila_pago.get(
                                        "ID_Pago",
                                        ""
                                    )
                                ).strip()

                            st.markdown(
                                f"**📋 Liquidación "
                                f"#{id_liquidacion}**"
                            )

                            with open(
                                ruta_pdf,
                                "rb"
                            ) as archivo_pdf:

                                datos_pdf = (
                                    archivo_pdf.read()
                                )

                            st.download_button(
                                label=(
                                    "📄 Ver / descargar "
                                    "comprobante de liquidación"
                                ),
                                data=datos_pdf,
                                file_name=nombre_pdf,
                                mime="application/pdf",
                                key=(
                                    "pdf_liquidacion_"
                                    f"{id_liquidacion}_"
                                    f"{nombre_pdf}"
                                ),
                                use_container_width=True
                            )

                    if not pdfs_mostrados:

                        st.info(
                            "ℹ️ No hay comprobantes de "
                            "liquidación disponibles."
                        )

                else:

                    st.info(
                        "ℹ️ Todavía no hay liquidaciones "
                        "con comprobante generado."
                    )

    # ==========================================
    # VALES Y REINTEGROS
    # ==========================================

    with col_r2:

        st.markdown(
            "### 🔧 VALES Y REINTEGROS (GASTOS A RENDIR)"
        )

        if not df_op.empty:

            df_reintegros = df_op[
                df_op["Tipo Registro"]
                == "Reintegro / Devolución"
            ]

            if not df_reintegros.empty:

                st.dataframe(
                    df_reintegros[
                        [
                            "Fecha Pago",
                            "Monto (ARS)",
                            "Estado Pago",
                            "Concepto"
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True
                )

                # Total de reintegros
                total_reintegros = df_reintegros[
                    "Monto (ARS)"
                ].sum()

                st.metric(
                    "🔧 Total Reintegros",
                    f"$ {total_reintegros:,.2f}"
                )

            else:

                st.info(
                    "No hay registros de reintegros o vales."
                )

        else:

            st.info("Sin movimientos.")
if menu == "💰 INGRESOS POR TRABAJOS":

    pantalla_ingresos()

if menu == "👥 CLIENTES":

    pantalla_clientes()
if menu == "🧾 FACTURACIÓN":

    pantalla_facturacion()

if menu == "🛠 SERVICIOS":

        pantalla_servicios()

if menu == "🌱 CAMPAÑAS AGRÍCOLAS":
    pantalla_campanas()

if menu == "🔧 MANTENIMIENTO DE MAQUINARIA":

    pantalla_mantenimiento()

if menu == "⛽ CONTROL DE COMBUSTIBLE":

    pantalla_combustible()

if menu == "📅 AGENDA Y VENCIMIENTOS":

    pantalla_agenda()

if menu == "⚙ ADMINISTRACIÓN":

    if not tiene_rol("Dueño", "Administrador"):

        st.error("No tiene permisos.")

        st.stop()

    pantalla_administracion()

if menu == "👑 PANEL DEL DUEÑO":

    if not tiene_rol("Dueño"):

        st.error("Solo acceso del dueño")

        st.stop()

    pantalla_panel_dueno()
# ----------------------------------------------------
# PESTAÑA: SEGUROS Y COBERTURAS
# ----------------------------------------------------
if menu == "🛡 SEGUROS Y COBERTURAS":
    if not tiene_rol("Dueño", "Administrador"):
        st.error("No tiene permisos.")
        st.stop()

    st.header("🛡 Control de Pólizas y Seguros")
    with st.form("form_seguros", clear_on_submit=True):
        s1, s2, s3 = st.columns(3)
        with s1:
            seg_comp = st.text_input("Compañía Aseguradora")
            seg_tipo = st.selectbox("Tipo Cobertura", ["Maquinaria Agrícola", "Granizo / Multiriesgo", "Responsabilidad Civil", "Otros"])
        with s2:
            seg_bien = st.text_input("Bien Asegurado")
            seg_venc = st.date_input("Vencimiento", value=datetime.date.today())
        with s3:
            seg_monto = st.number_input("Monto Cuota ($ ARS)", min_value=0.0)
            seg_estado = st.radio("Estado:", ["Pagado", "Pendiente"], horizontal=True)
        btn_seguro = st.form_submit_button("💾 Archivar")
        if btn_seguro and seg_comp and seg_monto > 0:
                nuevo_seg = {
                    "ID_Seguro": f"seg_{int(datetime.datetime.now().timestamp())}", "Compañía": seg_comp.strip(), "Tipo Cobertura": seg_tipo,
                    "Bien Asegurado": seg_bien.strip(), "Vencimiento": seg_venc.strftime("%Y-%m-%d"), "Monto Prima (ARS)": seg_monto, "Estado Pago": seg_estado
                }
                df_seguros = pd.concat([df_seguros, pd.DataFrame([nuevo_seg])], ignore_index=True)
                df_seguros.to_csv("registro_seguros.csv", index=False)
                st.rerun()
        if not df_seguros.empty: st.dataframe(df_seguros, use_container_width=True)

# ----------------------------------------------------
# PESTAÑA SECRETA: CONTROL DE ERRORES
# ----------------------------------------------------

if menu == "🗄 CONTROL DE ERRORES":

    if not tiene_rol("Dueño"):
        st.error("Solo el dueño puede ingresar.")
        st.stop()

    st.header("🗄 Panel exclusivo de borrado (Solo Dueño)")

    sub_g, sub_i, sub_p, sub_s = st.tabs(
        [
            "Gastos",
            "Ingresos",
            "Pagos Personal",
            "Seguros"
        ]
    )

    # ==========================================
    # GASTOS
    # ==========================================

    with sub_g:

        if not df_facturas.empty:

            for idx, fila in df_facturas.copy().iterrows():

                c_i, c_b = st.columns([6, 1])

                with c_i:

                    st.write(
                        f"📅 {fila['Fecha Registro']} | "
                        f"*{fila['Proveedor']}* | "
                        f"**$ {fila['Monto Original']:,.2f}**"
                    )

                with c_b:

                    if st.button(
                        "🗑 Borrar",
                        key=f"b_fac_{fila['ID']}_{idx}"
                    ):

                        df_facturas = df_facturas.drop(idx)

                        df_facturas.to_csv(
                            "datos_facturas.csv",
                            index=False
                        )

                        st.success("Gasto eliminado.")

                        st.rerun()

        else:

            st.info("No hay gastos registrados.")

    # ==========================================
    # INGRESOS
    # ==========================================

    with sub_i:

        if not df_ingresos.empty:

            for idx, fila in df_ingresos.copy().iterrows():

                c_i, c_b = st.columns([6, 1])

                with c_i:

                    st.write(
                        f"📅 {fila['Fecha']} | "
                        f"Cliente: *{fila['Cliente']}* | "
                        f"**$ {fila['Monto Total (ARS)']:,.2f}**"
                    )

                with c_b:

                    if st.button(
                        "🗑 Borrar",
                        key=f"b_ing_{fila['ID_Ingreso']}_{idx}"
                    ):

                        df_ingresos = df_ingresos.drop(idx)

                        df_ingresos.to_csv(
                            "registro_ingresos.csv",
                            index=False
                        )

                        st.success("Ingreso eliminado.")

                        st.rerun()

        else:

            st.info("No hay ingresos registrados.")

    # ==========================================
    # PAGOS PERSONAL
    # ==========================================

    with sub_p:

        if df_pagos_empleados.empty:

            st.info("No hay movimientos de personal.")

        else:

            for idx, fila in df_pagos_empleados.copy().iterrows():

                c_i, c_b = st.columns([6, 1])

                with c_i:

                    st.write(
                        f"📅 {fila['Fecha Pago']} | "
                        f"Operario: *{fila['Nombre Empleado']}* | "
                        f"**$ {fila['Monto (ARS)']:,.2f}**"
                    )

                with c_b:

                    boton_borrar = st.button(
                        "🗑 Borrar",
                        key=f"b_emp_{fila['ID_Pago']}_{idx}"
                    )

                if boton_borrar:

                    id_pago_borrar = str(
                        fila["ID_Pago"]
                    )

                # ==========================================
                # BORRAR DE NEON
                # ==========================================

                conn = None
                cursor = None

                try:

                    conn = get_conn()
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        DELETE FROM pagos_empleados
                        WHERE id_pago = %s
                        """,
                        (id_pago_borrar,)
                    )

                    conn.commit()

                except Exception as e:

                    if conn:
                        conn.rollback()

                    st.error(
                        f"❌ No se pudo eliminar de Neon: {e}"
                    )

                    if cursor:
                        cursor.close()

                    if conn:
                        conn.close()

                    st.stop()

                finally:

                    if cursor:
                        cursor.close()

                    if conn:
                        conn.close()

                # ==========================================
                # ELIMINAR DE LA TABLA EN MEMORIA
                # ==========================================

                df_pagos_empleados = (
                    df_pagos_empleados[
                        df_pagos_empleados["ID_Pago"].astype(str)
                        != id_pago_borrar
                    ]
                    .reset_index(drop=True)
                )

                # ==========================================
                # ACTUALIZAR CSV DE RESPALDO
                # ==========================================

                df_pagos_empleados.to_csv(
                    "registro_pagos_empleados.csv",
                    index=False,
                    encoding="utf-8-sig"
                )

                st.success(
                    "✅ Movimiento eliminado correctamente de Neon."
                )

                st.rerun()

    # ==========================================
    # SEGUROS
    # ==========================================

    with sub_s:

        if not df_seguros.empty:

            for idx, fila in df_seguros.copy().iterrows():

                c_i, c_b = st.columns([6, 1])

                with c_i:

                    st.write(
                        f"🛡 {fila['Compañía']} | "
                        f"Bien: *{fila['Bien Asegurado']}* | "
                        f"**$ {fila['Monto Prima (ARS)']:,.2f}**"
                    )

                with c_b:

                    if st.button(
                        "🗑 Borrar",
                        key=f"b_seg_{fila['ID_Seguro']}_{idx}"
                    ):

                        df_seguros = df_seguros.drop(idx)

                        df_seguros.to_csv(
                            "registro_seguros.csv",
                            index=False
                        )

                        st.success("Seguro eliminado.")

                        st.rerun()