import streamlit as st
import pandas as pd
import os
from datetime import datetime
import psycopg2

from pages.clientes import pantalla_clientes
from pages.servicios import pantalla_servicios
from pages.facturacion import pantalla_facturacion
from pages.administracion import pantalla_administracion
from database import get_conn

def check_password(usuario, password):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT nombre, rol FROM usuarios WHERE usuario = %s AND password = %s",(usuario, password)
    )

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
                if nombre:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = txt_user
                    st.session_state["rol"] = rol
                    st.session_state["nombre_usuario"] = nombre
                    st.success(f"¡Bienvenido {nombre}!")
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")

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
    pd.DataFrame(columns=["ID_Pago", "Fecha Pago", "Nombre Empleado", "Monto (ARS)", "Tipo Registro", "Estado Pago", "Concepto"]).to_csv("registro_pagos_empleados.csv", index=False)
df_pagos_empleados = pd.read_csv("registro_pagos_empleados.csv")
if "ID_Pago" not in df_pagos_empleados.columns: df_pagos_empleados["ID_Pago"] = [str(int(datetime.now().timestamp()) + i + 500) for i in range(len(df_pagos_empleados))]
df_pagos_empleados["ID_Pago"] = df_pagos_empleados["ID_Pago"].astype(str)

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
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN FILTRADA DE PESTAÑAS POR ROL
# ==========================================
rol_actual = st.session_state["rol"]
nombre_actual = st.session_state["nombre_usuario"]

menu = st.sidebar.radio(
    "📂 Menú",
    [
        "📊 Analíticas",
        "🚜 Labores y Lotes",
        "🛠 Servicios",
        "🧾 Facturación",
        "👥 Clientes",
        "💰 Ingresos por Trabajos",
        "🧾 Gastos Comerciales",
        "🔍 Cuentas Pendientes",
        "👥 Sistema de Tripulación",
        "📋 Rendición por Operario",
        "🛡 Seguros y Coberturas",
        "⚙ Administración",
        "🗄 Control de Errores"
    ]
)
st.sidebar.title("🚜 D&A CANDELERO AGRO")

