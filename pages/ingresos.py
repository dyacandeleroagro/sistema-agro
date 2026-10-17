
import streamlit as st
import pandas as pd
from datetime import datetime

from operaciones_db import (
    cargar_ingresos_desde_neon,
    guardar_ingreso_neon,
    eliminar_ingreso_neon,
)


def pantalla_ingresos():
    st.header("💰 Ingresos por Trabajos")

    # Cargar ingresos desde Neon
    try:
        df = cargar_ingresos_desde_neon()
    except Exception as e:
        st.error(f"No se pudieron cargar los ingresos desde Neon: {e}")
        return

    # ==========================================
    # NUEVO INGRESO
    # ==========================================
    st.subheader("➕ Nuevo ingreso")

    with st.form("nuevo_ingreso"):
        cliente = st.text_input("Cliente")
        servicio = st.text_input("Servicio")
        lote = st.text_input("Lote / Campo")
        hectareas = st.number_input(
            "Hectáreas", min_value=0.0, step=0.1
        )
        monto = st.number_input(
            "Monto ($)", min_value=0.0, step=1000.0
        )
        detalle = st.text_area("Detalle")

        guardar = st.form_submit_button("💾 Guardar ingreso")

    if guardar:
        if not cliente.strip():
            st.warning("Ingresá el nombre del cliente.")
        else:
            nuevo = {
                "ID": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "Fecha": datetime.today().strftime("%Y-%m-%d"),
                "Cliente": cliente.strip(),
                "Servicio": servicio.strip(),
                "Lote": lote.strip(),
                "Hectáreas": hectareas,
                "Monto": monto,
                "Detalle": detalle.strip(),
            }

            if guardar_ingreso_neon(nuevo):
                st.success("✅ Ingreso guardado correctamente en Neon.")
                st.rerun()
            else:
                st.error(
                    "No se pudo guardar el ingreso. "
                    "Revisá el mensaje de error anterior."
                )

    # ==========================================
    # INGRESOS REGISTRADOS
    # ==========================================
    st.divider()
    st.subheader("📋 Ingresos registrados")

    try:
        df = cargar_ingresos_desde_neon()
    except Exception as e:
        st.error(f"No se pudieron actualizar los ingresos: {e}")
        return

    if df.empty:
        st.info("Todavía no hay ingresos registrados.")
        return

    total = pd.to_numeric(
        df["Monto"], errors="coerce"
    ).fillna(0).sum()

    st.metric("💰 Total de ingresos", f"$ {total:,.2f}")

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🗑️ Eliminar un ingreso")

    for _, fila in df.iterrows():
        id_ingreso = str(fila["ID"])

        col_info, col_boton = st.columns([5, 1])

        with col_info:
            st.write(
                f"📅 {fila['Fecha']} | "
                f"**{fila['Cliente']}** | "
                f"{fila['Servicio']} | "
                f"$ {float(fila['Monto'] or 0):,.2f}"
            )

        with col_boton:
            if st.button(
                "🗑️ Borrar",
                key=f"borrar_ingreso_{id_ingreso}",
            ):
                if eliminar_ingreso_neon(id_ingreso):
                    st.success("Ingreso eliminado correctamente.")
                    st.rerun()
                else:
                    st.error("No se pudo eliminar el ingreso.")