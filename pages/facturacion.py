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

        cur = conn.cursor()

        # Obtener IDs
        cliente_id = clientes.loc[
            clientes["nombre"] == cliente,
            "id"
        ].iloc[0]

        producto_id = productos.loc[
            productos["nombre"] == producto,
            "id"
        ].iloc[0]

        # Guardar factura
        cur.execute("""
            INSERT INTO facturas
            (numero, cliente_id, usuario_id, total, estado)
            VALUES (%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            "FAC-0001",
            cliente_id,
            1,
            total,
            "PENDIENTE"
        ))

        factura_id = cur.fetchone()[0]

        # Guardar detalle
        cur.execute("""
            INSERT INTO detalle_factura
            (factura_id, producto_id, cantidad, precio_unitario, subtotal)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            factura_id,
            producto_id,
            cantidad,
            precio,
            total
        ))

        # Descontar stock
        cur.execute("""
            UPDATE productos
            SET stock = stock - %s
            WHERE id = %s
        """, (
            cantidad,
            producto_id
        ))

        conn.commit()

        st.success("✅ Factura guardada correctamente")
        st.rerun()