menu = st.sidebar.radio(
    "Menú",
    lista_tabs
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
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        💰 Facturación Total Ingresos
                    </div>
                    <div class="card-value-custom">
                        $ {total_ingresos_global:,.2f}
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        with c2:
            st.markdown(
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        🧾 Gastos Comerciales
                    </div>
                    <div class="card-value-custom">
                        $ {total_gasto_facturas:,.2f}
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        with c3:
            st.markdown(
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        👥 Total Costo Tripulación
                    </div>
                    <div class="card-value-custom">
                        $ {total_tripulacion_global:,.2f}
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        with c4:
            st.markdown(
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        🔴 Cuentas Proveedores Pendientes
                    </div>
                    <div class="card-value-custom">
                        $ {total_pendiente_facturas:,.2f}
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        c5, c6 = st.columns(2)

        with c5:
            st.markdown(
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        Superficie Total Operada
                    </div>
                    <div class="card-value-custom">
                        {total_has_global:,.1f} Has
                    </div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        with c6:
            st.markdown(
                f'''
                <div class="card-box">
                    <div class="card-title-custom">
                        Promedio Gasoil Flota
                    </div>
                    <div class="card-value-custom">
                        {eficiencia_flota:.2f} L/Ha
                    </div>
                </div>
                ''',
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
                fecha_labor = st.date_input("Fecha de Labor", value=datetime.today())
                lote_labor = st.text_input("Nombre del Campo / Lote")
            with col_la2:
                maquina_labor = st.selectbox("Maquinaria Activa", ["Cosechadora CR 7.90", "Tractor Valtra", "Pulverizadora", "Camión"])
                has_labor = st.number_input("Hectáreas Trabajadas", min_value=0.0, step=1.0)
            with col_la3:
                eficiencia_labor = st.number_input("Consumo Gasoil (Litros por Ha)", min_value=0.0, step=0.1)
                st.markdown("<br>", unsafe_allow_html=True)
                btn_lab = st.form_submit_button("💾 Guardar Trabajo")

            if btn_lab and lote_labor and has_labor > 0:
                litros_totales = round(has_labor * eficiencia_labor, 1)
                nueva_labor = {
                    "Fecha": fecha_labor.strftime("%Y-%m-%d"), "Maquinaria": maquina_labor, "Lote": lote_labor.strip(),
                    "Has Trabajadas": has_labor, "Gasoil Consumido (L)": litros_totales, "Eficiencia (L/Ha)": round(eficiencia_labor, 2)
                }
                df_telemetria = pd.concat([df_telemetria, pd.DataFrame([nueva_labor])], ignore_index=True)
                df_telemetria.to_csv("registro_telemetria.csv", index=False)
                st.success("✔ ¡Trabajo guardado!")
                st.rerun()
        if not df_telemetria.empty: st.dataframe(df_telemetria, use_container_width=True)

# ----------------------------------------------------
# PESTAÑA: INGRESOS POR TRABAJOS
# ----------------------------------------------------
if menu == "💰 INGRESOS POR TRABAJOS":
        st.header("💰 Registro de Facturación e Ingresos por Servicios")
        with st.form("form_ingresos", clear_on_submit=True):
            i1, i2, i3 = st.columns(3)
            with i1:
                i_fecha = st.date_input("Fecha del Trabajo/Cobro", value=datetime.today())
                i_cliente = st.text_input("Cliente / Productor")
            with i2:
                i_servicio = st.selectbox("Tipo de Servicio", ["Cosecha", "Siembra", "Pulverización", "Movimiento de Paja / Rollos", "Otros"])
                i_lote = st.text_input("Establecimiento / Lote Destino")
            with i3:
                i_has = st.number_input("Cantidad de Hectáreas", min_value=0.0, step=1.0)
                i_monto = st.number_input("Monto Cobrado/Facturado ($ ARS)", min_value=0.0, step=100.0)
            i_detalle = st.text_input("Notas / Detalles del Pago")
            btn_ingreso = st.form_submit_button("💾 Registrar Ingreso")

            if btn_ingreso and i_cliente and i_monto > 0:
                nuevo_id_ing = f"ing_{int(datetime.now().timestamp())}"
                nuevo_ingreso = {
                    "ID_Ingreso": nuevo_id_ing, "Fecha": i_fecha.strftime("%Y-%m-%d"), "Cliente": i_cliente.strip(),
                    "Tipo Servicio": i_servicio, "Lote/Establecimiento": i_lote.strip(), "Hectáreas": i_has,
                    "Monto Total (ARS)": i_monto, "Detalle": i_detalle
                }
                df_ingresos = pd.concat([df_ingresos, pd.DataFrame([nuevo_ingreso])], ignore_index=True)
                df_ingresos.to_csv("registro_ingresos.csv", index=False)
                st.success("✔ ¡Ingreso registrado!")
                st.rerun()
        if not df_ingresos.empty: st.dataframe(df_ingresos, use_container_width=True)

# ----------------------------------------------------
# PESTAÑA: GASTOS COMERCIALES
# ----------------------------------------------------
if menu == ("🧾 GASTOS COMERCIALES")
        st.header("🧾 Archivo de Comprobantes Comerciales")
        with st.form("form_facturas", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                proveedor = st.text_input("Proveedor / Taller / Repuestera")
                categoria = st.selectbox("Categoría de Compra", ["Repuestos y Talleres", "Combustibles", "Semillas", "Agroquímicos / Fertilizantes", "Gastos Generales"])
                lote_asignado = st.text_input("Lote o Campo Destino")
            with f2:
                monto_orig = st.number_input("Monto del Comprobante", min_value=0.0)
                moneda = st.radio("Moneda", ["Pesos ($ ARS)", "Dólares (USD)"], horizontal=True)
                estado_pago = st.radio("Condición Inicial de la Factura:", ["Pagado", "Pendiente de Pago"], horizontal=True)
            with f3:
                archivo_adjunto = st.file_uploader("Subir Factura/Remito digital", type=["pdf", "png", "jpg", "jpeg"])
                st.markdown("<br><br>", unsafe_allow_html=True)
                btn_fac = st.form_submit_button("💾 Registrar Gasto")

            if btn_fac and proveedor and monto_orig > 0:
                simbolo = "USD" if "Dólares" in moneda else "ARS"
                monto_ars = monto_orig * TIPO_CAMBIO_OFICIAL if simbolo == "USD" else monto_orig

                nombre_archivo_guardado = "N/A"
                if archivo_adjunto is not None:
                    nombre_archivo_guardado = f"{int(datetime.now().timestamp())}_{archivo_adjunto.name}"
                    with open(os.path.join("comprobantes", nombre_archivo_guardado), "wb") as f:
                        f.write(archivo_adjunto.getbuffer())

                nuevo_id = str(int(datetime.now().timestamp()))
                nueva_fac = {
                    "ID": nuevo_id, "Fecha Registro": datetime.now().strftime("%Y-%m-%d %H:%M"), "Proveedor": proveedor, "Monto Original": f"{simbolo} {monto_orig:,.2f}",
                    "Moneda": simbolo, "Monto (ARS)": monto_ars, "Categoría": categoria, "Lote Asignado": lote_asignado, "Estado Pago": estado_pago, "Archivo Comprobante": nombre_archivo_guardado
                }
                df_facturas = pd.concat([df_facturas, pd.DataFrame([nueva_fac])], ignore_index=True)
                df_facturas.to_csv("datos_facturas.csv", index=False)
                st.success("✔ ¡Gasto comercial registrado!")
                st.rerun()
        if not df_facturas.empty: st.dataframe(df_facturas, use_container_width=True)

# ----------------------------------------------------
# PESTAÑA: CUENTAS PENDIENTES
# ----------------------------------------------------
if menu == ("🔍 CUENTAS PENDIENTES")
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

# ----------------------------------------------------
# PESTAÑA: SISTEMA DE TRIPULACIÓN
# ----------------------------------------------------
if menu == ("👥 SISTEMA DE TRIPULACIÓN")
        st.header("👤 Personal y Comisiones de la Tripulación")
        emp_col1, emp_col2 = st.columns(2)
        with emp_col1:
            st.subheader("1. Gestión del Personal Fijo")
            if not df_empleados.empty:
                st.dataframe(df_empleados, use_container_width=True)

            st.markdown("---")
            st.subheader("Agregar Nuevo Integrante (si ingresa alguien nuevo)")
            with st.form("form_alta_empleado"):
                n_nombre = st.text_input("Nombre Completo (Ej: Juan Perez)")
                n_puesto = st.selectbox("Rol", ["Maquinista Cosechadora", "Tractorista", "Ayudante / Mecánico"])
                n_porcentaje = st.number_input("Comisión (%)", min_value=0.0, max_value=100.0, step=0.1, value=0.0)
                btn_alta_emp = st.form_submit_button("💾 Guardar Nuevo Operario")
                if btn_alta_emp and n_nombre:
                    nuevo_emp = {"Nombre": n_nombre.strip(), "Puesto": n_puesto, "Porcentaje (%)": n_porcentaje}
                    df_empleados = pd.concat([df_empleados, pd.DataFrame([nuevo_emp])], ignore_index=True)
                    df_empleados.to_csv("registro_empleados.csv", index=False)
                    st.rerun()

        with emp_col2:
            st.subheader("2. Cargar Movimiento de Cuenta")
            with st.form("form_pago_empleado"):
                if not df_empleados.empty:
                    emp_seleccionado = st.selectbox("Seleccionar Operario", df_empleados["Nombre"].tolist())
                    tipo_registro = st.radio("Tipo:", ["Liquidación / Pago", "Reintegro / Devolución"])
                    p_monto = st.number_input("Monto ($ ARS)", min_value=0.0)
                    p_estado = st.radio("Estado:", ["Pagado", "Pendiente"], horizontal=True)
                    p_concepto = st.text_input("Detalle (Ej: Entrega quincena, Compra de repuesto)")
                    btn_pago_emp = st.form_submit_button("💳 Guardar Movimiento")
                    if btn_pago_emp and p_monto > 0:
                        nuevo_pago = {
                            "ID_Pago": str(int(datetime.now().timestamp())), "Fecha Pago": datetime.now().strftime("%Y-%m-%d"),
                            "Nombre Empleado": emp_seleccionado, "Monto (ARS)": p_monto, "Tipo Registro": tipo_registro, "Estado Pago": p_estado, "Concepto": p_concepto
                        }
                        df_pagos_empleados = pd.concat([df_pagos_empleados, pd.DataFrame([nuevo_pago])], ignore_index=True)
                        df_pagos_empleados.to_csv("registro_pagos_empleados.csv", index=False)
                        st.success("✔ Movimiento registrado con éxito.")
                        st.rerun()

# ----------------------------------------------------
# PESTAÑA: RENDICIÓN POR OPERARIO (Filtro de Privacidad Seguro)
# ----------------------------------------------------
if menu == ("📋 RENDICIÓN POR OPERARIO")
        st.header("📋 Historial de Cuenta por Operario")

        if rol_actual == "Operario":
            lista_para_filtrar = [nombre_actual]
            st.info(f"Visualizando la cuenta de: **{nombre_actual}**")
        else:
            lista_para_filtrar = df_empleados["Nombre"].tolist() if not df_empleados.empty else ["No hay personal registrado"]

        op_filtro = st.selectbox("Seleccionar Operario para revisar:", lista_para_filtrar)
        df_op = df_pagos_empleados[df_pagos_empleados["Nombre Empleado"] == op_filtro] if not df_pagos_empleados.empty else pd.DataFrame()

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.markdown("### 💰 LIQUIDACIONES Y PAGOS EN EFECTIVO")
            if not df_op.empty:
                df_pagos = df_op[df_op["Tipo Registro"] == "Liquidación / Pago"]
                if not df_pagos.empty:
                    st.dataframe(df_pagos[["Fecha Pago", "Monto (ARS)", "Estado Pago", "Concepto"]], use_container_width=True)
                else: st.write("No hay registros de pagos para este operario.")
            else: st.write("Sin movimientos.")

        with col_r2:
            st.markdown("### 🔧 VALES Y REINTEGROS (GASTOS A RENDIR)")
            if not df_op.empty:
                df_reintegros = df_op[df_op["Tipo Registro"] == "Reintegro / Devolución"]
                if not df_reintegros.empty:
                    st.dataframe(df_reintegros[["Fecha Pago", "Monto (ARS)", "Estado Pago", "Concepto"]], use_container_width=True)
                else: st.write("No hay registros de reintegros o vales.")
            else: st.write("Sin movimientos.")
if menu == ("👥 CLIENTES")

if t_clientes:
    with t_clientes:
        pantalla_clientes()
        if menu == ("🧾 FACTURACIÓN")

if t_factura:
    with t_factura:
        pantalla_facturacion()

if menu == ("🛠 SERVICIOS")

if t_servicios:
    with t_servicios:
        pantalla_servicios()

if menu == ("⚙ ADMINISTRACIÓN")

if t_administracion: 
    with t_administracion:
        pantalla_administracion()
# ----------------------------------------------------
# PESTAÑA: SEGUROS Y COBERTURAS
# ----------------------------------------------------
t_seg = obtener_tab("🛡 SEGUROS Y COBERTURAS")
if t_seg:
    with t_seg:
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
# PESTAÑA SECRETA: CONTROL DE ERRORES (Solo Admin)
# ----------------------------------------------------
t_aud = obtener_tab("🗄 CONTROL DE ERRORES")
if t_aud and rol_actual == "Administrador":
    with t_aud:
        st.header("🗄 Panel exclusivo de borrado (Solo Administrador)")
        sub_g, sub_i, sub_p, sub_s = st.tabs(["Gastos", "Ingresos", "Pagos Personal", "Seguros"])

        with sub_g:
            if not df_facturas.empty:
                for idx, fila in df_facturas.copy().iterrows():
                    c_i, c_b = st.columns([6, 1])
                    with c_i: st.write(f"📅 {fila['Fecha Registro']} | *{fila['Proveedor']}* | **{fila['Monto Original']}**")
                    with c_b:
                        if st.button("🗑 Borrar", key=f"b_fac_{fila['ID']}_{idx}"):
                            df_facturas.drop(idx).to_csv("datos_facturas.csv", index=False)
                            st.rerun()
        with sub_i:
            if not df_ingresos.empty:
                for idx, fila in df_ingresos.copy().iterrows():
                    c_i, c_b = st.columns([6, 1])
                    with c_i: st.write(f"📅 {fila['Fecha']} | Cliente: *{fila['Cliente']}* | **$ {fila['Monto Total (ARS)']:,.2f}**")
                    with c_b:
                        if st.button("🗑 Borrar", key=f"b_ing_{fila['ID_Ingreso']}_{idx}"):
                            df_ingresos.drop(idx).to_csv("registro_ingresos.csv", index=False)
                            st.rerun()
        with sub_p:
            if not df_pagos_empleados.empty:
                for idx, fila in df_pagos_empleados.copy().iterrows():
                    c_i, c_b = st.columns([6, 1])
                    with c_i: st.write(f"📅 {fila['Fecha Pago']} | Operario: *{fila['Nombre Empleado']}* | **$ {fila['Monto (ARS)']:,.2f}**")
                    with c_b:
                        if st.button("🗑 Borrar", key=f"b_emp_{fila['ID_Pago']}_{idx}"):
                            df_pagos_empleados.drop(idx).to_csv("registro_pagos_empleados.csv", index=False)
                            st.rerun()
        with sub_s:
            if not df_seguros.empty:
                for idx, fila in df_seguros.copy().iterrows():
                    c_i, c_b = st.columns([6, 1])
                    with c_i: st.write(f"🛡 {fila['Compañía']} | Bien: *{fila['Bien Asegurado']}* | **$ {fila['Monto Prima (ARS)']:,.2f}**")
                    with c_b:
                        if st.button("🗑 Borrar", key=f"b_seg_{fila['ID_Seguro']}_{idx}"):
                            df_seguros.drop(idx).to_csv("registro_seguros.csv", index=False)
                            st.rerun()
    st.markdown("<br><br>", unsafe_allow_html=True)
