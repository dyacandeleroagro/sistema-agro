import streamlit as st
import pandas as pd
from database import get_conn

def pantalla_facturacion():

    st.title("🧾 Facturación")

    conn = get_conn()

    clientes = pd.read_sql(
        "SELECT id, nombre FROM clientes ORDER BY nombre",
        conn
    )

    servicios = pd.read_sql(
        "SELECT id, nombre, precio FROM productos ORDER BY nombre",
        conn
    )

    if clientes.empty:
        st.warning("No hay clientes cargados.")
        return

    if servicios.empty:
        st.warning("No hay servicios cargados.")
        return

    cliente = st.selectbox(
        "Cliente",
        clientes["nombre"].tolist()
    )

    servicio = st.selectbox(
        "Servicio",
        servicios["nombre"].tolist()
    )

    cantidad = st.number_input(
        "Cantidad",
        min_value=1.0,
        value=1.0
    )

    fila = servicios[servicios["nombre"] == servicio].iloc[0]
    producto_id = int(fila["id"])
    precio = float(fila["precio"])

    total = cantidad * precio

    st.write(f"Precio unitario: ${precio:,.2f}")
    st.subheader(f"TOTAL: ${total:,.2f}")

    if st.button("Guardar Factura"):

        try:

            cur = conn.cursor()

            cliente_id = int(
                clientes.loc[
                    clientes["nombre"] == cliente,
                    "id"
                ].iloc[0]
            )

            numero = f"FAC-{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"

            cur.execute("""
                INSERT INTO facturas
                (numero, cliente_id, usuario_id, total, estado)
                VALUES (%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                numero,
                cliente_id,
                1,
                total,
                "PENDIENTE"
            ))

            factura_id = cur.fetchone()[0]

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

        except Exception as e:

            conn.rollback()
            st.error(str(e))