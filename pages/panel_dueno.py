
import streamlit as st
import pandas as pd
import os

from database import get_conn


def leer_csv(nombre, columnas=None):
    if os.path.exists(nombre):
        return pd.read_csv(nombre)

    return pd.DataFrame(columns=columnas if columnas else [])


def cargar_gastos_desde_neon():
    conn = None

    try:
        conn = get_conn()

        query = """
            SELECT
                id_gasto AS "ID",
                fecha_registro AS "Fecha Registro",
                proveedor AS "Proveedor",
                monto_original AS "Monto Original",
                moneda AS "Moneda",
                monto_ars AS "Monto (ARS)",
                categoria AS "Categoría",
                lote_asignado AS "Lote Asignado",
                estado_pago AS "Estado Pago",
                archivo_comprobante AS "Archivo Comprobante"
            FROM gastos_comerciales
            ORDER BY fecha_registro DESC, id_gasto DESC
        """

        df = pd.read_sql_query(query, conn)

        if "Monto (ARS)" in df.columns:
            df["Monto (ARS)"] = pd.to_numeric(
                df["Monto (ARS)"], errors="coerce"
            ).fillna(0)

        return df

    except Exception as e:
        st.error(f"❌ No se pudieron cargar los gastos desde Neon: {e}")
        return pd.DataFrame()

    finally:
        if conn is not None:
            conn.close()


def cargar_combustible_desde_neon():
    """
    Utiliza la función existente del sistema si está disponible.
    No modifica ni escribe datos en Neon.
    """
    try:
        from app import cargar_combustible_desde_neon as cargar_combustible
        return cargar_combustible()
    except Exception:
        return pd.DataFrame()


def pantalla_panel_dueno():
    st.header("👑 Panel de Control del Dueño")

    # ==========================
    # CARGAR DATOS
    # ==========================

    ingresos = leer_csv("registro_ingresos.csv")
    gastos = cargar_gastos_desde_neon()
    combustible = leer_csv("registro_combustible.csv")
    agenda = leer_csv("agenda.csv")
    pagos = leer_csv("registro_pagos_empleados.csv")
    telemetria = leer_csv("registro_telemetria.csv")

    # ==========================
    # FINANZAS
    # ==========================

    st.subheader("💰 Resumen Financiero")

    total_ingresos = 0.0
    if not ingresos.empty and "Monto Total (ARS)" in ingresos.columns:
        total_ingresos = pd.to_numeric(
            ingresos["Monto Total (ARS)"], errors="coerce"
        ).fillna(0).sum()

    total_gastos = 0.0
    if not gastos.empty and "Monto (ARS)" in gastos.columns:
        total_gastos = pd.to_numeric(
            gastos["Monto (ARS)"], errors="coerce"
        ).fillna(0).sum()

    total_combustible = 0.0
    if not combustible.empty and "Total" in combustible.columns:
        total_combustible = pd.to_numeric(
            combustible["Total"], errors="coerce"
        ).fillna(0).sum()

    resultado = total_ingresos - total_gastos - total_combustible

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("💰 Ingresos", f"$ {total_ingresos:,.0f}")

    with c2:
        st.metric("🧾 Gastos", f"$ {total_gastos:,.0f}")

    with c3:
        st.metric("⛽ Combustible", f"$ {total_combustible:,.0f}")

    with c4:
        st.metric("📈 Resultado", f"$ {resultado:,.0f}")

    st.divider()

    # ==========================
    # OPERACIONES
    # ==========================

    st.subheader("🚜 Operaciones")

    hectareas = 0.0
    litros = 0.0

    if not telemetria.empty:
        if "Has Trabajadas" in telemetria.columns:
            hectareas = pd.to_numeric(
                telemetria["Has Trabajadas"], errors="coerce"
            ).fillna(0).sum()

        if "Gasoil Consumido (L)" in telemetria.columns:
            litros = pd.to_numeric(
                telemetria["Gasoil Consumido (L)"], errors="coerce"
            ).fillna(0).sum()

    o1, o2 = st.columns(2)

    with o1:
        st.metric("🌾 Hectáreas trabajadas", f"{hectareas:,.1f} Has")

    with o2:
        st.metric("⛽ Litros consumidos", f"{litros:,.0f} L")

    st.divider()

    # ==========================
    # ALERTAS
    # ==========================

    st.subheader("🔔 Alertas")

    alertas = 0

    if not agenda.empty and "Estado" in agenda.columns:
        pendientes_agenda = agenda[
            agenda["Estado"].astype(str).str.contains(
                "Pendiente", case=False, na=False
            )
        ]

        if not pendientes_agenda.empty:
            alertas += len(pendientes_agenda)

            for _, fila in pendientes_agenda.iterrows():
                fecha = fila.get("Fecha", "")
                titulo = fila.get("Título", "Evento pendiente")
                st.warning(f"📅 {fecha} - {titulo}")

    if not gastos.empty and "Estado Pago" in gastos.columns:
        deudas = gastos[
            gastos["Estado Pago"].astype(str).str.strip().str.lower()
            == "pendiente de pago"
        ]

        if not deudas.empty:
            alertas += len(deudas)
            st.error(f"🧾 Hay {len(deudas)} proveedores pendientes de pago.")

    if alertas == 0:
        st.success("✅ No hay alertas pendientes")

    # ==========================
    # PERSONAL
    # ==========================

    st.divider()
    st.subheader("👥 Personal")

    pagos_pendientes = 0.0

    if not pagos.empty and "Estado Pago" in pagos.columns:
        pendientes_personal = pagos[
            pagos["Estado Pago"].astype(str).str.strip().str.lower()
            == "pendiente"
        ]

        if not pendientes_personal.empty and "Monto (ARS)" in pendientes_personal.columns:
            pagos_pendientes = pd.to_numeric(
                pendientes_personal["Monto (ARS)"], errors="coerce"
            ).fillna(0).sum()

    st.metric(
        "💵 Pagos pendientes personal",
        f"$ {pagos_pendientes:,.0f}"
    )

    # ==========================
    # DETALLE DE GASTOS
    # ==========================

    st.divider()
    st.subheader("🧾 Últimos gastos comerciales")

    if gastos.empty:
        st.info("No hay gastos registrados en Neon.")
    else:
        columnas_mostrar = [
            columna for columna in [
                "Fecha Registro",
                "Proveedor",
                "Categoría",
                "Monto (ARS)",
                "Estado Pago",
                "Lote Asignado"
            ]
            if columna in gastos.columns
        ]

        st.dataframe(
            gastos[columnas_mostrar],
            use_container_width=True,
            hide_index=True
        )