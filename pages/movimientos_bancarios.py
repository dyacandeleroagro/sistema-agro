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
    """
    Clasifica de forma conservadora.
    Reconoce el concepto, pero no supone que una transferencia
    sea un movimiento entre cuentas propias.
    """
    d = re.sub(r"\s+", " ", str(descripcion or "").upper()).strip()
    tipo = str(tipo or "Otro").strip()

    # Transferencias: reconocerlas, pero no asumir quién es la contraparte.
    if any(x in d for x in ("TRANSF", "TRPRO", "DEBTRF", "EGRESO:")):
        return "Pendiente de clasificar", tipo

    if any(x in d for x in ("EXTRACCION", "EXTRACCIÓN", "CAJERO")):
        return "Extracción / efectivo", "Personal"

    # Comisiones bancarias específicas.
    if any(x in d for x in (
        "COMISION ADM.VALORES",
        "COMISIÓN ADM.VALORES",
        "COMISION",
        "COMISIÓN",
        "PAQUETE BANCARIO",
    )):
        return "Comisiones bancarias", tipo

    # Retenciones, percepciones y débitos/créditos impositivos.
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
        return "Impuestos", tipo

    if any(x in d for x in (
        "SEGURO",
        "SAN CRISTOBAL",
        "SAN CRISTÓBAL",
        "SANCOR",
    )):
        return "Seguro", tipo

    if any(x in d for x in (
        "COMBUST",
        "YPF",
        "SHELL",
        "AXION",
    )):
        return "Combustible", tipo

    # No asumir que el nombre de una empresa implica un cobro o pago.
    # Se necesita verificar la contraparte y el motivo.
    if any(x in d for x in (
        "ACREDITACION CHEQUE REMESAS",
        "ACREDITACIÓN CHEQUE REMESAS",
        "CHEQUE",
        "FAC ",
        "FACTURA",
        "AGROP",
        "COOP GAN",
        "COOP. GAN",
        "CREDIN:",
    )):
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

        # El importe de la operación debe coincidir con el cambio del saldo.
        if abs(delta) < 0.005:
            saldo_anterior = saldo
            continue

        if abs(abs(delta) - abs(importe_linea)) > 0.01:
            raise ValueError(
                "Importación cancelada por seguridad: el importe del movimiento "
                f"no coincide con la variación del saldo. Línea: {linea}. "
                f"Importe de línea: $ {abs(importe_linea):,.2f}; "
                f"variación calculada: $ {abs(delta):,.2f}. "
                "No se guardó esta importación. Revisá el PDF y su extracción."
            )

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
    """
    Contabiliza un movimiento bancario en Neon de forma transaccional.
    Bloquea categorías personales, transferencias y registros duplicados.
    """
    conn = None

    categorias_personales_o_no_contables = {
        "Gasto personal",
        "Transferencia entre cuentas",
        "Extracción / efectivo",
        "Pendiente de clasificar",
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
            # Bloquea el movimiento para impedir contabilizaciones simultáneas.
            cur.execute(
                """
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
                """,
                (mid,),
            )

            row = cur.fetchone()

            if not row:
                raise ValueError("No se encontró el movimiento bancario.")

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

            # Una operación ya contabilizada no debe volver a insertarse.
            if estado_revision == "Contabilizado":
                if tipo == "Ingreso" and id_ingreso_existente:
                    cur.execute(
                        "SELECT 1 FROM ingresos_trabajos WHERE id = %s",
                        (id_ingreso_existente,),
                    )
                    if cur.fetchone():
                        conn.commit()
                        return id_ingreso_existente

                elif tipo == "Egreso" and id_gasto_existente:
                    cur.execute(
                        "SELECT 1 FROM gastos_comerciales WHERE id_gasto = %s",
                        (id_gasto_existente,),
                    )
                    if cur.fetchone():
                        conn.commit()
                        return id_gasto_existente

                raise ValueError(
                    "El movimiento figura como contabilizado, pero su "
                    "registro vinculado no existe o no es válido. "
                    "Requiere revisión manual; no se creará otro registro."
                )

            # Solo se contabilizan movimientos revisados expresamente.
            if estado_revision != "Revisado":
                raise ValueError(
                    "Primero guardá la revisión del movimiento."
                )

            tipo = str(tipo or "").strip()
            categoria = str(categoria or "").strip()
            moneda = str(moneda or "").strip().upper()

            if categoria in categorias_personales_o_no_contables:
                raise ValueError(
                    f"La categoría '{categoria}' no se puede contabilizar "
                    "como ingreso o gasto comercial. Revisá su clasificación."
                )

            if tipo not in ("Ingreso", "Egreso"):
                raise ValueError(
                    "Solo se pueden contabilizar ingresos y egresos "
                    "comerciales. Las transferencias, extracciones y "
                    "movimientos personales quedan fuera de estos módulos."
                )

            if tipo == "Ingreso" and categoria in categorias_de_egreso:
                raise ValueError(
                    "La categoría elegida corresponde a un gasto, "
                    "no a un ingreso. Corregí la clasificación."
                )

            if tipo == "Egreso" and categoria in categorias_de_ingreso:
                raise ValueError(
                    "La categoría elegida corresponde a un ingreso, "
                    "no a un gasto. Corregí la clasificación."
                )

            if moneda != "ARS":
                raise ValueError(
                    "La contabilización automática solo admite ARS. "
                    "La moneda debe revisarse antes de continuar."
                )

            monto_decimal = Decimal(str(monto))

            if not monto_decimal.is_finite() or monto_decimal <= 0:
                raise ValueError(
                    "El importe debe ser un número válido mayor que cero."
                )

            # Si ya hay un vínculo parcial, no generar un segundo registro.
            if id_ingreso_existente or id_gasto_existente:
                raise ValueError(
                    "El movimiento ya tiene un vínculo contable. "
                    "Se requiere revisar ese vínculo antes de continuar."
                )

            registro_id = "BAN-" + str(mid)[:12]

            if tipo == "Ingreso":
                cur.execute(
                    """
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        registro_id,
                        fecha,
                        "Por identificar",
                        "Ingreso bancario",
                        "",
                        0,
                        monto_decimal,
                        f"Importado desde Banco Macro: {descripcion}",
                    ),
                )

                insertado = cur.fetchone()

                if not insertado:
                    raise ValueError(
                        "Ya existe un ingreso con el identificador "
                        f"{registro_id}. No se vinculó ni contabilizó "
                        "automáticamente para evitar duplicados."
                    )

                cur.execute(
                    """
                    UPDATE movimientos_bancarios
                    SET id_ingreso = %s,
                        estado_revision = 'Contabilizado',
                        actualizado_en = NOW()
                    WHERE id = %s
                    """,
                    (registro_id, mid),
                )

            else:
                cur.execute(
                    """
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id_gasto) DO NOTHING
                    RETURNING id_gasto
                    """,
                    (
                        registro_id,
                        fecha,
                        str(descripcion or ""),
                        monto_decimal,
                        moneda,
                        monto_decimal,
                        categoria,
                        "",
                        "Pendiente de Pago",
                        str(comprobante_nombre or ""),
                        comprobante_data,
                    ),
                )

                insertado = cur.fetchone()

                if not insertado:
                    raise ValueError(
                        "Ya existe un gasto con el identificador "
                        f"{registro_id}. No se vinculó ni contabilizó "
                        "automáticamente para evitar duplicados."
                    )

                cur.execute(
                    """
                    UPDATE movimientos_bancarios
                    SET id_gasto = %s,
                        estado_revision = 'Contabilizado',
                        actualizado_en = NOW()
                    WHERE id = %s
                    """,
                    (registro_id, mid),
                )

            if cur.rowcount != 1:
                raise ValueError(
                    "No se pudo actualizar el vínculo del movimiento."
                )

        # El registro contable y su vínculo se confirman juntos.
        conn.commit()
        return registro_id

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if conn:
            conn.close()


def generar_analisis_resumen(texto):
    """Analiza un extracto sin guardar datos ni modificar la contabilidad."""

    from decimal import Decimal, InvalidOperation

    if not texto or not texto.strip():
        return None

    lineas = [x.strip() for x in texto.splitlines() if x.strip()]

    def importe_decimal(valor):
        valor = str(valor).strip().replace("$", "").replace(" ", "")
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

        if "SALDO FINAL AL DIA" in mayus or "SALDO FINAL AL DÍA" in mayus:
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
                f"No se identificaron importe y saldo posterior: {linea}"
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

        clave = (fecha_txt, descripcion.upper(), str(saldo))

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

        diferencia = (saldo_actual - saldo_previo).quantize(
            Decimal("0.01")
        )
        variacion_bancaria += diferencia

        if diferencia == Decimal("0.00"):
            errores.append(
                f"El saldo no cambió pese a que aparece un movimiento: {linea}"
            )
            sin_clasificar.append((linea, float(importe_linea)))
            destacados.append(linea)
            saldo_previo = saldo_actual
            continue

        # Verificar que el importe impreso coincida con la variación del saldo.
        if abs(abs(diferencia) - importe_linea) > Decimal("0.01"):
            errores.append(
                "El importe de la línea no coincide con la variación "
                f"del saldo. Línea: {linea}. "
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

        # Reconocer el concepto sin afirmar algo que el extracto no prueba.
        if "ACREDITACION CHEQUE REMESAS" in d or "ACREDITACIÓN CHEQUE REMESAS" in d:
            concepto = "Acreditación de cheque; origen por confirmar"

        elif "COMISION ADM.VALORES" in d or "COMISIÓN ADM.VALORES" in d:
            concepto = "Comisión bancaria por valores al cobro"

        elif "RETENCION IVA" in d or "RETENCIÓN IVA" in d or "PERCEPCION" in d or "PERCEPCIÓN" in d:
            concepto = "Retención/percepción impositiva; revisar tratamiento contable"

        elif "DBCR" in d and "S/DB" in d:
            concepto = "Débito por tasa/impuesto; verificar concepto bancario"

        elif "DBCR" in d and "S/CR" in d:
            concepto = "Crédito o reversión de tasa/impuesto; verificar origen"

        elif "TRANSF" in d or "TRPRO" in d or "DEBTRF" in d:
            concepto = (
                "Transferencia entrante; contraparte y motivo por confirmar"
                if tipo == "Ingreso"
                else "Transferencia saliente; destinatario y motivo por confirmar"
            )

        elif "CHEQUE" in d:
            concepto = "Movimiento relacionado con cheque; revisar origen"

        else:
            concepto = "Concepto detectado; verificar clasificación comercial"

        conceptos_reconocidos.append((linea, concepto, float(monto)))

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
        # Se concilia con todos los cambios de saldo, incluso los que quedaron
        # pendientes de revisión, para no ocultar diferencias.
        conciliacion_calculada = (
            saldo_inicial + variacion_bancaria
        ).quantize(Decimal("0.01"))

        diferencia_conciliacion = (
            saldo_final - conciliacion_calculada
        ).quantize(Decimal("0.01"))

        conciliado = diferencia_conciliacion == Decimal("0.00")

        if not conciliado:
            errores.append(
                "La conciliación de saldos no coincide. Revisá movimientos "
                "omitidos, páginas faltantes, orden de las líneas o saldos."
            )
    else:
        errores.append(
            "No se encontraron los saldos inicial y final de la cuenta. "
            "La conciliación completa no puede verificarse."
        )

    # Quitar repeticiones sin alterar el orden.
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
        "saldo_inicial": float(saldo_inicial) if saldo_inicial is not None else None,
        "saldo_final": float(saldo_final) if saldo_final is not None else None,
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

def pantalla_movimientos_bancarios():
    st.header("🏦 Movimientos bancarios")
    st.caption("Importación del extracto a Neon. Los movimientos quedan pendientes de revisión; nada se contabiliza sin confirmación.")


    with st.expander("📊 Analizar resumen bancario (sin contabilizar)", expanded=False):
        st.write(
            "Pegá el texto del resumen o cargá un PDF para obtener un "
            "informe independiente. Este análisis no guarda movimientos "
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
                    import io

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
                st.warning("Pegá un texto o seleccioná un PDF antes de analizar.")
            else:
                resultado = generar_analisis_resumen(texto_a_analizar)

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
                        "La diferencia es la resta entre los ingresos y "
                        "egresos que se pudieron identificar. No representa "
                        "necesariamente la variación real del saldo bancario."
                    )

                    st.markdown("#### 🧾 ¿Qué pasó en el resumen?")

                    st.write(
                        f"Se analizaron {len(resultado['lineas'])} líneas "
                        "de texto. Se identificaron "
                        f"{len(resultado['ingresos'])} posibles ingresos y "
                        f"{len(resultado['egresos'])} posibles egresos."
                    )

                    if resultado["ingresos"]:
                        with st.expander("Ver ingresos identificados"):
                            for descripcion, monto in resultado["ingresos"]:
                                st.write(f"- {descripcion} · $ {monto:,.2f}")

                    if resultado["egresos"]:
                        with st.expander("Ver egresos identificados"):
                            for descripcion, monto in resultado["egresos"]:
                                st.write(f"- {descripcion} · $ {monto:,.2f}")

                    if resultado["saldos"]:
                        st.markdown("#### 💰 Saldos encontrados")
                        for descripcion, saldo in resultado["saldos"]:
                            st.write(f"- {descripcion}: $ {saldo:,.2f}")

                    if resultado.get("conceptos_reconocidos"):
                        with st.expander(
                            f"Conceptos reconocidos ({len(resultado['conceptos_reconocidos'])})"
                        ):
                            for descripcion, concepto, monto in resultado["conceptos_reconocidos"]:
                                st.write(f"- **{concepto}** · $ {monto:,.2f}")
                                st.caption(descripcion)

                    if resultado["errores"]:
                        with st.expander(
                            f"Validaciones y advertencias ({len(resultado['errores'])})"
                        ):
                            for error in resultado["errores"]:
                                st.warning(error)

                    if resultado["sin_clasificar"]:
                        with st.expander(
                            f"Movimientos sin clasificar "
                            f"({len(resultado['sin_clasificar'])})"
                        ):
                            st.caption(
                                "No se suman a ingresos ni egresos porque "
                                "el texto no permite determinar su sentido."
                            )
                            for descripcion, monto in resultado["sin_clasificar"]:
                                st.write(f"- {descripcion} · $ {monto:,.2f}")

                    st.caption(
                        "Análisis automático por palabras clave. Revisá los "
                        "importes y las clasificaciones antes de usar el "
                        "resultado para tomar decisiones contables."
                    )

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
