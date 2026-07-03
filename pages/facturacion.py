import streamlit as st
import pandas as pd
from database import get_conn

def pantalla_facturacion():

    st.title("🧾 Nueva Factura")

    conn = get_conn()

    clientes = pd.read_sql(
        "SELECT id,nombre FROM clientes ORDER BY nombre",
        conn
    )

    productos = pd.read_sql(
        "SELECT id,nombre,precio FROM productos ORDER BY nombre",
        conn
    )

    cliente = st.selectbox(
        "Cliente",
        clientes["nombre"]
    )

    producto = st.selectbox(
        "Producto",
        productos["nombre"]
    )

    cantidad = st.number_input(
        "Cantidad",
        min_value=1.0,
        value=1.0
    )

    precio = productos.loc[
        productos["nombre"] == producto,
        "precio"
    ].iloc[0]

    st.write(f"Precio: ${precio:,.2f}")

    total = cantidad * precio

    st.subheader(f"TOTAL: ${total:,.2f}")

    if st.button("Guardar Factura"):

        st.success("La siguiente etapa será guardar la factura en la base de datos.")