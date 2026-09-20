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

if not os.path.exists("datos_facturas.csv"):
    pd.DataFrame(columns=["ID", "Fecha Registro", "Proveedor", "Monto Original", "Moneda", "Monto (ARS)", "Categoría", "Lote Asignado", "Estado Pago", "Archivo Comprobante"]).to_csv("datos_facturas.csv", index=False)
df_facturas = pd.read_csv("datos_facturas.csv")
if "ID" not in df_facturas.columns: df_facturas["ID"] = [str(int(datetime.now().timestamp()) + i) for i in range(len(df_facturas))]
df_facturas["ID"] = df_facturas["ID"].astype(str)

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


df_pagos_empleados = pd.read_csv(
    "registro_pagos_empleados.csv"
)


# Agregar columnas nuevas si el archivo ya existía

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

    # NUEVAS COLUMNAS
    "Porcentaje Bonificacion": 0.0,
    "Monto Bonificacion (ARS)": 0.0,
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


for columna, valor in columnas_pagos.items():
    if columna not in df_pagos_empleados.columns:
        df_pagos_empleados[columna] = valor

# Asegurar que los ID sean texto

df_pagos_empleados["ID_Pago"] = (
    df_pagos_empleados["ID_Pago"]
    .fillna("")
    .astype(str)
)
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
                value=datetime.today()
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
                value=datetime.today()
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

        guardar = st.form_submit_button(
            "💾 Guardar gasto"
        )

    if guardar:

        nuevo = {

            "ID": str(int(datetime.now().timestamp())),

            "Fecha Registro": fecha.strftime("%Y-%m-%d"),

            "Proveedor": proveedor,

            "Monto Original": monto,

            "Moneda": "ARS",

            "Monto (ARS)": monto,

            "Categoría": categoria,

            "Lote Asignado": lote,

            "Estado Pago": estado,

            "Archivo Comprobante": ""

        }

        df_facturas = pd.concat(
            [
                df_facturas,
                pd.DataFrame([nuevo])
            ],
            ignore_index=True
        )

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
                            nombre_archivo_guardado = f"liquidado_{int(datetime.now().timestamp())}_{archivo_pendiente.name}"
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

def obtener_saldo_adelanto(df_pagos, empleado):

    if df_pagos.empty:
        return 0.0

    df_emp = df_pagos[
        df_pagos["Nombre Empleado"] == empleado
    ].copy()

    if df_emp.empty:
        return 0.0

    if "Adelanto Generado (ARS)" not in df_emp.columns:
        return 0.0

    if "Monto Compensado (ARS)" not in df_emp.columns:
        return 0.0

    adelantos = pd.to_numeric(
        df_emp["Adelanto Generado (ARS)"],
        errors="coerce"
    ).fillna(0).sum()

    compensados = pd.to_numeric(
        df_emp["Monto Compensado (ARS)"],
        errors="coerce"
    ).fillna(0).sum()

    return max(adelantos - compensados, 0.0)


def guardar_comprobantes(comprobantes, id_liquidacion):

    if not comprobantes:
        return []

    carpeta = os.path.join(
        "comprobantes_pagos",
        str(id_liquidacion)
    )

    os.makedirs(carpeta, exist_ok=True)

    nombres = []

    for numero, archivo in enumerate(comprobantes, 1):

        nombre_original = os.path.basename(
            archivo.name
        )

        nombre_limpio = re.sub(
            r"[^a-zA-Z0-9._-]",
            "_",
            nombre_original
        )

        nombre_final = (
            f"{numero}_{nombre_limpio}"
        )

        ruta = os.path.join(
            carpeta,
            nombre_final
        )

        with open(ruta, "wb") as f:
            f.write(
                archivo.getbuffer()
            )

        nombres.append(nombre_final)

    return nombres


