import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st
import pdfplumber

from database import get_conn


CATEGORIAS = [
    "Pendiente de clasificar",
    "Cobro de cliente",
    "Venta de cosecha",
    "Servicio / trabajo",
    "Combustible",
    "Reparación / repuesto",
    "Sueldos / jornales",
    "Seguro",
    "Impuestos",
    "Comisiones bancarias",
    "Proveedor / compra",
    "Transferencia entre cuentas",
    "Extracción / efectivo",
    "Gasto personal",
    "Otro",
]
TIPOS = ["Ingreso", "Egreso", "Transferencia", "Personal", "Otro"]
ESTADOS = ["Pendiente de revisión contable", "Revisado", "No contabilizar"]


def asegurar_tabla():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS movimientos_bancarios (
                    id TEXT PRIMARY KEY,
                    huella TEXT NOT NULL UNIQUE,
                    fecha DATE NOT NULL,
                    descripcion TEXT NOT NULL DEFAULT '',
                    referencia TEXT NOT NULL DEFAULT '',
                    tipo TEXT NOT NULL DEFAULT 'Otro',
                    categoria TEXT NOT NULL DEFAULT 'Pendiente de clasificar',
                    moneda TEXT NOT NULL DEFAULT 'ARS',
                    monto NUMERIC(16,2) NOT NULL DEFAULT 0,
                    saldo NUMERIC(16,2),
                    estado_revision TEXT NOT NULL DEFAULT 'Pendiente de revisión contable',
                    origen TEXT NOT NULL DEFAULT 'Banco Macro',
                    archivo_origen TEXT NOT NULL DEFAULT '',
                    comprobante_nombre TEXT NOT NULL DEFAULT '',
                    comprobante_mime TEXT NOT NULL DEFAULT '',
                    comprobante_data BYTEA,
                    id_ingreso TEXT,
                    id_gasto TEXT,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
    finally:
        conn.close()


def numero_ar(valor):
    return float(str(valor).replace(".", "").replace(",", "."))


def clasificar(descripcion, tipo):
    d = descripcion.upper()
    if "TRANSF" in d or "TRPRO" in d or "DEBTRF" in d or "EGRESO:" in d:
        return "Transferencia entre cuentas", "Transferencia"
    if "EXTRACCION" in d or "CAJERO" in d:
        return "Extracción / efectivo", "Personal"
    if any(x in d for x in ["DBCR", "IMPUESTO", "IIBB", "AFIP", "IVA", "RETENCION"]):
        return "Impuestos" if any(x in d for x in ["IMPUESTO", "IIBB", "AFIP", "IVA", "RETENCION"]) else "Comisiones bancarias", tipo
    if "SEGURO" in d or "SAN CRISTOBAL" in d or "SANCOR" in d:
        return "Seguro", tipo
    if any(x in d for x in ["COOP GAN", "COOP. GAN", "AGROP", "CIRC.CERRADO", "CREDIN:"]):
        return ("Cobro de cliente" if tipo == "Ingreso" else "Proveedor / compra"), tipo
    if any(x in d for x in ["COMBUST", "YPF", "SHELL", "AXION"]):
        return "Combustible", tipo
    if any(x in d for x in ["MANTENIMIENTO", "COMISION", "PAQUETE"]):
        return "Comisiones bancarias", tipo
    if tipo == "Ingreso":
        return "Pendiente de clasificar", tipo
    return "Pendiente de clasificar", tipo


def extraer_movimientos_pdf(datos, nombre_archivo):
    lineas = []
    with pdfplumber.open(__import__("io").BytesIO(datos)) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            lineas.extend(texto.splitlines())

    # El saldo anterior de la cuenta corriente permite reconocer débitos y créditos
    # por la variación de saldo, aunque el PDF no mantenga las columnas al extraer texto.
    saldo_anterior = None
    dentro_cuenta_corriente = False
    for linea in lineas:
        if "CUENTA CORRIENTE BANCARIA NRO" in linea.upper():
            dentro_cuenta_corriente = True
        if dentro_cuenta_corriente and "SALDO ULTIMO EXTRACTO" in linea.upper():
            m = re.search(r"([\d.]+,\d{2})\s*$", linea)
            if m:
                saldo_anterior = numero_ar(m.group(1))
                break

    patron_fecha = re.compile(r"^\s*(\d{2}/\d{2}/\d{2})\s+(.+?)\s*$")
    patron_importe = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}")
    movimientos = []
    dentro_cuenta_corriente = False
    for linea in lineas:
        if "CUENTA CORRIENTE BANCARIA NRO" in linea.upper():
            dentro_cuenta_corriente = True
        if not dentro_cuenta_corriente:
            continue
        m = patron_fecha.match(linea)
        if not m:
            continue
        fecha_txt, resto = m.groups()
        importes = patron_importe.findall(resto)
        if len(importes) < 2:
            continue
        try:
            importe_linea = numero_ar(importes[-2])
            saldo = numero_ar(importes[-1])
        except Exception:
            continue
        descripcion = resto
        # Retira del final los dos importes (importe del movimiento y saldo).
        idx = resto.rfind(importes[-2])
        descripcion = resto[:idx].strip()
        # Evitar tomar renglones que no son movimientos de una cuenta.
        if not descripcion or "SALDO" in descripcion.upper():
            saldo_anterior = saldo
            continue
        if saldo_anterior is None:
            # Sin saldo inicial no es seguro inferir el sentido del movimiento.
            saldo_anterior = saldo
            continue
        delta = round(saldo - saldo_anterior, 2)
        if abs(delta) < 0.005:
            saldo_anterior = saldo
            continue
        tipo = "Ingreso" if delta > 0 else "Egreso"
        monto = abs(delta)
        saldo_anterior = saldo
        fecha = date(2000 + int(fecha_txt[-2:]), int(fecha_txt[3:5]), int(fecha_txt[:2]))
        # La referencia se conserva como texto íntegro; evita perder códigos del banco.
        categoria, tipo_sugerido = clasificar(descripcion, tipo)
        base = f"{fecha.isoformat()}|{descripcion.upper()}|{monto:.2f}|{tipo}"
        huella = hashlib.sha256(base.encode("utf-8")).hexdigest()
        movimientos.append({
            "id": str(uuid.uuid4()),
            "huella": huella,
            "fecha": fecha,
            "descripcion": descripcion,
            "referencia": "",
            "tipo": tipo_sugerido,
            "categoria": categoria,
            "moneda": "ARS",
            "monto": monto,
            "saldo": saldo,
            "estado_revision": "Pendiente de revisión contable",
            "origen": "Banco Macro",
            "archivo_origen": nombre_archivo,
        })
    return movimientos


