import hashlib
import re
import uuid
import io
from datetime import date
from decimal import Decimal, InvalidOperation

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

TIPOS = [
    "Ingreso",
    "Egreso",
    "Transferencia",
    "Personal",
    "Otro",
]

ESTADOS = [
    "Pendiente de revisión contable",
    "Revisado",
    "No contabilizar",
]

# Si pasás plata entre cuentas propias (por ejemplo a tu caja de ahorro),
# poné acá fragmentos del texto que aparece en el extracto, en mayúsculas:
# tu apellido, tu CUIT, el nombre de la otra cuenta, etc.
# Los movimientos que los contengan NO se cargan como ingreso ni gasto.
# Ejemplo: TRANSFERENCIAS_PROPIAS = ["GARCIA JUAN", "20123456789"]
TRANSFERENCIAS_PROPIAS = []


# ==========================================================
# BASE DE DATOS
# ==========================================================

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
                    sentido_bancario TEXT NOT NULL DEFAULT 'Otro',
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

            # Migración segura para la tabla existente.
            # No borra ni reemplaza movimientos anteriores.

            cur.execute("""
                ALTER TABLE movimientos_bancarios
                ADD COLUMN IF NOT EXISTS sentido_bancario
                TEXT NOT NULL DEFAULT 'Otro'
            """)

        conn.commit()

    finally:
        conn.close()


def numero_ar(valor):

    return float(
        str(valor)
        .replace(".", "")
        .replace(",", ".")
    )


# ==========================================================
# CLASIFICACIÓN CONTABLE
# ==========================================================

def _clasificar_base(descripcion, sentido_bancario):

    d = re.sub(
        r"\s+",
        " ",
        str(descripcion or "").upper()
    ).strip()

    sentido_bancario = str(
        sentido_bancario or "Otro"
    ).strip()

    # Extracciones: son salidas bancarias, pero no gastos
    # comerciales automáticos.

    if any(x in d for x in (
        "EXTRACCION",
        "EXTRACCIÓN",
        "CAJERO",
    )):
        return "Extracción / efectivo", "Personal"

    # Transferencias: no se consideran automáticamente
    # ingresos o gastos comerciales.

    if any(x in d for x in (
        "TRANSF",
        "TRPRO",
        "DEBTRF",
        "TRANSFERENCIA",
    )):
        return (
            "Transferencia entre cuentas",
            "Transferencia"
        )

    # Compras con débito no se clasifican automáticamente
    # como gasto comercial: requieren revisión.

    if any(x in d for x in (
        "COMPRA DEBITO",
        "COMPRA DÉBITO",
        "GASTO PERSONAL",
    )):
        return "Gasto personal", "Personal"

    if any(x in d for x in (
        "COMISION",
        "COMISIÓN",
        "PAQUETE BANCARIO",
        "ADM.VALORES",
    )):
        return "Comisiones bancarias", "Egreso"

    if any(x in d for x in (
        "RETENCION IVA",
        "RETENCIÓN IVA",
        "PERCEPCION IVA",
        "PERCEPCIÓN IVA",
        "IIBB",
        "AFIP",
        "IMPUESTO",
        "TASA GRAL",
        "DBCR",
    )):
        return "Impuestos", "Egreso"

    if any(x in d for x in (
        "SEGURO",
        "SAN CRISTOBAL",
        "SAN CRISTÓBAL",
        "SANCOR",
    )):
        return "Seguro", "Egreso"

    if any(x in d for x in (
        "COMBUST",
        "YPF",
        "SHELL",
        "AXION",
        "GNC",
        "ESTACION DE SERVICIO",
        "ESTACIÓN DE SERVICIO",
    )):
        return "Combustible", "Egreso"

    if any(x in d for x in (
        "REPUESTO",
        "TALLER",
        "MECANICA",
        "MECÁNICA",
        "REPARACION",
        "REPARACIÓN",
        "NEUMATICO",
        "NEUMÁTICO",
    )):
        return "Reparación / repuesto", "Egreso"

    if any(x in d for x in (
        "SUELDO",
        "JORNAL",
        "HABERES",
        "LIQUIDACION SUELDO",
        "LIQUIDACIÓN SUELDO",
    )):
        return "Sueldos / jornales", "Egreso"

    if sentido_bancario == "Ingreso":

        if any(x in d for x in (
            "COBRO CLIENTE",
            "COBRO DE CLIENTE",
            "PAGO CLIENTE",
            "PAGO DE CLIENTE",
        )):
            return "Cobro de cliente", "Ingreso"

        if any(x in d for x in (
            "VENTA DE CEREAL",
            "VENTA DE GRANOS",
            "LIQUIDACION GRANOS",
            "LIQUIDACIÓN GRANOS",
            "ACOPIO DE CEREALES",
            "COSECHA",
        )):
            return "Venta de cosecha", "Ingreso"

        if any(x in d for x in (
            "COBRO SERVICIO",
            "COBRO DE SERVICIO",
            "SERVICIO PRESTADO",
        )):
            return "Servicio / trabajo", "Ingreso"

    if sentido_bancario == "Egreso" and any(x in d for x in (
        "PROVEEDOR",
        "COMPRA INSUMOS",
        "COMPRA DE INSUMOS",
    )):
        return "Proveedor / compra", "Egreso"

    return "Pendiente de clasificar", sentido_bancario


def clasificar(descripcion, sentido_bancario):
    """
    Regla automática:
      - Lo que SALE del banco  -> Egreso  -> gastos comerciales.
      - Lo que ENTRA al banco  -> Ingreso -> ingresos por trabajos.
    Salvedades:
      - Extracciones de cajero y compras personales siguen afuera.
      - Transferencias entre cuentas propias (TRANSFERENCIAS_PROPIAS)
        quedan afuera.
      - Reversiones (un crédito que el texto marca como gasto, o al revés)
        quedan afuera para no inflar gastos con plata que entró.
    """

    d = re.sub(
        r"\s+", " ", str(descripcion or "").upper()
    ).strip()

    sentido = str(sentido_bancario or "Otro").strip()

    es_extraccion = any(x in d for x in (
        "EXTRACCION", "EXTRACCIÓN", "CAJERO",
    ))

    es_transferencia = any(x in d for x in (
        "TRANSF", "TRPRO", "DEBTRF", "TRANSFERENCIA",
    ))

    if es_transferencia and not es_extraccion:

        if any(
            str(p).strip().upper() in d
            for p in TRANSFERENCIAS_PROPIAS
            if str(p).strip()
        ):
            return "Transferencia entre cuentas", "Transferencia"

        if sentido == "Ingreso":
            return "Servicio / trabajo", "Ingreso"

        if sentido == "Egreso":
            return "Proveedor / compra", "Egreso"

    categoria, tipo = _clasificar_base(descripcion, sentido)

    # Reversión: el texto dice gasto pero entró plata (o al revés).
    if tipo in ("Ingreso", "Egreso") and sentido in ("Ingreso", "Egreso"):
        if tipo != sentido:
            return "Otro", "Otro"

    # Lo que antes quedaba "Pendiente de clasificar" ahora sigue
    # el sentido bancario.
    if categoria == "Pendiente de clasificar":

        if sentido == "Ingreso":
            return "Servicio / trabajo", "Ingreso"

        if sentido == "Egreso":
            return "Proveedor / compra", "Egreso"

    return categoria, tipo


# ==========================================================
# IMPORTACIÓN DEL PDF BANCARIO
# ==========================================================

