#!/usr/bin/env python3
"""Parche conservador de validación de SKU, sin cambios automáticos en MariaDB."""
from pathlib import Path
from datetime import datetime, timezone
import shutil
import sys

archivo = Path('/var/www/equiparts/app/blueprints/inventario.py')
marcador = "    if request.method == 'POST' and session.get('rol') in ['Administrador', 'Bodeguero']:\n"
sello = '        # EQUIPARTS_SKU_UNICO_118\n'
bloque = '''        # EQUIPARTS_SKU_UNICO_118
        sku_nuevo = str(request.form.get('sku', '')).strip().upper()
        if not sku_nuevo:
            conn.close()
            flash('El SKU es obligatorio.', 'danger')
            return redirect(url_for('inventario.inventario'))
        if any(c.isspace() for c in sku_nuevo):
            conn.close()
            flash('El SKU no puede contener espacios.', 'danger')
            return redirect(url_for('inventario.inventario'))
        with conn.cursor() as cur_sku:
            cur_sku.execute('SELECT id FROM productos WHERE UPPER(TRIM(sku)) = %s LIMIT 1', (sku_nuevo,))
            sku_repetido = cur_sku.fetchone()
        if sku_repetido:
            conn.close()
            flash(f'No se guardó el producto: el SKU {sku_nuevo} ya existe, incluso si está inactivo o archivado.', 'warning')
            return redirect(url_for('inventario.inventario'))
'''
try:
    antes = archivo.read_text(encoding='utf-8')
    if sello in antes:
        print('YA APLICADO: la validación de SKU está presente.')
        raise SystemExit(0)
    if antes.count(marcador) != 1:
        raise ValueError('El punto de inserción del alta no coincide con la versión prevista.')
    despues = antes.replace(marcador, marcador + bloque, 1)
    compile(despues, str(archivo), 'exec')
    destino = Path('/root/backups-equiparts') / ('sku_118_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    destino.mkdir(parents=True, exist_ok=False)
    shutil.copy2(archivo, destino / archivo.name)
    temporal = archivo.with_name(archivo.name + '.sku118.tmp')
    temporal.write_text(despues, encoding='utf-8')
    temporal.chmod(archivo.stat().st_mode & 0o777)
    temporal.replace(archivo)
    print('APLICADO: validación del SKU antes de insertar.')
    print('Respaldo:', destino / archivo.name)
except Exception as exc:
    print('NO APLICADO:', exc, file=sys.stderr)
    raise SystemExit(1)