def importar_movimientos(movimientos):
    conn = get_conn()
    insertados = 0
    duplicados = 0
    try:
        with conn.cursor() as cur:
            for m in movimientos:
                cur.execute("""
                    INSERT INTO movimientos_bancarios
                    (id, huella, fecha, descripcion, referencia, tipo, categoria,
                     moneda, monto, saldo, estado_revision, origen, archivo_origen)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (huella) DO NOTHING
                """, (
                    m["id"], m["huella"], m["fecha"], m["descripcion"], m["referencia"],
                    m["tipo"], m["categoria"], m["moneda"], m["monto"], m["saldo"],
                    m["estado_revision"], m["origen"], m["archivo_origen"]
                ))
                if cur.rowcount:
                    insertados += 1
                else:
                    duplicados += 1
        conn.commit()
        return insertados, duplicados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cargar_movimientos():
    conn = get_conn()
    try:
        return pd.read_sql("""
            SELECT id, fecha, descripcion, referencia, tipo, categoria, moneda,
                   monto, saldo, estado_revision, origen, archivo_origen,
                   comprobante_nombre, comprobante_mime, comprobante_data,
                   id_ingreso, id_gasto
            FROM movimientos_bancarios
            ORDER BY fecha DESC, creado_en DESC
        """, conn)
    finally:
        conn.close()