def generar_pdf_liquidacion(
    id_liquidacion,
    empleado,
    fecha,
    horas,
    valor_hora,
    monto_base,
    porcentaje,
    monto_bonificacion,
    monto_final,
    adelanto_anterior,
    monto_compensado,
    monto_neto,
    monto_pagado,
    adelanto_nuevo,
    saldo_adelanto,
    tipo_pago,
    estado,
    concepto,
    comprobantes
):

    carpeta = "liquidaciones_pdf"

    os.makedirs(
        carpeta,
        exist_ok=True
    )

    ruta_pdf = os.path.join(
        carpeta,
        f"liquidacion_{id_liquidacion}.pdf"
    )

    doc = SimpleDocTemplate(
        ruta_pdf,
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
        Spacer(1, 8)
    )

    elementos.append(
        Paragraph(
            "<b>LIQUIDACIÓN DE PERSONAL</b>",
            estilos["Heading2"]
        )
    )

    elementos.append(
        Spacer(1, 10)
    )

    datos_principales = [
        ["Empleado", empleado],
        ["Fecha", str(fecha)],
        ["ID Liquidación", str(id_liquidacion)],
        ["Tipo", tipo_pago],
        ["Estado", estado],
        ["Concepto", concepto],
    ]

    tabla_principal = Table(
        datos_principales,
        colWidths=[45 * mm, 130 * mm]
    )

    tabla_principal.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )

    elementos.append(tabla_principal)

    elementos.append(
        Spacer(1, 15)
    )

    datos_liquidacion = [
        ["Detalle", "Valor"],

        [
            "Horas trabajadas",
            f"{horas:.2f} h"
        ],

        [
            "Valor por hora",
            f"$ {valor_hora:,.2f}"
        ],

        [
            "Monto base",
            f"$ {monto_base:,.2f}"
        ],

        [
            "Bonificación / Descuento",
            f"{porcentaje:+.2f}%"
        ],

        [
            "Monto bonificación/descuento",
            f"$ {monto_bonificacion:,.2f}"
        ],

        [
            "Monto final del trabajo",
            f"$ {monto_final:,.2f}"
        ],

        [
            "Adelanto anterior",
            f"$ {adelanto_anterior:,.2f}"
        ],

        [
            "Adelanto compensado",
            f"$ {monto_compensado:,.2f}"
        ],

        [
            "Neto a pagar",
            f"$ {monto_neto:,.2f}"
        ],

        [
            "Monto realmente pagado",
            f"$ {monto_pagado:,.2f}"
        ],

        [
            "Nuevo adelanto generado",
            f"$ {adelanto_nuevo:,.2f}"
        ],

        [
            "Saldo de adelanto",
            f"$ {saldo_adelanto:,.2f}"
        ],
    ]

    tabla_liquidacion = Table(
        datos_liquidacion,
        colWidths=[100 * mm, 75 * mm]
    )

    tabla_liquidacion.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
            ("FONTNAME", (0, 9), (-1, 9), "Helvetica-Bold"),
            ("FONTNAME", (0, 12), (-1, 12), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ])
    )

    elementos.append(tabla_liquidacion)

    elementos.append(
        Spacer(1, 15)
    )

    elementos.append(
        Paragraph(
            "<b>Comprobantes de pago:</b>",
            estilos["Heading3"]
        )
    )

    if comprobantes:

        for comprobante in comprobantes:

            elementos.append(
                Paragraph(
                    f"• {comprobante}",
                    estilos["Normal"]
                )
            )

    else:

        elementos.append(
            Paragraph(
                "No se adjuntaron comprobantes.",
                estilos["Normal"]
            )
        )

    elementos.append(
        Spacer(1, 15)
    )

    elementos.append(
        Paragraph(
            "Documento generado automáticamente por "
            "D&A Candelero Agro.",
            estilos["Normal"]
        )
    )

    doc.build(elementos)

    return ruta_pdf

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
                "📋 Liquidación por horas totales"
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
                                    datetime.now().timestamp()
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
                                    datetime.now().strftime(
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

                            df_pagos_empleados.to_csv(
                                "registro_pagos_empleados.csv",
                                index=False
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

                # ==========================================
        # LIQUIDACIÓN ESPECIAL POR HORAS TOTALES
        # ==========================================
        else:

            st.markdown("### 📋 Liquidación por horas totales")

            st.info(
                "Esta opción permite cargar una liquidación completa "
                "sin tener que registrar cada jornada por separado."
            )

            with st.form("form_liquidacion_especial"):

                if not df_empleados.empty:

                    # ==========================================
                    # EMPLEADO
                    # ==========================================

                    emp_liquidacion = st.selectbox(
                        "👤 Empleado",
                        df_empleados["Nombre"].tolist(),
                        key="empleado_liquidacion_especial"
                    )

                    # ==========================================
                    # FECHA DE LIQUIDACIÓN
                    # ==========================================

                    fecha_liquidacion = st.date_input(
                        "📅 Fecha de liquidación",
                        value=datetime.date.today(),
                        key="fecha_liquidacion_especial"
                    )

                    # ==========================================
                    # HORAS TOTALES
                    # ==========================================

                    horas_totales = st.number_input(
                        "⏱️ Horas totales trabajadas",
                        min_value=0.0,
                        step=0.5,
                        value=0.0,
                        key="horas_totales_liquidacion"
                    )

                    # ==========================================
                    # VALOR HORA
                    # ==========================================

                    valor_hora_total = st.number_input(
                        "💵 Valor de la hora",
                        min_value=0.0,
                        step=100.0,
                        value=0.0,
                        key="valor_hora_liquidacion"
                    )

                    # ==========================================
                    # MONTO BASE
                    # ==========================================

                    monto_base_trabajado = (
                        horas_totales * valor_hora_total
                    )

                    st.markdown(
                        f"""
                        **Monto trabajado:**  
                        ${monto_base_trabajado:,.2f}
                        """.replace(",", "X").replace(".", ",").replace("X", ".")
                    )

                                        # ==========================================
                    # BONIFICACIÓN
                    # ==========================================

                    porcentaje_bonificacion = st.number_input(
                        "🎁 Bonificación (%)",
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

                    # ==========================================
                    # DESCUENTO
                    # ==========================================

                    porcentaje_descuento = st.number_input(
                        "➖ Descuento (%)",
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

                    # ==========================================
                    # MONTO FINAL DEL TRABAJO
                    # ==========================================

                    monto_final_trabajo = (
                        monto_base_trabajado
                        + monto_bonificacion
                        - monto_descuento
                    )

                    if monto_final_trabajo < 0:
                        monto_final_trabajo = 0.0

                    st.markdown(
                        f"""
                        **Monto final del trabajo:**  
                        ${monto_final_trabajo:,.2f}
                        """.replace(",", "X")
                        .replace(".", ",")
                        .replace("X", ".")
                    )

                    # ==========================================
                    # ADELANTO / DEUDA ANTERIOR
                    # ==========================================

                    saldo_adelanto_anterior = obtener_saldo_adelanto(
                        df_pagos_empleados,
                        emp_liquidacion
                    )

                    if saldo_adelanto_anterior > 0:

                        st.warning(
                            "⚠️ Este empleado tiene un adelanto/deuda "
                            f"pendiente de "
                            f"${saldo_adelanto_anterior:,.2f}"
                        )

                    else:

                        st.success(
                            "✅ Este empleado no tiene adelantos pendientes."
                        )

                    # ==========================================
# COMPENSACIÓN AUTOMÁTICA DEL ADELANTO
# ==========================================

# El sistema calcula automáticamente cuánto
# del adelanto pendiente se descuenta.

monto_compensado = min(
    saldo_adelanto_anterior,
    monto_final_trabajo
)

st.info(
    f"💳 Adelanto a compensar automáticamente: "
    f"${monto_compensado:,.2f}"
    .replace(",", "X")
    .replace(".", ",")
    .replace("X", ".")
)
                    # ==========================================
                    # NETO A PAGAR
                    # ==========================================

                    monto_neto_a_pagar = (
                        monto_final_trabajo
                        - monto_compensado
                    )

                    if monto_neto_a_pagar < 0:
                        monto_neto_a_pagar = 0.0

                    st.markdown(
                        f"""
                        ### 💰 Neto correspondiente

                        **${monto_neto_a_pagar:,.2f}**
                        """.replace(",", "X").replace(".", ",").replace("X", ".")
                    )

                    # ==========================================
                    # MONTO REALMENTE PAGADO
                    # ==========================================

                    monto_pagado = st.number_input(
                        "💵 Monto realmente pagado",
                        min_value=0.0,
                        step=100.0,
                        value=float(monto_neto_a_pagar),
                        key="monto_pagado_liquidacion"
                    )

                    st.caption(
                        "Este es el importe que realmente se entrega al empleado. "
                        "Puede ser diferente del neto correspondiente."
                    )

                    # ==========================================
                    # DIFERENCIA
                    # ==========================================

                    if monto_pagado < monto_neto_a_pagar:

                        saldo_pendiente_pago = (
                            monto_neto_a_pagar - monto_pagado
                        )

                        adelanto_nuevo = 0.0

                        st.warning(
                            f"⚠️ Queda un saldo pendiente de pago de "
                            f"${saldo_pendiente_pago:,.2f}"
                        )

                    elif monto_pagado > monto_neto_a_pagar:

                        adelanto_nuevo = (
                            monto_pagado - monto_neto_a_pagar
                        )

                        saldo_pendiente_pago = 0.0

                        st.info(
                            f"ℹ️ El empleado recibe "
                            f"${adelanto_nuevo:,.2f} "
                            f"por encima de la liquidación."
                        )

                    else:

                        adelanto_nuevo = 0.0
                        saldo_pendiente_pago = 0.0

                    # ==========================================
                    # SALDO FINAL DE ADELANTO
                    # ==========================================

                    saldo_adelanto_final = (
                        saldo_adelanto_anterior
                        - monto_compensado
                        + adelanto_nuevo
                    )

                    if saldo_adelanto_final < 0:
                        saldo_adelanto_final = 0.0

                    # ==========================================
                    # ESTADO DEL PAGO
                    # ==========================================

                    estado_liquidacion = st.selectbox(
                        "📌 Estado del pago",
                        [
                            "Pagado",
                            "Pendiente",
                            "Pagado parcialmente"
                        ],
                        key="estado_liquidacion_especial"
                    )

                    # ==========================================
                    # CONCEPTO
                    # ==========================================

                    concepto_liquidacion = st.text_input(
                        "📝 Concepto",
                        value="Liquidación de horas",
                        key="concepto_liquidacion_especial"
                    )

                    # ==========================================
                    # COMPROBANTES
                    # ==========================================

                    archivos_comprobantes = st.file_uploader(
                        "📎 Comprobantes",
                        accept_multiple_files=True,
                        key="comprobantes_liquidacion_especial"
                    )

                    # ==========================================
                    # RESUMEN
                    # ==========================================

                    st.markdown("---")
                    st.markdown("### 📊 Resumen de liquidación")

                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            f"**Monto trabajado:** "
                            f"${monto_base_trabajado:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Bonificación:** "
                            f"${monto_bonificacion:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Descuento:** "
                            f"${monto_descuento:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Monto final:** "
                            f"${monto_final_trabajo:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                    with col2:

                        st.write(
                            f"**Adelanto anterior:** "
                            f"${saldo_adelanto_anterior:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Adelanto compensado:** "
                            f"${monto_compensado:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Neto correspondiente:** "
                            f"${monto_neto_a_pagar:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                        st.write(
                            f"**Realmente pagado:** "
                            f"${monto_pagado:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )

                    # ==========================================
                    # SALDOS
                    # ==========================================

                    st.markdown("---")

                    col3, col4 = st.columns(2)

                    with col3:

                        st.metric(
                            "💰 Saldo de adelanto",
                            f"${saldo_adelanto_final:,.2f}"
                        )

                    with col4:

                        st.metric(
                            "📌 Saldo pendiente de pago",
                            f"${saldo_pendiente_pago:,.2f}"
                        )

                    # ==========================================
                    # BOTÓN GUARDAR
                    # ==========================================

                    guardar_liquidacion = st.form_submit_button(
                        "💾 Guardar liquidación",
                        use_container_width=True
                    )

                    # ==========================================
                    # GUARDAR
                    # ==========================================

                    if guardar_liquidacion:

                        nuevo_id = (
                            int(df_pagos_empleados["ID_Pago"].max()) + 1
                            if not df_pagos_empleados.empty
                            else 1
                        )

                        nombres_comprobantes = guardar_comprobantes(
                            archivos_comprobantes,
                            nuevo_id,
                            emp_liquidacion
                        )

                        nuevo_pago = {

                            "ID_Pago": nuevo_id,

                            "Fecha Pago": str(
                                fecha_liquidacion
                            ),

                            "Nombre Empleado":
                                emp_liquidacion,

                            "Fecha Trabajo": str(
                                fecha_liquidacion
                            ),

                            "Hora Entrada": "",

                            "Hora Salida": "",

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
                                    saldo_pendiente_pago,
                                    2
                                ),

                            "Comprobantes":
                                nombres_comprobantes,

                            "PDF Liquidacion":
                                ""
                        }

                        df_pagos_empleados = pd.concat(
                            [
                                df_pagos_empleados,
                                pd.DataFrame([nuevo_pago])
                            ],
                            ignore_index=True
                        )

                        # ==========================================
                        # GUARDAR CSV
                        # ==========================================

                        df_pagos_empleados.to_csv(
                            ARCHIVO_PAGOS_EMPLEADOS,
                            index=False,
                            encoding="utf-8-sig"
                        )

                        # ==========================================
                        # PDF
                        # ==========================================

                        try:

                            ruta_pdf = generar_pdf_liquidacion(
                                nuevo_id,
                                emp_liquidacion,
                                fecha_liquidacion,
                                horas_totales,
                                valor_hora_total,
                                monto_base_trabajado,
                                porcentaje_bonificacion,
                                monto_bonificacion,
                                monto_final_trabajo,
                                saldo_adelanto_anterior,
                                monto_compensado,
                                monto_neto_a_pagar,
                                monto_pagado,
                                adelanto_nuevo,
                                saldo_adelanto_final,
                                tipo_liquidacion,
                                estado_liquidacion,
                                concepto_liquidacion,
                                nombres_comprobantes
                            )

                            if ruta_pdf:

                                df_pagos_empleados.loc[
                                    df_pagos_empleados["ID_Pago"] == nuevo_id,
                                    "PDF Liquidacion"
                                ] = ruta_pdf

                                df_pagos_empleados.to_csv(
                                    ARCHIVO_PAGOS_EMPLEADOS,
                                    index=False,
                                    encoding="utf-8-sig"
                                )

                        except Exception as e:

                            st.warning(
                                f"⚠️ La liquidación se guardó, "
                                f"pero no se pudo generar el PDF: {e}"
                            )

                        st.success(
                            "✅ Liquidación guardada correctamente."
                        )

                        st.rerun()

                else:

                    st.warning(
                        "⚠️ No hay operarios registrados."
                    )
# ==========================================
# BOTÓN DE DESCARGA DEL PDF
# SOLO EN SISTEMA DE TRIPULACIÓN
# ==========================================

if menu == "👥 SISTEMA DE TRIPULACIÓN":

    if "ultimo_pdf_liquidacion" in st.session_state:

        pdf_info = st.session_state[
            "ultimo_pdf_liquidacion"
        ]

        if os.path.exists(pdf_info["ruta"]):

            with open(
                pdf_info["ruta"],
                "rb"
            ) as archivo_pdf:

                st.download_button(
                    label="📄 DESCARGAR LIQUIDACIÓN EN PDF",
                    data=archivo_pdf.read(),
                    file_name=(
                        f"Liquidacion_"
                        f"{pdf_info['empleado']}_"
                        f"{pdf_info['fecha']}.pdf"
                    ),
                    mime="application/pdf",
                    key=f"pdf_{pdf_info['id']}"
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
                            "Monto (ARS)",
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

            else:

                st.info(
                    "No hay registros de pagos para este operario."
                )

        else:

            st.info("Sin movimientos.")

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
            seg_venc = st.date_input("Vencimiento", value=datetime.today())
        with s3:
            seg_monto = st.number_input("Monto Cuota ($ ARS)", min_value=0.0)
            seg_estado = st.radio("Estado:", ["Pagado", "Pendiente"], horizontal=True)
        btn_seguro = st.form_submit_button("💾 Archivar")
        if btn_seguro and seg_comp and seg_monto > 0:
                nuevo_seg = {
                    "ID_Seguro": f"seg_{int(datetime.now().timestamp())}", "Compañía": seg_comp.strip(), "Tipo Cobertura": seg_tipo,
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

        if not df_pagos_empleados.empty:

            for idx, fila in df_pagos_empleados.copy().iterrows():

                c_i, c_b = st.columns([6, 1])

                with c_i:

                    st.write(
                        f"📅 {fila['Fecha Pago']} | "
                        f"Operario: *{fila['Nombre Empleado']}* | "
                        f"**$ {fila['Monto (ARS)']:,.2f}**"
                    )

                with c_b:

                    if st.button(
                        "🗑 Borrar",
                        key=f"b_emp_{fila['ID_Pago']}_{idx}"
                    ):

                        df_pagos_empleados = df_pagos_empleados.drop(idx)

                        df_pagos_empleados.to_csv(
                            "registro_pagos_empleados.csv",
                            index=False
                        )

                        st.success("Movimiento de personal eliminado.")

                        st.rerun()

        else:

            st.info("No hay movimientos de personal.")

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