def extraer_movimientos_pdf(datos, nombre_archivo):

    lineas = []

    with pdfplumber.open(io.BytesIO(datos)) as pdf:

        for pagina in pdf.pages:

            texto = pagina.extract_text() or ""
            lineas.extend(texto.splitlines())

    saldo_anterior = None
    dentro_cuenta_corriente = False

    for linea in lineas:

        if "CUENTA CORRIENTE BANCARIA NRO" in linea.upper():
            dentro_cuenta_corriente = True

        if (
            dentro_cuenta_corriente
            and "SALDO ULTIMO EXTRACTO" in linea.upper()
        ):

            m = re.search(
                r"([\d.]+,\d{2})\s*$",
                linea
            )

            if m:
                saldo_anterior = numero_ar(m.group(1))
                break

    patron_fecha = re.compile(
        r"^\s*(\d{2}/\d{2}/\d{2})\s+(.+?)\s*$"
    )

    patron_importe = re.compile(
        r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}"
    )

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

        idx = resto.rfind(importes[-2])
        descripcion = resto[:idx].strip()

        if not descripcion or "SALDO" in descripcion.upper():
            saldo_anterior = saldo
            continue

        if saldo_anterior is None:
            saldo_anterior = saldo
            continue

        delta = round(saldo - saldo_anterior, 2)

        if abs(delta) < 0.005:
            saldo_anterior = saldo
            continue

        if abs(abs(delta) - abs(importe_linea)) > 0.01:

            raise ValueError(
                "Importación cancelada por seguridad: "
                "el importe del movimiento no coincide "
                "con la variación del saldo. "
                f"Línea: {linea}. "
                f"Importe de línea: $ {abs(importe_linea):,.2f}; "
                f"variación calculada: $ {abs(delta):,.2f}. "
                "No se guardó esta importación."
            )

        # SENTIDO REAL DEL DINERO EN EL BANCO.
        sentido_bancario = (
            "Ingreso" if delta > 0 else "Egreso"
        )

        monto = abs(delta)

        saldo_anterior = saldo

        fecha = date(
            2000 + int(fecha_txt[-2:]),
            int(fecha_txt[3:5]),
            int(fecha_txt[:2])
        )

        # CLASIFICACIÓN CONTABLE SEPARADA.
        categoria, tipo_sugerido = clasificar(
            descripcion,
            sentido_bancario
        )

        base = (
            f"{fecha.isoformat()}|"
            f"{descripcion.upper()}|"
            f"{monto:.2f}|{sentido_bancario}"
        )

        huella = hashlib.sha256(
            base.encode("utf-8")
        ).hexdigest()

        movimientos.append({

            "id": str(uuid.uuid4()),
            "huella": huella,
            "fecha": fecha,
            "descripcion": descripcion,
            "referencia": "",

            # Clasificación contable.
            "tipo": tipo_sugerido,
            "categoria": categoria,

            # Sentido real del movimiento bancario.
            "sentido_bancario": sentido_bancario,

            "moneda": "ARS",
            "monto": monto,
            "saldo": saldo,
            "estado_revision": "Pendiente de revisión contable",
            "origen": "Banco Macro",
            "archivo_origen": nombre_archivo,

        })

    return movimientos


# ==========================================================
# GUARDAR MOVIMIENTOS EN NEON
# ==========================================================

def importar_movimientos(movimientos):

    conn = get_conn()

    insertados = 0
    actualizados = 0
    ids_nuevos = []

    try:
        with conn.cursor() as cur:

            for m in movimientos:

                cur.execute("""
                    INSERT INTO movimientos_bancarios (
                        id,
                        huella,
                        fecha,
                        descripcion,
                        referencia,
                        tipo,
                        sentido_bancario,
                        categoria,
                        moneda,
                        monto,
                        saldo,
                        estado_revision,
                        origen,
                        archivo_origen
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (huella)
                    DO UPDATE SET
                        sentido_bancario = EXCLUDED.sentido_bancario,
                        saldo = EXCLUDED.saldo,
                        actualizado_en = NOW()
                    RETURNING (xmax = 0) AS fue_insertado
                """, (
                    m["id"],
                    m["huella"],
                    m["fecha"],
                    m["descripcion"],
                    m["referencia"],
                    m["tipo"],
                    m["sentido_bancario"],
                    m["categoria"],
                    m["moneda"],
                    m["monto"],
                    m["saldo"],
                    m["estado_revision"],
                    m["origen"],
                    m["archivo_origen"],
                ))

                resultado = cur.fetchone()

                if resultado and resultado[0]:
                    insertados += 1
                    ids_nuevos.append(m["id"])
                else:
                    actualizados += 1

        conn.commit()

        return insertados, actualizados, ids_nuevos

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
# ==========================================================
# CONSULTA Y ACTUALIZACIÓN DE MOVIMIENTOS
# ==========================================================

