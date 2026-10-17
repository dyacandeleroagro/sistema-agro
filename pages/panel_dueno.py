import streamlit as st
import pandas as pd
import os


def leer_csv(nombre, columnas=None):

    if os.path.exists(nombre):
        return pd.read_csv(nombre)

    return pd.DataFrame(columns=columnas if columnas else [])



def pantalla_panel_dueno():

    st.header("👑 Panel de Control del Dueño")


    # ==========================
    # CARGAR DATOS
    # ==========================

    ingresos = leer_csv(
        "registro_ingresos.csv"
    )

    gastos = leer_csv(
        "datos_facturas.csv"
    )

    combustible = leer_csv(
        "registro_combustible.csv"
    )

    agenda = leer_csv(
        "agenda.csv"
    )

    pagos = leer_csv(
        "registro_pagos_empleados.csv"
    )

    telemetria = leer_csv(
        "registro_telemetria.csv"
    )



    # ==========================
    # FINANZAS
    # ==========================

    st.subheader("💰 Resumen Financiero")


    total_ingresos = 0

    if not ingresos.empty:

        total_ingresos = ingresos[
            "Monto Total (ARS)"
        ].sum()


    total_gastos = 0

    if not gastos.empty:

        total_gastos = gastos[
            "Monto (ARS)"
        ].sum()


    total_combustible = 0

    if not combustible.empty:

        total_combustible = combustible[
            "Total"
        ].sum()


    resultado = (
        total_ingresos
        -
        total_gastos
        -
        total_combustible
    )



    c1,c2,c3,c4 = st.columns(4)


    with c1:

        st.metric(
            "💰 Ingresos",
            f"$ {total_ingresos:,.0f}"
        )


    with c2:

        st.metric(
            "🧾 Gastos",
            f"$ {total_gastos:,.0f}"
        )


    with c3:

        st.metric(
            "⛽ Combustible",
            f"$ {total_combustible:,.0f}"
        )


    with c4:

        st.metric(
            "📈 Resultado",
            f"$ {resultado:,.0f}"
        )



    st.divider()



    # ==========================
    # OPERACIONES
    # ==========================

    st.subheader("🚜 Operaciones")


    hectareas = 0

    litros = 0


    if not telemetria.empty:

        hectareas = telemetria[
            "Has Trabajadas"
        ].sum()


        litros = telemetria[
            "Gasoil Consumido (L)"
        ].sum()



    o1,o2 = st.columns(2)


    with o1:

        st.metric(
            "🌾 Hectáreas trabajadas",
            f"{hectareas:,.1f} Has"
        )


    with o2:

        st.metric(
            "⛽ Litros consumidos",
            f"{litros:,.0f} L"
        )



    st.divider()



    # ==========================
    # ALERTAS
    # ==========================

    st.subheader("🔔 Alertas")


    alertas = 0


    if not agenda.empty:

        pendientes = agenda[
            agenda["Estado"].str.contains(
                "Pendiente",
                na=False
            )
        ]


        if not pendientes.empty:

            alertas += len(pendientes)

            for _, fila in pendientes.iterrows():

                st.warning(
                    f"📅 {fila['Fecha']} - {fila['Título']}"
                )



    if not gastos.empty:

        deudas = gastos[
            gastos["Estado Pago"]
            ==
            "Pendiente de Pago"
        ]


        if not deudas.empty:

            alertas += len(deudas)

            st.error(
                f"🧾 Hay {len(deudas)} proveedores pendientes"
            )



    if alertas == 0:

        st.success(
            "✅ No hay alertas pendientes"
        )



    st.divider()



    # ==========================
    # PERSONAL
    # ==========================

    st.subheader("👥 Personal")


    pagos_pendientes = 0


    if not pagos.empty:

        pendientes = pagos[
            pagos["Estado Pago"]
            ==
            "Pendiente"
        ]


        if not pendientes.empty:

            pagos_pendientes = pendientes[
                "Monto (ARS)"
            ].sum()



    st.metric(
        "💵 Pagos pendientes personal",
        f"$ {pagos_pendientes:,.0f}"
    )