def actualizar_movimiento(mid, tipo, categoria, estado):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE movimientos_bancarios
                SET tipo=%s, categoria=%s, estado_revision=%s, actualizado_en=NOW()
                WHERE id=%s
            """, (tipo, categoria, estado, mid))
        conn.commit()
    finally:
        conn.close()


def guardar_comprobante(mid, archivo):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE movimientos_bancarios
                SET comprobante_nombre=%s, comprobante_mime=%s,
                    comprobante_data=%s, actualizado_en=NOW()
                WHERE id=%s
            """, (archivo.name, archivo.type or "application/octet-stream", archivo.getvalue(), mid))
        conn.commit()
    finally:
        conn.close()


def contabilizar(mid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fecha, descripcion, tipo, categoria, moneda, monto,
                       comprobante_nombre, comprobante_data
                FROM movimientos_bancarios WHERE id=%s FOR UPDATE
            """, (mid,))
            row = cur.fetchone()
            if not row:
                raise ValueError("No se encontró el movimiento.")
            fecha, descripcion, tipo, categoria, moneda, monto, comprobante_nombre, comprobante_data = row
            if tipo == "Ingreso":
                ingreso_id = "BAN-" + mid[:12]
                cur.execute("""
                    INSERT INTO ingresos_trabajos
                    (id, fecha, cliente, servicio, lote, hectareas, monto, detalle)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (ingreso_id, fecha, "Por identificar", "Ingreso bancario",
                      "", 0, monto, f"Importado desde Banco Macro: {descripcion}"))
                cur.execute("""
                    UPDATE movimientos_bancarios SET id_ingreso=%s,
                    estado_revision='Contabilizado', actualizado_en=NOW() WHERE id=%s
                """, (ingreso_id, mid))
            elif tipo == "Egreso":
                gasto_id = "BAN-" + mid[:12]
                cur.execute("""
                    INSERT INTO gastos_comerciales
                    (id_gasto, fecha_registro, proveedor, monto_original, moneda,
                     monto_ars, categoria, lote_asignado, estado_pago,
                     archivo_comprobante, comprobante_data)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id_gasto) DO NOTHING
                """, (gasto_id, fecha, descripcion, monto, moneda, monto,
                      categoria, "", "Pendiente de revisión", comprobante_nombre,
                      comprobante_data))
                cur.execute("""
                    UPDATE movimientos_bancarios SET id_gasto=%s,
                    estado_revision='Contabilizado', actualizado_en=NOW() WHERE id=%s
                """, (gasto_id, mid))
            else:
                raise ValueError("Solo se pueden contabilizar movimientos clasificados como Ingreso o Egreso. Transferencias y movimientos personales quedan fuera de la contabilidad.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def pantalla_movimientos_bancarios():
    st.header("🏦 Movimientos bancarios")
    st.caption("Importación del extracto a Neon. Los movimientos quedan pendientes de revisión; nada se contabiliza sin confirmación.")

    try:
        asegurar_tabla()
    except Exception as e:
        st.error(f"No se pudo preparar la tabla en Neon: {e}")
        st.info("Verificá que la conexión de Neon esté configurada en Secrets como `db`.")
        return

    with st.expander("📄 Importar extracto bancario PDF", expanded=True):
        archivo = st.file_uploader("Seleccioná el extracto PDF", type=["pdf"], key="pdf_mov_bancarios")
        if archivo is not None:
            st.caption(f"Archivo seleccionado: {archivo.name} · {archivo.size:,} bytes")
            if st.button("Importar y guardar en Neon", type="primary", key="btn_importar_mov_bancarios"):
                try:
                    movimientos = extraer_movimientos_pdf(archivo.getvalue(), archivo.name)
                    if not movimientos:
                        st.warning("No se detectaron movimientos con un formato compatible. No se guardó nada.")
                    else:
                        nuevos, repetidos = importar_movimientos(movimientos)
                        st.success(f"Importación terminada: {nuevos} nuevos y {repetidos} duplicados omitidos.")
                        st.rerun()
                except Exception as e:
                    st.error(f"No se pudo importar el PDF: {e}")

    try:
        df = cargar_movimientos()
    except Exception as e:
        st.error(f"No se pudieron cargar los movimientos desde Neon: {e}")
        return

    if df.empty:
        st.info("Todavía no hay movimientos importados.")
        return

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    mes_options = sorted(df["fecha"].dropna().dt.strftime("%Y-%m").unique(), reverse=True)
    mes = st.selectbox("Mes", ["Todos"] + mes_options)
    filtrado = df if mes == "Todos" else df[df["fecha"].dt.strftime("%Y-%m") == mes]
    total_ingresos = filtrado.loc[filtrado["tipo"] == "Ingreso", "monto"].sum()
    total_egresos = filtrado.loc[filtrado["tipo"] == "Egreso", "monto"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Movimientos", len(filtrado))
    c2.metric("Ingresos identificados", f"$ {total_ingresos:,.2f}")
    c3.metric("Egresos identificados", f"$ {total_egresos:,.2f}")

    st.subheader("Movimientos guardados")
    st.caption("Revisá tipo y categoría. Los movimientos personales o transferencias no se contabilizan en Ingresos/Gastos.")
    for _, fila in filtrado.iterrows():
        mid = str(fila["id"])
        fecha_txt = fila["fecha"].strftime("%d/%m/%Y") if pd.notna(fila["fecha"]) else "Sin fecha"
        with st.expander(f"{fecha_txt} · $ {float(fila['monto']):,.2f} · {str(fila['descripcion'])[:90]}"):
            st.write(f"**Descripción:** {fila['descripcion']}")
            st.write(f"**Saldo posterior:** $ {float(fila['saldo']):,.2f}" if pd.notna(fila["saldo"]) else "Saldo no disponible")
            if fila.get("id_ingreso"):
                st.caption(f"Vinculado a ingreso: {fila['id_ingreso']}")
            if fila.get("id_gasto"):
                st.caption(f"Vinculado a gasto: {fila['id_gasto']}")
            col1, col2, col3 = st.columns(3)
            with col1:
                tipo_actual = fila["tipo"] if fila["tipo"] in TIPOS else "Otro"
                tipo = st.selectbox("Tipo", TIPOS, index=TIPOS.index(tipo_actual), key=f"tipo_{mid}")
            with col2:
                cat_actual = fila["categoria"] if fila["categoria"] in CATEGORIAS else CATEGORIAS[0]
                categoria = st.selectbox("Categoría", CATEGORIAS, index=CATEGORIAS.index(cat_actual), key=f"cat_{mid}")
            with col3:
                if fila["estado_revision"] == "Contabilizado":
                    st.text_input("Estado", value="Contabilizado", disabled=True, key=f"estado_{mid}")
                    estado = "Contabilizado"
                else:
                    estado_actual = fila["estado_revision"] if fila["estado_revision"] in ESTADOS else ESTADOS[0]
                    estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(estado_actual), key=f"estado_{mid}")
            if fila["estado_revision"] != "Contabilizado":
                if st.button("Guardar revisión", key=f"guardar_rev_{mid}"):
                    try:
                        actualizar_movimiento(mid, tipo, categoria, estado)
                        st.success("Revisión guardada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo guardar la revisión: {e}")

            comprobante = st.file_uploader("Adjuntar comprobante (PDF o imagen)", type=["pdf", "png", "jpg", "jpeg", "webp"], key=f"comprobante_{mid}")
            if comprobante is not None and st.button("Guardar comprobante", key=f"guardar_comp_{mid}"):
                try:
                    guardar_comprobante(mid, comprobante)
                    st.success("Comprobante guardado en Neon.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar el comprobante: {e}")
            if fila.get("comprobante_data") is not None:
                st.download_button(
                    "Descargar comprobante guardado",
                    data=bytes(fila["comprobante_data"]),
                    file_name=str(fila["comprobante_nombre"] or "comprobante"),
                    mime=str(fila["comprobante_mime"] or "application/octet-stream"),
                    key=f"descargar_comp_{mid}",
                )

            if fila["estado_revision"] != "Contabilizado":
                if st.button("Confirmar y contabilizar", type="primary", key=f"contabilizar_{mid}"):
                    try:
                        # Persistir la revisión elegida antes de contabilizar.
                        actualizar_movimiento(mid, tipo, categoria, "Revisado")
                        contabilizar(mid)
                        st.success("Movimiento contabilizado y vinculado al módulo existente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo contabilizar: {e}")