def cargar_movimientos():

    conn = get_conn()

    try:

        return pd.read_sql("""
            SELECT
                id,
                fecha,
                descripcion,
                referencia,
                tipo,
                sentido_bancario,
                categoria,
                moneda,
                monto,
                saldo,
                estado_revision,
                origen,
                archivo_origen,
                comprobante_nombre,
                comprobante_mime,
                comprobante_data,
                id_ingreso,
                id_gasto
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
                SET tipo = %s,
                    categoria = %s,
                    estado_revision = %s,
                    actualizado_en = NOW()
                WHERE id = %s
            """, (
                tipo,
                categoria,
                estado,
                mid,
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def guardar_comprobante(mid, archivo):

    conn = get_conn()

    try:

        with conn.cursor() as cur:

            cur.execute("""
                UPDATE movimientos_bancarios
                SET comprobante_nombre = %s,
                    comprobante_mime = %s,
                    comprobante_data = %s,
                    actualizado_en = NOW()
                WHERE id = %s
            """, (
                archivo.name,
                archivo.type or "application/octet-stream",
                archivo.getvalue(),
                mid,
            ))

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==========================================================
# CONTABILIZACIÓN INDIVIDUAL SEGURA
# ==========================================================

def contabilizar(mid, permitir_pendiente=False):

    conn = None

    categorias_personales_o_no_contables = {
        "Gasto personal",
        "Transferencia entre cuentas",
        "Extracción / efectivo",
        "Pendiente de clasificar",
        "Otro",
    }

    categorias_de_ingreso = {
        "Cobro de cliente",
        "Venta de cosecha",
        "Servicio / trabajo",
    }

    categorias_de_egreso = {
        "Combustible",
        "Reparación / repuesto",
        "Sueldos / jornales",
        "Seguro",
        "Impuestos",
        "Comisiones bancarias",
        "Proveedor / compra",
    }

    try:

        conn = get_conn()

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    fecha,
                    descripcion,
                    tipo,
                    categoria,
                    moneda,
                    monto,
                    comprobante_nombre,
                    comprobante_data,
                    estado_revision,
                    id_ingreso,
                    id_gasto
                FROM movimientos_bancarios
                WHERE id = %s
                FOR UPDATE
            """, (mid,))

            row = cur.fetchone()

            if not row:
                raise ValueError(
                    "No se encontró el movimiento bancario."
                )

            (
                fecha,
                descripcion,
                tipo,
                categoria,
                moneda,
                monto,
                comprobante_nombre,
                comprobante_data,
                estado_revision,
                id_ingreso_existente,
                id_gasto_existente,
            ) = row

            # Verificar contabilizaciones anteriores.

            if estado_revision == "Contabilizado":

                if tipo == "Ingreso" and id_ingreso_existente:

                    cur.execute("""
                        SELECT 1
                        FROM ingresos_trabajos
                        WHERE id = %s
                    """, (id_ingreso_existente,))

                    if cur.fetchone():
                        conn.commit()
                        return id_ingreso_existente

                elif tipo == "Egreso" and id_gasto_existente:

                    cur.execute("""
                        SELECT 1
                        FROM gastos_comerciales
                        WHERE id_gasto = %s
                    """, (id_gasto_existente,))

                    if cur.fetchone():
                        conn.commit()
                        return id_gasto_existente

                raise ValueError(
                    "El movimiento figura como contabilizado, "
                    "pero su registro vinculado no existe. "
                    "Requiere revisión manual."
                )

            estados_permitidos = {"Revisado"}
            if permitir_pendiente:
                estados_permitidos.add("Pendiente de revisión contable")

            if estado_revision not in estados_permitidos:
                raise ValueError(
                    "El movimiento debe estar revisado o ser procesado "
                    "por la contabilización masiva."
                )

            tipo = str(tipo or "").strip()
            categoria = str(categoria or "").strip()
            moneda = str(moneda or "").strip().upper()

            if categoria in categorias_personales_o_no_contables:

                raise ValueError(
                    f"La categoría '{categoria}' no se puede "
                    "contabilizar como ingreso o gasto comercial."
                )

            if tipo not in ("Ingreso", "Egreso"):

                raise ValueError(
                    "Solo se contabilizan ingresos y egresos. "
                    "Personales y transferencias quedan afuera."
                )

            if (
                tipo == "Ingreso"
                and categoria not in categorias_de_ingreso
            ):

                raise ValueError(
                    "La categoría no está habilitada "
                    "para contabilizar ingresos."
                )

            if (
                tipo == "Egreso"
                and categoria not in categorias_de_egreso
            ):

                raise ValueError(
                    "La categoría no está habilitada "
                    "para contabilizar gastos."
                )

            if moneda != "ARS":

                raise ValueError(
                    "La contabilización automática solo admite ARS."
                )

            monto_decimal = Decimal(str(monto))

            if (
                not monto_decimal.is_finite()
                or monto_decimal <= 0
            ):

                raise ValueError(
                    "El importe debe ser válido y mayor que cero."
                )

            if id_ingreso_existente or id_gasto_existente:

                raise ValueError(
                    "El movimiento ya tiene un vínculo contable. "
                    "Se requiere revisar ese vínculo."
                )

            registro_id = "BAN-" + str(mid)[:12]

            if tipo == "Ingreso":

                cur.execute("""
                    INSERT INTO ingresos_trabajos (
                        id,
                        fecha,
                        cliente,
                        servicio,
                        lote,
                        hectareas,
                        monto,
                        detalle
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                """, (
                    registro_id,
                    fecha,
                    "Por identificar",
                    "Ingreso bancario",
                    "",
                    0,
                    monto_decimal,
                    f"Importado desde Banco Macro: {descripcion}",
                ))

                insertado = cur.fetchone()

                if not insertado:

                    raise ValueError(
                        f"Ya existe el ingreso {registro_id}. "
                        "No se generó un duplicado."
                    )

                cur.execute("""
                    UPDATE movimientos_bancarios
                    SET id_ingreso = %s,
                        estado_revision = 'Contabilizado',
                        actualizado_en = NOW()
                    WHERE id = %s
                """, (
                    registro_id,
                    mid,
                ))

            else:

                # Comprobar el identificador antes de insertar. Esto evita
                # depender de que id_gasto tenga un índice UNIQUE en Neon.
                cur.execute("""
                    SELECT 1
                    FROM gastos_comerciales
                    WHERE id_gasto = %s
                    LIMIT 1
                """, (registro_id,))

                if cur.fetchone():
                    raise ValueError(
                        f"Ya existe el gasto {registro_id}. "
                        "Se detuvo para evitar un duplicado."
                    )

                cur.execute("""
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
                        archivo_comprobante,
                        comprobante_data
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id_gasto
                """, (
                    registro_id,
                    fecha,
                    str(descripcion or ""),
                    monto_decimal,
                    moneda,
                    monto_decimal,
                    categoria,
                    "",
                    "Pagado",
                    str(comprobante_nombre or ""),
                    comprobante_data,
                ))

                insertado = cur.fetchone()

                if not insertado:

                    raise ValueError(
                        f"Ya existe el gasto {registro_id}. "
                        "No se generó un duplicado."
                    )

                cur.execute("""
                    UPDATE movimientos_bancarios
                    SET id_gasto = %s,
                        estado_revision = 'Contabilizado',
                        actualizado_en = NOW()
                    WHERE id = %s
                """, (
                    registro_id,
                    mid,
                ))

            if cur.rowcount != 1:

                raise ValueError(
                    "No se pudo actualizar el vínculo del movimiento."
                )

        conn.commit()

        return registro_id

    except Exception:

        if conn:
            conn.rollback()

        raise

    finally:

        if conn:
            conn.close()


# ==========================================================
# CONTABILIZACIÓN MASIVA
# ==========================================================

def contabilizar_clasificados_existentes(df):

    exitosos = 0
    excluidos = 0
    errores = []

    categorias_ingreso = {
        "Cobro de cliente",
        "Venta de cosecha",
        "Servicio / trabajo",
    }

    categorias_egreso = {
        "Combustible",
        "Reparación / repuesto",
        "Sueldos / jornales",
        "Seguro",
        "Impuestos",
        "Comisiones bancarias",
        "Proveedor / compra",
    }

    for _, fila in df.iterrows():

        mid = str(fila["id"])

        tipo = str(fila.get("tipo") or "").strip()
        categoria = str(fila.get("categoria") or "").strip()
        estado = str(fila.get("estado_revision") or "").strip()
        moneda = str(fila.get("moneda") or "").strip().upper()

        if estado not in (
            "Pendiente de revisión contable",
            "Revisado",
        ):
            continue

        if tipo in (
            "Personal",
            "Transferencia",
            "Otro",
        ):
            excluidos += 1
            continue

        if (
            tipo == "Ingreso"
            and categoria not in categorias_ingreso
        ):
            excluidos += 1
            continue

        if (
            tipo == "Egreso"
            and categoria not in categorias_egreso
        ):
            excluidos += 1
            continue

        if tipo not in ("Ingreso", "Egreso"):
            excluidos += 1
            continue

        if moneda != "ARS":
            excluidos += 1
            continue

        id_ingreso = fila.get("id_ingreso")
        id_gasto = fila.get("id_gasto")

        if pd.notna(id_ingreso) and str(id_ingreso).strip():
            excluidos += 1
            continue

        if pd.notna(id_gasto) and str(id_gasto).strip():
            excluidos += 1
            continue

        try:

            contabilizar(mid, permitir_pendiente=True)

            exitosos += 1

        except Exception as e:

            errores.append({
                "id": mid,
                "error": str(e),
            })

    return exitosos, excluidos, errores


def procesar_movimientos_nuevos(ids_nuevos):
    """
    Pasa a Ingresos / Gastos comerciales los movimientos recién
    importados, usando la misma validación de siempre.
    Devuelve (contabilizados, excluidos, errores).
    """

    if not ids_nuevos:
        return 0, 0, []

    df_total = cargar_movimientos()

    df_nuevos = df_total[
        df_total["id"].astype(str).isin([str(i) for i in ids_nuevos])
    ]

    return contabilizar_clasificados_existentes(df_nuevos)


def _pendientes_reclasificables(cur):

    cur.execute("""
        SELECT id, descripcion, sentido_bancario
        FROM movimientos_bancarios
        WHERE estado_revision = 'Pendiente de revisión contable'
          AND categoria IN (
              'Pendiente de clasificar',
              'Transferencia entre cuentas'
          )
          AND COALESCE(id_ingreso, '') = ''
          AND COALESCE(id_gasto, '') = ''
        FOR UPDATE
    """)

    return cur.fetchall()


def contar_pendientes_reclasificables():

    conn = get_conn()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT COUNT(*)
                FROM movimientos_bancarios
                WHERE estado_revision = 'Pendiente de revisión contable'
                  AND categoria IN (
                      'Pendiente de clasificar',
                      'Transferencia entre cuentas'
                  )
                  AND COALESCE(id_ingreso, '') = ''
                  AND COALESCE(id_gasto, '') = ''
            """)

            return cur.fetchone()[0]

    finally:
        conn.close()


def reclasificar_pendientes():
    """
    Aplica la regla automática vigente a movimientos que quedaron sin
    clasificar o como transferencia y todavía no se contabilizaron.
    No toca los Revisado, No contabilizar ni Contabilizado.
    Devuelve los ids reclasificados.
    """

    conn = get_conn()
    ids = []

    try:
        with conn.cursor() as cur:

            for mid, descripcion, sentido in _pendientes_reclasificables(cur):

                categoria, tipo = clasificar(descripcion, sentido)

                cur.execute("""
                    UPDATE movimientos_bancarios
                    SET tipo = %s,
                        categoria = %s,
                        actualizado_en = NOW()
                    WHERE id = %s
                """, (tipo, categoria, mid))

                ids.append(mid)

        conn.commit()
        return ids

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==========================================================
# DIAGNÓSTICO
# ==========================================================

def diagnostico_movimientos(filtrado):

    st.subheader("🔎 Diagnóstico de movimientos")

    st.write("Total de movimientos:", len(filtrado))

    st.markdown("#### Por sentido bancario")

    if "sentido_bancario" in filtrado.columns:

        sentidos = (
            filtrado["sentido_bancario"]
            .fillna("Sin sentido")
            .value_counts()
        )

        for nombre, cantidad in sentidos.items():
            st.write(f"- **{nombre}:** {cantidad}")

    st.markdown("#### Por estado")

    estados = (
        filtrado["estado_revision"]
        .fillna("Sin estado")
        .value_counts()
    )

    for nombre, cantidad in estados.items():
        st.write(f"- **{nombre}:** {cantidad}")

    st.markdown("#### Por tipo contable")

    tipos = (
        filtrado["tipo"]
        .fillna("Sin tipo")
        .value_counts()
    )

    for nombre, cantidad in tipos.items():
        st.write(f"- **{nombre}:** {cantidad}")

    st.markdown("#### Por categoría")

    categorias = (
        filtrado["categoria"]
        .fillna("Sin categoría")
        .value_counts()
    )

    for nombre, cantidad in categorias.items():
        st.write(f"- **{nombre}:** {cantidad}")

    st.markdown("#### Por moneda")

    monedas = (
        filtrado["moneda"]
        .fillna("Sin moneda")
        .value_counts()
    )

    for nombre, cantidad in monedas.items():
        st.write(f"- **{nombre}:** {cantidad}")
# ==========================================================
# ANALIZADOR INDEPENDIENTE DEL RESUMEN
# NO GUARDA NI MODIFICA CONTABILIDAD
# ==========================================================

def generar_analisis_resumen(texto):

    if not texto or not texto.strip():
        return None

    lineas = [
        x.strip()
        for x in texto.splitlines()
        if x.strip()
    ]

    def importe_decimal(valor):
        valor = (
            str(valor)
            .strip()
            .replace("$", "")
            .replace(" ", "")
        )

        valor = valor.replace(".", "").replace(",", ".")
        resultado = Decimal(valor)

        if not resultado.is_finite():
            raise InvalidOperation("Importe no finito")

        return resultado

    patron_fecha = re.compile(
        r"^\s*(\d{2}/\d{2}/\d{2})\s+(.+?)\s*$"
    )

    patron_importe = re.compile(
        r"(?<![\w/])-?\d{1,3}(?:\.\d{3})+,\d{2}|"
        r"(?<![\w/])-?\d+,\d{2}"
    )

    dentro_cuenta = False
    saldo_inicial = None
    saldo_final = None

    movimientos = []
    saldos = []
    errores = []
    destacados = []
    filas_vistas = set()

    for linea in lineas:

        mayus = linea.upper()

        if "CUENTA CORRIENTE BANCARIA NRO" in mayus:
            dentro_cuenta = True
            continue

        if not dentro_cuenta:
            continue

        if (
            "SALDO ULTIMO EXTRACTO" in mayus
            or "SALDO ÚLTIMO EXTRACTO" in mayus
        ):
            importes = patron_importe.findall(linea)

            if importes:
                try:
                    saldo_inicial = importe_decimal(importes[-1])
                    saldos.append((linea, float(saldo_inicial)))
                except (InvalidOperation, ValueError):
                    errores.append(f"Saldo inicial ilegible: {linea}")

            continue

        if (
            "SALDO FINAL AL DIA" in mayus
            or "SALDO FINAL AL DÍA" in mayus
        ):
            importes = patron_importe.findall(linea)

            if importes:
                try:
                    saldo_final = importe_decimal(importes[-1])
                    saldos.append((linea, float(saldo_final)))
                except (InvalidOperation, ValueError):
                    errores.append(f"Saldo final ilegible: {linea}")

            continue

        m = patron_fecha.match(linea)

        if not m:
            continue

        fecha_txt, resto = m.groups()
        importes = patron_importe.findall(resto)

        if len(importes) < 2:
            errores.append(
                "No se identificaron importe y saldo posterior: " + linea
            )
            destacados.append(linea)
            continue

        try:
            importe_linea = abs(importe_decimal(importes[-2]))
            saldo = importe_decimal(importes[-1])

        except (InvalidOperation, ValueError):
            errores.append(f"Importe o saldo ilegible: {linea}")
            destacados.append(linea)
            continue

        posicion = resto.rfind(importes[-2])
        descripcion = resto[:posicion].strip()

        if not descripcion:
            errores.append(f"Movimiento sin descripción: {linea}")
            destacados.append(linea)
            continue

        clave = (
            fecha_txt,
            descripcion.upper(),
            str(saldo),
        )

        if clave in filas_vistas:
            continue

        filas_vistas.add(clave)

        movimientos.append({
            "fecha_txt": fecha_txt,
            "descripcion": descripcion,
            "importe_linea": importe_linea,
            "saldo": saldo,
            "linea": linea,
        })

    ingresos = []
    egresos = []
    sin_clasificar = []
    conceptos_reconocidos = []

    total_ingresos = Decimal("0.00")
    total_egresos = Decimal("0.00")
    variacion_bancaria = Decimal("0.00")

    saldo_previo = saldo_inicial

    for mov in movimientos:

        saldo_actual = mov["saldo"]
        importe_linea = mov["importe_linea"]
        descripcion = mov["descripcion"]
        linea = mov["linea"]

        if saldo_previo is None:
            errores.append(
                "Falta el saldo inicial: no se puede verificar "
                "el sentido ni el importe de este movimiento."
            )

            sin_clasificar.append((linea, float(importe_linea)))
            destacados.append(linea)
            saldo_previo = saldo_actual
            continue

        diferencia = (
            saldo_actual - saldo_previo
        ).quantize(Decimal("0.01"))

        variacion_bancaria += diferencia

        if diferencia == Decimal("0.00"):
            errores.append(
                "El saldo no cambió pese a que aparece "
                f"un movimiento: {linea}"
            )

            sin_clasificar.append((linea, float(importe_linea)))
            destacados.append(linea)
            saldo_previo = saldo_actual
            continue

        if abs(abs(diferencia) - importe_linea) > Decimal("0.01"):
            errores.append(
                "El importe de la línea no coincide con la "
                "variación del saldo. "
                f"Línea: {linea}. "
                f"Importe leído: $ {importe_linea:,.2f}; "
                f"variación del saldo: $ {abs(diferencia):,.2f}."
            )

            sin_clasificar.append((linea, float(importe_linea)))
            destacados.append(linea)
            saldo_previo = saldo_actual
            continue

        monto = abs(diferencia)

        tipo = "Ingreso" if diferencia > 0 else "Egreso"
        d = descripcion.upper()

        if (
            "ACREDITACION CHEQUE REMESAS" in d
            or "ACREDITACIÓN CHEQUE REMESAS" in d
        ):
            concepto = "Acreditación de cheque; origen por confirmar"

        elif (
            "COMISION ADM.VALORES" in d
            or "COMISIÓN ADM.VALORES" in d
        ):
            concepto = "Comisión bancaria por valores al cobro"

        elif (
            "RETENCION IVA" in d
            or "RETENCIÓN IVA" in d
            or "PERCEPCION" in d
            or "PERCEPCIÓN" in d
        ):
            concepto = (
                "Retención/percepción impositiva; "
                "revisar tratamiento contable"
            )

        elif "DBCR" in d and "S/DB" in d:
            concepto = (
                "Débito por tasa/impuesto; "
                "verificar concepto bancario"
            )

        elif "DBCR" in d and "S/CR" in d:
            concepto = (
                "Crédito o reversión de tasa/impuesto; "
                "verificar origen"
            )

        elif (
            "TRANSF" in d
            or "TRPRO" in d
            or "DEBTRF" in d
        ):
            concepto = (
                "Transferencia entrante; contraparte y motivo por confirmar"
                if tipo == "Ingreso"
                else "Transferencia saliente; destinatario y motivo por confirmar"
            )

        elif "CHEQUE" in d:
            concepto = (
                "Movimiento relacionado con cheque; revisar origen"
            )

        else:
            concepto = (
                "Concepto detectado; verificar clasificación comercial"
            )

        conceptos_reconocidos.append((
            linea,
            concepto,
            float(monto)
        ))

        if tipo == "Ingreso":
            total_ingresos += monto
            ingresos.append((linea, float(monto)))
        else:
            total_egresos += monto
            egresos.append((linea, float(monto)))

        saldo_previo = saldo_actual

    variacion = total_ingresos - total_egresos

    conciliacion_calculada = None
    diferencia_conciliacion = None
    conciliado = False

    if saldo_inicial is not None and saldo_final is not None:

        conciliacion_calculada = (
            saldo_inicial + variacion_bancaria
        ).quantize(Decimal("0.01"))

        diferencia_conciliacion = (
            saldo_final - conciliacion_calculada
        ).quantize(Decimal("0.01"))

        conciliado = (
            diferencia_conciliacion == Decimal("0.00")
        )

        if not conciliado:
            errores.append(
                "La conciliación de saldos no coincide. "
                "Revisá movimientos omitidos, páginas faltantes, "
                "orden de las líneas o saldos."
            )

    else:
        errores.append(
            "No se encontraron los saldos inicial y final "
            "de la cuenta. La conciliación completa no puede verificarse."
        )

    destacados = list(dict.fromkeys(destacados))

    return {
        "lineas": lineas,
        "ingresos": ingresos,
        "egresos": egresos,
        "sin_clasificar": sin_clasificar,
        "saldos": saldos,
        "destacados": destacados,
        "conceptos_reconocidos": conceptos_reconocidos,
        "total_ingresos": float(total_ingresos),
        "total_egresos": float(total_egresos),
        "variacion_identificada": float(variacion),
        "saldo_inicial": (
            float(saldo_inicial)
            if saldo_inicial is not None else None
        ),
        "saldo_final": (
            float(saldo_final)
            if saldo_final is not None else None
        ),
        "conciliacion_calculada": (
            float(conciliacion_calculada)
            if conciliacion_calculada is not None else None
        ),
        "diferencia_conciliacion": (
            float(diferencia_conciliacion)
            if diferencia_conciliacion is not None else None
        ),
        "conciliado": conciliado,
        "errores": errores,
        "cantidad_movimientos": len(movimientos),
    }

# ==========================================================
# CONTROL Y RESPALDO SEGURO DEL REINICIO BANCARIO
# ==========================================================

def obtener_estado_reinicio_bancario():
    """
    Consulta los movimientos bancarios y verifica sus vínculos.
    Esta función NO modifica ni elimina información.
    """

    conn = get_conn()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT id, id_ingreso, id_gasto
                FROM movimientos_bancarios
                ORDER BY id
            """)

            movimientos = cur.fetchall()

            ids_ingresos = []
            ids_gastos = []
            errores = []

            for mid, id_ingreso, id_gasto in movimientos:

                esperado = "BAN-" + str(mid)[:12]

                if id_ingreso and id_gasto:
                    errores.append(
                        f"Movimiento {mid}: tiene ingreso y gasto vinculados."
                    )
                    continue

                if id_ingreso:
                    if str(id_ingreso) != esperado:
                        errores.append(
                            f"Movimiento {mid}: vínculo de ingreso inesperado."
                        )
                    else:
                        ids_ingresos.append(str(id_ingreso))

                if id_gasto:
                    if str(id_gasto) != esperado:
                        errores.append(
                            f"Movimiento {mid}: vínculo de gasto inesperado."
                        )
                    else:
                        ids_gastos.append(str(id_gasto))

            if len(ids_ingresos) != len(set(ids_ingresos)):
                errores.append("Hay ingresos vinculados más de una vez.")

            if len(ids_gastos) != len(set(ids_gastos)):
                errores.append("Hay gastos vinculados más de una vez.")

            cur.execute("""
                SELECT COUNT(*)
                FROM ingresos_trabajos
                WHERE id = ANY(%s)
            """, (ids_ingresos,))

            ingresos_existentes = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*)
                FROM gastos_comerciales
                WHERE id_gasto = ANY(%s)
            """, (ids_gastos,))

            gastos_existentes = cur.fetchone()[0]

            if ingresos_existentes != len(ids_ingresos):
                errores.append(
                    "Hay ingresos vinculados que no existen en la tabla contable."
                )

            if gastos_existentes != len(ids_gastos):
                errores.append(
                    "Hay gastos vinculados que no existen en la tabla contable."
                )

            return {
                "movimientos": len(movimientos),
                "ingresos": len(ids_ingresos),
                "gastos": len(ids_gastos),
                "errores": errores,
                "ids_ingresos": ids_ingresos,
                "ids_gastos": ids_gastos,
            }

    finally:
        conn.close()


def reiniciar_movimientos_bancarios(cantidad_esperada):
    """
    Respalda y elimina exclusivamente los registros contables
    vinculados de forma verificada a movimientos bancarios.
    Todo se ejecuta en una única transacción.
    """

    conn = get_conn()

    try:
        with conn.cursor() as cur:

            # Bloquear los movimientos durante la operación.
            cur.execute("""
                SELECT id, id_ingreso, id_gasto
                FROM movimientos_bancarios
                ORDER BY id
                FOR UPDATE
            """)

            movimientos = cur.fetchall()

            if len(movimientos) != cantidad_esperada:
                raise ValueError(
                    "La cantidad de movimientos cambió. "
                    "Volvé a revisar el resumen antes de continuar."
                )

            ids_ingresos = []
            ids_gastos = []

            for mid, id_ingreso, id_gasto in movimientos:

                esperado = "BAN-" + str(mid)[:12]

                if id_ingreso and id_gasto:
                    raise ValueError(
                        f"El movimiento {mid} tiene dos vínculos contables."
                    )

                if id_ingreso:
                    if str(id_ingreso) != esperado:
                        raise ValueError(
                            f"Vínculo de ingreso inesperado en {mid}."
                        )
                    ids_ingresos.append(str(id_ingreso))

                if id_gasto:
                    if str(id_gasto) != esperado:
                        raise ValueError(
                            f"Vínculo de gasto inesperado en {mid}."
                        )
                    ids_gastos.append(str(id_gasto))

            if (
                len(ids_ingresos) != len(set(ids_ingresos))
                or len(ids_gastos) != len(set(ids_gastos))
            ):
                raise ValueError(
                    "Hay vínculos contables repetidos. Se canceló el reinicio."
                )

            # Verificar que todos los registros vinculados existan.
            cur.execute("""
                SELECT COUNT(*)
                FROM ingresos_trabajos
                WHERE id = ANY(%s)
            """, (ids_ingresos,))

            if cur.fetchone()[0] != len(ids_ingresos):
                raise ValueError(
                    "No coinciden los ingresos vinculados. "
                    "Se canceló el reinicio."
                )

            cur.execute("""
                SELECT COUNT(*)
                FROM gastos_comerciales
                WHERE id_gasto = ANY(%s)
            """, (ids_gastos,))

            if cur.fetchone()[0] != len(ids_gastos):
                raise ValueError(
                    "No coinciden los gastos vinculados. "
                    "Se canceló el reinicio."
                )

            # Crear tabla de respaldo sin sobrescribir respaldos anteriores.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS respaldo_reset_bancario (
                    backup_id TEXT NOT NULL,
                    tabla_origen TEXT NOT NULL,
                    registro_id TEXT NOT NULL,
                    datos JSONB NOT NULL,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (backup_id, tabla_origen, registro_id)
                )
            """)

            backup_id = str(uuid.uuid4())

            # Respaldar movimientos bancarios.
            cur.execute("""
                INSERT INTO respaldo_reset_bancario
                    (backup_id, tabla_origen, registro_id, datos)
                SELECT %s, 'movimientos_bancarios', id, to_jsonb(t)
                FROM movimientos_bancarios t
            """, (backup_id,))

            # Respaldar exclusivamente los ingresos vinculados.
            cur.execute("""
                INSERT INTO respaldo_reset_bancario
                    (backup_id, tabla_origen, registro_id, datos)
                SELECT %s, 'ingresos_trabajos', id, to_jsonb(t)
                FROM ingresos_trabajos t
                WHERE id = ANY(%s)
            """, (backup_id, ids_ingresos))

            # Respaldar exclusivamente los gastos vinculados.
            cur.execute("""
                INSERT INTO respaldo_reset_bancario
                    (backup_id, tabla_origen, registro_id, datos)
                SELECT %s, 'gastos_comerciales', id_gasto, to_jsonb(t)
                FROM gastos_comerciales t
                WHERE id_gasto = ANY(%s)
            """, (backup_id, ids_gastos))

            # Eliminar únicamente los registros vinculados.
            cur.execute("""
                DELETE FROM ingresos_trabajos
                WHERE id = ANY(%s)
            """, (ids_ingresos,))

            cur.execute("""
                DELETE FROM gastos_comerciales
                WHERE id_gasto = ANY(%s)
            """, (ids_gastos,))

            # Eliminar los movimientos bancarios al final.
            cur.execute("""
                DELETE FROM movimientos_bancarios
            """)

        conn.commit()

        return backup_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

# ==========================================================
# PANTALLA PRINCIPAL
# ==========================================================

def pantalla_movimientos_bancarios():

    st.header("🏦 Movimientos bancarios")

    st.caption(
        "Subí el resumen del banco: lo que entró se carga en Ingresos "
        "y lo que salió en Gastos comerciales, sin cargar nada a mano."
    )
        # ======================================================
    # REINICIO SEGURO DE MOVIMIENTOS BANCARIOS
    # ======================================================

    with st.expander(
        "🛡️ Reinicio seguro de movimientos bancarios",
        expanded=False
    ):

        st.warning(
            "Esta herramienta permite respaldar y eliminar "
            "los movimientos bancarios para volver a importarlos. "
            "También elimina exclusivamente los ingresos y gastos "
            "vinculados a esos movimientos."
        )

        if st.button(
            "🔎 VERIFICAR QUÉ SE VA A ELIMINAR",
            key="btn_previsualizar_reset_bancario"
        ):

            try:
                estado = obtener_estado_reinicio_bancario()

                st.session_state["preview_reset_bancario"] = estado

            except Exception as e:
                st.error(f"No se pudo verificar la información: {e}")

        estado = st.session_state.get("preview_reset_bancario")

        if estado:

            st.divider()

            st.subheader("📋 Vista previa")

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Movimientos bancarios",
                estado["movimientos"]
            )

            c2.metric(
                "Ingresos vinculados",
                estado["ingresos"]
            )

            c3.metric(
                "Gastos vinculados",
                estado["gastos"]
            )

            if estado["errores"]:

                st.error(
                    "Se encontraron inconsistencias. "
                    "El reinicio está bloqueado."
                )

                for error in estado["errores"]:
                    st.write(f"• {error}")

            else:

                st.success(
                    "Verificación correcta. "
                    "No se detectaron vínculos inconsistentes."
                )

                st.info(
                    "Se generará un respaldo en Neon antes de eliminar "
                    "los registros. Los demás ingresos, gastos y datos "
                    "de la aplicación permanecerán intactos."
                )

                confirmacion = st.text_input(
                    f"Para confirmar, escribí: BORRAR "
                    f"{estado['movimientos']} MOVIMIENTOS",
                    key="confirmacion_reset_bancario"
                )

                if st.button(
                    "🗑️ CONFIRMAR REINICIO DEFINITIVO",
                    type="primary",
                    key="btn_confirmar_reset_bancario"
                ):

                    texto_esperado = (
                        f"BORRAR {estado['movimientos']} MOVIMIENTOS"
                    )

                    if confirmacion.strip() != texto_esperado:

                        st.error(
                            "La confirmación no coincide. "
                            "No se eliminó ningún dato."
                        )

                    else:

                        try:

                            backup_id = reiniciar_movimientos_bancarios(
                                estado["movimientos"]
                            )

                            st.session_state.pop(
                                "preview_reset_bancario",
                                None
                            )

                            st.session_state.pop(
                                "confirmacion_reset_bancario",
                                None
                            )

                            st.success(
                                "Reinicio completado. "
                                "El respaldo quedó guardado en Neon."
                            )

                            st.code(backup_id)

                            st.rerun()

                        except Exception as e:

                            st.error(
                                "El reinicio fue cancelado. "
                                f"La transacción se revirtió: {e}"
                            )

    # ------------------------------------------------------
    # ANALIZADOR INDEPENDIENTE
    # ------------------------------------------------------

    with st.expander(
        "📊 Analizar resumen bancario (sin contabilizar)",
        expanded=False
    ):

        st.write(
            "Pegá el texto del resumen o cargá un PDF para "
            "obtener un informe independiente. "
            "Este análisis no guarda movimientos "
            "ni modifica la contabilidad."
        )

        texto_resumen = st.text_area(
            "Pegá aquí el texto del resumen bancario",
            height=200,
            key="texto_analisis_resumen_bancario",
            placeholder="Pegá el texto copiado del resumen bancario..."
        )

        pdf_resumen = st.file_uploader(
            "O cargá un PDF del resumen",
            type=["pdf"],
            key="pdf_analisis_resumen_bancario"
        )

        if st.button(
            "Analizar resumen",
            type="primary",
            key="btn_analizar_resumen_bancario"
        ):

            texto_a_analizar = texto_resumen.strip()

            if pdf_resumen is not None:

                try:
                    with pdfplumber.open(
                        io.BytesIO(pdf_resumen.getvalue())
                    ) as pdf:

                        texto_a_analizar = "\n".join(
                            pagina.extract_text() or ""
                            for pagina in pdf.pages
                        ).strip()

                except Exception as e:
                    st.error(f"No se pudo leer el PDF: {e}")
                    texto_a_analizar = ""

            if not texto_a_analizar:
                st.warning(
                    "Pegá un texto o seleccioná un PDF antes de analizar."
                )

            else:

                resultado = generar_analisis_resumen(
                    texto_a_analizar
                )

                if resultado is None:
                    st.warning("No se encontró texto para analizar.")

                else:

                    st.subheader("📋 Resultado del análisis")

                    c1, c2, c3 = st.columns(3)

                    c1.metric(
                        "Ingresos identificados",
                        f"$ {resultado['total_ingresos']:,.2f}"
                    )

                    c2.metric(
                        "Egresos identificados",
                        f"$ {resultado['total_egresos']:,.2f}"
                    )

                    c3.metric(
                        "Diferencia identificada",
                        f"$ {resultado['variacion_identificada']:,.2f}"
                    )

                    st.info(
                        "La diferencia es la resta entre los ingresos "
                        "y egresos que se pudieron identificar. "
                        "La conciliación se verifica por separado "
                        "utilizando los saldos del resumen."
                    )

                    if resultado["saldo_inicial"] is not None:
                        st.write(
                            "Saldo inicial: "
                            f"$ {resultado['saldo_inicial']:,.2f}"
                        )

                    if resultado["saldo_final"] is not None:
                        st.write(
                            "Saldo final: "
                            f"$ {resultado['saldo_final']:,.2f}"
                        )

                    if resultado["conciliacion_calculada"] is not None:

                        st.write(
                            "Saldo calculado: "
                            f"$ {resultado['conciliacion_calculada']:,.2f}"
                        )

                        st.write(
                            "Diferencia de conciliación: "
                            f"$ {resultado['diferencia_conciliacion']:,.2f}"
                        )

                        if resultado["conciliado"]:
                            st.success("La conciliación de saldos coincide.")
                        else:
                            st.error("La conciliación de saldos no coincide.")

                    st.markdown("#### 🧾 ¿Qué pasó en el resumen?")

                    st.write(
                        f"Se analizaron {len(resultado['lineas'])} "
                        "líneas de texto. Se identificaron "
                        f"{len(resultado['ingresos'])} posibles ingresos "
                        f"y {len(resultado['egresos'])} posibles egresos."
                    )

                    if resultado["ingresos"]:
                        with st.expander("Ver ingresos identificados"):
                            for descripcion, monto in resultado["ingresos"]:
                                st.write(
                                    f"- {descripcion} · $ {monto:,.2f}"
                                )

                    if resultado["egresos"]:
                        with st.expander("Ver egresos identificados"):
                            for descripcion, monto in resultado["egresos"]:
                                st.write(
                                    f"- {descripcion} · $ {monto:,.2f}"
                                )

                    if resultado["saldos"]:
                        st.markdown("#### 💰 Saldos encontrados")

                        for descripcion, saldo in resultado["saldos"]:
                            st.write(
                                f"- {descripcion}: $ {saldo:,.2f}"
                            )

                    if resultado.get("conceptos_reconocidos"):

                        with st.expander(
                            "Conceptos reconocidos "
                            f"({len(resultado['conceptos_reconocidos'])})"
                        ):

                            for descripcion, concepto, monto in resultado[
                                "conceptos_reconocidos"
                            ]:

                                st.write(
                                    f"- **{concepto}** · $ {monto:,.2f}"
                                )

                                st.caption(descripcion)

                    if resultado["errores"]:

                        with st.expander(
                            "Validaciones y advertencias "
                            f"({len(resultado['errores'])})"
                        ):

                            for error in resultado["errores"]:
                                st.warning(error)

                    if resultado["sin_clasificar"]:

                        with st.expander(
                            "Movimientos sin clasificar "
                            f"({len(resultado['sin_clasificar'])})"
                        ):

                            st.caption(
                                "No se suman a ingresos ni egresos "
                                "porque el texto no permite "
                                "determinar su sentido."
                            )

                            for descripcion, monto in resultado[
                                "sin_clasificar"
                            ]:

                                st.write(
                                    f"- {descripcion} · $ {monto:,.2f}"
                                )

                    st.caption(
                        "Análisis automático. Revisá los importes "
                        "y las clasificaciones antes de utilizar "
                        "el resultado para tomar decisiones contables."
                    )

    # ------------------------------------------------------
    # PREPARAR TABLA
    # ------------------------------------------------------

    try:
        asegurar_tabla()

    except Exception as e:
        st.error(f"No se pudo preparar la tabla en Neon: {e}")
        st.info(
            "Verificá que la conexión de Neon esté configurada "
            "en Secrets como db."
        )
        return

    
    # ------------------------------------------------------
    # IMPORTACIÓN MASIVA DE RESÚMENES BANCARIOS
    # ------------------------------------------------------

    with st.expander(
        "📄 Importar uno o varios extractos bancarios PDF",
        expanded=True
    ):

        archivos = st.file_uploader(
            "Seleccioná todos los resúmenes bancarios que quieras importar",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_mov_bancarios"
        )

        if archivos:

            st.success(
                f"Seleccionaste {len(archivos)} archivo(s)."
            )

            for archivo in archivos:
                st.write(
                    f"📄 {archivo.name} · {archivo.size:,} bytes"
                )

            if st.button(
                "🚀 IMPORTAR TODOS Y GUARDAR EN NEON",
                type="primary",
                use_container_width=True,
                key="btn_importar_mov_bancarios"
            ):

                movimientos_totales = []
                archivos_correctos = []
                archivos_sin_movimientos = []
                errores_archivos = []

                barra = st.progress(0)

                # Leer cada PDF por separado.
                for i, archivo in enumerate(archivos):

                    try:

                        movimientos = extraer_movimientos_pdf(
                            archivo.getvalue(),
                            archivo.name
                        )

                        if movimientos:

                            movimientos_totales.extend(
                                movimientos
                            )

                            archivos_correctos.append(
                                archivo.name
                            )

                        else:

                            archivos_sin_movimientos.append(
                                archivo.name
                            )

                    except Exception as e:

                        errores_archivos.append({
                            "archivo": archivo.name,
                            "error": str(e)
                        })

                    barra.progress(
                        (i + 1) / len(archivos)
                    )

                # Guardar todos los movimientos válidos
                # en una sola transacción.
                if movimientos_totales:

                    try:

                        nuevos, actualizados, ids_nuevos = (
                            importar_movimientos(movimientos_totales)
                        )

                        st.success(
                            "¡Importación masiva terminada!"
                        )

                        c1, c2, c3 = st.columns(3)

                        c1.metric(
                            "Archivos procesados",
                            len(archivos_correctos)
                        )

                        c2.metric(
                            "Movimientos nuevos",
                            nuevos
                        )

                        c3.metric(
                            "Movimientos actualizados",
                            actualizados
                        )

                        st.info(
                            f"Se procesaron {len(movimientos_totales)} "
                            "movimientos detectados. "
                            "Los existentes se actualizaron por su huella "
                            "sin borrar su clasificación manual ni sus "
                            "vínculos contables."
                        )

                        # Paso automático: lo que entró va a Ingresos y
                        # lo que salió va a Gastos comerciales.
                        try:
                            ok, excluidos, errores_auto = (
                                procesar_movimientos_nuevos(ids_nuevos)
                            )

                            a1, a2, a3 = st.columns(3)

                            a1.metric("Pasados a contabilidad", ok)
                            a2.metric("Quedaron afuera", excluidos)
                            a3.metric("Con error", len(errores_auto))

                            if excluidos:
                                st.caption(
                                    "Quedan afuera las extracciones, "
                                    "compras personales, transferencias "
                                    "entre cuentas propias y reversiones. "
                                    "Los ves abajo, en 'Movimientos guardados'."
                                )

                            for e in errores_auto:
                                st.error(
                                    f"Movimiento {e['id']}: {e['error']}"
                                )

                        except Exception as e:
                            st.error(
                                "Los movimientos se importaron, pero falló "
                                f"el paso a contabilidad: {e}"
                            )

                    except Exception as e:

                        st.error(
                            "No se pudieron guardar los movimientos. "
                            "La transacción fue cancelada y no se "
                            f"guardó parcialmente: {e}"
                        )

                else:

                    st.warning(
                        "No se encontraron movimientos válidos. "
                        "No se guardó ningún archivo."
                    )

                if archivos_sin_movimientos:

                    with st.expander(
                        "Archivos sin movimientos detectados"
                    ):

                        for nombre in archivos_sin_movimientos:
                            st.warning(nombre)

                if errores_archivos:

                    with st.expander(
                        f"Archivos con errores ({len(errores_archivos)})"
                    ):

                        for error in errores_archivos:

                            st.error(
                                f"**{error['archivo']}**: "
                                f"{error['error']}"
                            )

    # ------------------------------------------------------
    # CARGAR MOVIMIENTOS
    # ------------------------------------------------------

    try:
        df = cargar_movimientos()

    except Exception as e:
        st.error(
            f"No se pudieron cargar los movimientos desde Neon: {e}"
        )
        return

    if df.empty:
        st.info("Todavía no hay movimientos importados.")
        return

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce"
    )

    mes_options = sorted(
        df["fecha"]
        .dropna()
        .dt.strftime("%Y-%m")
        .unique(),
        reverse=True
    )

    col_filtro_mes, col_filtro_estado = st.columns(2)

    with col_filtro_mes:
        mes = st.selectbox(
            "Mes",
            ["Todos"] + mes_options,
            key="filtro_mes_mov_bancarios"
        )

    estados_filtro = [
        "Todos",
        "Pendiente de revisión contable",
        "Revisado",
        "Contabilizado",
        "No contabilizar",
    ]

    with col_filtro_estado:
        estado_filtro = st.selectbox(
            "Filtrar por estado",
            estados_filtro,
            key="filtro_estado_mov_bancarios"
        )

    filtrado = df.copy()

    if mes != "Todos":
        filtrado = filtrado[
            filtrado["fecha"].dt.strftime("%Y-%m") == mes
        ]

    if estado_filtro != "Todos":
        filtrado = filtrado[
            filtrado["estado_revision"].fillna("") == estado_filtro
        ]

    st.caption(
        f"Mostrando {len(filtrado)} de {len(df)} movimientos."
    )

    diagnostico_movimientos(filtrado)

    # ------------------------------------------------------
    # TOTALES BANCARIOS
    # IMPORTANTE: USAR SENTIDO BANCARIO, NO TIPO CONTABLE
    # ------------------------------------------------------

    total_entradas = filtrado.loc[
        filtrado["sentido_bancario"] == "Ingreso",
        "monto"
    ].sum()

    total_salidas = filtrado.loc[
        filtrado["sentido_bancario"] == "Egreso",
        "monto"
    ].sum()

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Movimientos",
        len(filtrado)
    )

    c2.metric(
        "Entradas bancarias",
        f"$ {total_entradas:,.2f}"
    )

    c3.metric(
        "Salidas bancarias",
        f"$ {total_salidas:,.2f}"
    )

    st.caption(
        "Estos totales representan todos los movimientos de dinero "
        "que entraron y salieron del banco. Incluyen transferencias "
        "y movimientos personales; no equivalen a ingresos y gastos "
        "comerciales."
    )

    # ======================================================
    # CONTABILIZACIÓN MASIVA
    # ======================================================

    st.divider()

    st.subheader(
        "🚀 Pasar movimientos a Ingresos y Gastos"
    )

    st.caption(
        "Este proceso utiliza el tipo y la categoría que "
        "ya están guardados en Neon. No vuelve a clasificar "
        "ni modifica las descripciones."
    )

    st.warning(
        "Los ingresos se incorporarán a Ingresos y los egresos "
        "a Gastos comerciales. Los movimientos personales, "
        "transferencias y categorías pendientes quedarán afuera."
    )

    if st.button(
        "🚀 PASAR INGRESOS Y EGRESOS A LA CONTABILIDAD",
        type="primary",
        use_container_width=True,
        key="btn_contabilizar_clasificados"
    ):

        try:
            exitosos, excluidos, errores = (
                contabilizar_clasificados_existentes(df)
            )

            st.session_state["resultado_lote_bancario"] = {
                "exitosos": exitosos,
                "excluidos": excluidos,
                "errores": errores,
            }

            st.rerun()

        except Exception as e:
            st.error(
                f"Error durante la contabilización: {e}"
            )

    # ------------------------------------------------------
    # RESULTADO DE LA CONTABILIZACIÓN
    # ------------------------------------------------------

    if "resultado_lote_bancario" in st.session_state:

        resultado = st.session_state[
            "resultado_lote_bancario"
        ]

        st.success(
            "Movimientos enviados a la contabilidad: "
            f"{resultado['exitosos']}"
        )

        st.info(
            "Movimientos excluidos por tipo, categoría, "
            "moneda o vínculo existente: "
            f"{resultado['excluidos']}"
        )

        if resultado["errores"]:

            with st.expander(
                f"Movimientos con errores "
                f"({len(resultado['errores'])})"
            ):

                for error in resultado["errores"]:
                    st.error(
                        f"Movimiento {error['id']}: "
                        f"{error['error']}"
                    )

        if st.button(
            "Cerrar resultado",
            key="cerrar_resultado_lote"
        ):

            del st.session_state[
                "resultado_lote_bancario"
            ]

            st.rerun()

    # ======================================================
    # REGLA AUTOMÁTICA SOBRE MOVIMIENTOS ANTERIORES
    # ======================================================

    st.divider()

    st.subheader("♻️ Aplicar la regla automática a lo ya importado")

    try:
        cantidad_reclasificable = contar_pendientes_reclasificables()
    except Exception as e:
        cantidad_reclasificable = 0
        st.error(f"No se pudo consultar los pendientes: {e}")

    st.caption(
        "Toma los movimientos que quedaron 'Pendiente de clasificar' o "
        "como 'Transferencia entre cuentas' sin revisar, los clasifica "
        "con la regla actual (entró = ingreso, salió = gasto) y los pasa "
        "a contabilidad. No toca los que ya están Contabilizado, Revisado "
        "o No contabilizar."
    )

    st.write(f"Movimientos alcanzados: **{cantidad_reclasificable}**")

    if cantidad_reclasificable:

        confirma = st.checkbox(
            "Entiendo que se van a cargar como ingresos y gastos",
            key="chk_reclasificar_pendientes"
        )

        if st.button(
            "♻️ RECLASIFICAR Y PASAR A CONTABILIDAD",
            disabled=not confirma,
            key="btn_reclasificar_pendientes"
        ):

            try:
                ids_reclasificados = reclasificar_pendientes()

                ok, excluidos, errores_rec = (
                    procesar_movimientos_nuevos(ids_reclasificados)
                )

                st.session_state["resultado_lote_bancario"] = {
                    "exitosos": ok,
                    "excluidos": excluidos,
                    "errores": errores_rec,
                }

                st.rerun()

            except Exception as e:
                st.error(f"Error al reclasificar: {e}")

    # ======================================================
    # MOVIMIENTOS GUARDADOS
    # ======================================================

    st.divider()

    st.subheader("Movimientos guardados")

    st.caption(
        "Revisá tipo y categoría. El sentido bancario "
        "se conserva por separado y no se modifica al clasificar."
    )

    for _, fila in filtrado.iterrows():

        mid = str(fila["id"])

        fecha_txt = (
            fila["fecha"].strftime("%d/%m/%Y")
            if pd.notna(fila["fecha"])
            else "Sin fecha"
        )

        monto_fila = float(fila["monto"] or 0)

        descripcion_fila = str(
            fila["descripcion"] or ""
        )

        with st.expander(
            f"{fecha_txt} · $ {monto_fila:,.2f} · "
            f"{descripcion_fila[:90]}"
        ):

            st.write(
                f"**Descripción:** {descripcion_fila}"
            )

            st.write(
                "**Sentido bancario:** "
                f"{fila.get('sentido_bancario', 'Otro')}"
            )

            st.write(
                "**Clasificación contable:** "
                f"{fila['tipo']}"
            )

            if pd.notna(fila["saldo"]):
                st.write(
                    f"**Saldo posterior:** "
                    f"$ {float(fila['saldo']):,.2f}"
                )
            else:
                st.write("Saldo no disponible")

            if fila.get("id_ingreso"):
                st.caption(
                    f"Vinculado a ingreso: {fila['id_ingreso']}"
                )

            if fila.get("id_gasto"):
                st.caption(
                    f"Vinculado a gasto: {fila['id_gasto']}"
                )

            col1, col2, col3 = st.columns(3)

            with col1:

                tipo_actual = (
                    fila["tipo"]
                    if fila["tipo"] in TIPOS
                    else "Otro"
                )

                tipo = st.selectbox(
                    "Tipo contable",
                    TIPOS,
                    index=TIPOS.index(tipo_actual),
                    key=f"tipo_{mid}"
                )

            with col2:

                cat_actual = (
                    fila["categoria"]
                    if fila["categoria"] in CATEGORIAS
                    else CATEGORIAS[0]
                )

                categoria = st.selectbox(
                    "Categoría",
                    CATEGORIAS,
                    index=CATEGORIAS.index(cat_actual),
                    key=f"cat_{mid}"
                )

            with col3:

                if fila["estado_revision"] == "Contabilizado":

                    st.text_input(
                        "Estado",
                        value="Contabilizado",
                        disabled=True,
                        key=f"estado_{mid}"
                    )

                    estado = "Contabilizado"

                else:

                    estado_actual = (
                        fila["estado_revision"]
                        if fila["estado_revision"] in ESTADOS
                        else ESTADOS[0]
                    )

                    estado = st.selectbox(
                        "Estado",
                        ESTADOS,
                        index=ESTADOS.index(estado_actual),
                        key=f"estado_{mid}"
                    )

            if fila["estado_revision"] != "Contabilizado":

                if st.button(
                    "Guardar revisión",
                    key=f"guardar_rev_{mid}"
                ):

                    try:
                        actualizar_movimiento(
                            mid,
                            tipo,
                            categoria,
                            estado
                        )

                        st.success("Revisión guardada.")
                        st.rerun()

                    except Exception as e:
                        st.error(
                            f"No se pudo guardar la revisión: {e}"
                        )

            comprobante = st.file_uploader(
                "Adjuntar comprobante (PDF o imagen)",
                type=[
                    "pdf",
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                ],
                key=f"comprobante_{mid}"
            )

            if (
                comprobante is not None
                and st.button(
                    "Guardar comprobante",
                    key=f"guardar_comp_{mid}"
                )
            ):

                try:
                    guardar_comprobante(
                        mid,
                        comprobante
                    )

                    st.success(
                        "Comprobante guardado en Neon."
                    )

                    st.rerun()

                except Exception as e:
                    st.error(
                        f"No se pudo guardar el comprobante: {e}"
                    )

            if fila.get("comprobante_data") is not None:

                st.download_button(
                    "Descargar comprobante guardado",
                    data=bytes(fila["comprobante_data"]),
                    file_name=str(
                        fila["comprobante_nombre"] or "comprobante"
                    ),
                    mime=str(
                        fila["comprobante_mime"]
                        or "application/octet-stream"
                    ),
                    key=f"descargar_comp_{mid}",
                )

            if (
                fila["estado_revision"] != "Contabilizado"
                and estado != "No contabilizar"
            ):

                if st.button(
                    "Confirmar y contabilizar",
                    type="primary",
                    key=f"contabilizar_{mid}"
                ):

                    try:
                        actualizar_movimiento(
                            mid,
                            tipo,
                            categoria,
                            "Revisado"
                        )

                        contabilizar(mid)

                        st.success(
                            "Movimiento contabilizado y vinculado "
                            "al módulo existente."
                        )

                        st.rerun()

                    except Exception as e:
                        st.error(
                            f"No se pudo contabilizar: {e}"
                        )                