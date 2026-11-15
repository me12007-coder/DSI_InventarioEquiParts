"""Reconstrucción estimada diaria; sin cambios en MariaDB. Versión 1.1.11."""
from collections import defaultdict
from datetime import date, datetime, timedelta


def delta_fisico(tipo, cantidad):
    """Cambio físico de un movimiento; None si no es posible inferirlo."""
    nombre = str(tipo or '').strip()
    n = nombre.casefold()
    q = int(cantidad or 0)
    if n in ('entrada', 'creación de producto', 'importación masiva (csv)'):
        return q
    if n in ('salida', 'venta_cotizacion'):
        return -q
    if n.startswith('ajuste manual:') or n.startswith('ajuste:'):
        return q  # los ajustes contienen diferencia firmada, NO stock final
    if n.startswith('traslado a mermas:'):
        return -q
    if n.startswith('devolución (reingreso):') or n.startswith('devolucion (reingreso):'):
        return q
    # Operaciones que solo afectan reservas, mermas separadas o estados.
    if (n in ('cotizacion', 'baja', 'eliminación de producto', 'desactivación de producto',
              'reactivación de producto', 'purga de historial (respaldo csv descargado)')
        or n.startswith('devolución (dañado/')
        or n.startswith('devolucion (dañado/')
        or n.startswith('destrucción de merma:')
        or n.startswith('retiro definitivo')
        or n.startswith('archivado')):
        return 0
    return None


def construir_cierres(productos, movimientos, inicio, fin):
    """Retorna filas de stock físico estimado, por SKU y día, hasta fecha fin incluida.

    El ancla es productos.cantidad (snapshot actual). Se revierten los eventos
    posteriores a cada cierre. Fechas y cantidades son las registradas en MariaDB.
    """
    por_producto = defaultdict(list)
    for m in movimientos:
        por_producto[m['producto_id']].append(m)

    dias = (fin - inicio).days + 1
    filas = []
    for p in productos:
        idp = p['id']
        eventos = sorted(por_producto[idp], key=lambda e: (e['fecha'], e['id']), reverse=True)
        ignorados = [e for e in eventos if delta_fisico(e['tipo'], e['cantidad']) is None]
        primer_alta = min((e['fecha'].date() for e in eventos if str(e['tipo']).casefold() in
                          ('creación de producto', 'importación masiva (csv)')), default=None)
        actual = int(p['cantidad'] or 0)
        indice = 0
        # Retroceder día a día a partir de la última fecha solicitada.
        for paso in range(dias - 1, -1, -1):
            dia = inicio + timedelta(days=paso)
            while indice < len(eventos) and eventos[indice]['fecha'].date() > dia:
                e = eventos[indice]
                delta = delta_fisico(e['tipo'], e['cantidad'])
                if delta is not None:
                    actual -= delta
                indice += 1
            # Los eventos desconocidos posteriores al corte impiden calcularlo con certeza.
            desconocidos_posteriores = any(e['fecha'].date() > dia for e in ignorados)
            estado = 'REVISAR' if desconocidos_posteriores else 'ESTIMADO'
            if primer_alta and dia < primer_alta:
                valor = 0
                estado = 'PREVIO AL ALTA' if not desconocidos_posteriores else 'REVISAR'
            else:
                valor = None if desconocidos_posteriores else actual
                if valor is not None and valor < 0:
                    estado = 'REVISAR'
            filas.append({'fecha': dia.isoformat(), 'sku': p['sku'], 'nombre': p['nombre'],
                          'stock': valor, 'estado': estado})
    filas.sort(key=lambda r: (r['fecha'], str(r['sku'])))
    return filas
