#!/usr/bin/env python3
"""Hotfix conservador para Equi-Parts: archivar sin romper referencias históricas.
Requiere columna productos.archivado creada previamente (ver instrucciones).
No ejecuta SQL ni reinicia servicios.
"""
from pathlib import Path
from datetime import datetime, timezone
import sys, shutil

BASE = Path('/var/www/equiparts')
PYFILE = BASE / 'app/blueprints/inventario.py'
HTML = BASE / 'app/plantillas/inventario.html'
try:
    source = PYFILE.read_text(encoding='utf-8')
    page = HTML.read_text(encoding='utf-8')
    if 'WHERE p.activo = %s AND (p.sku LIKE %s OR p.nombre LIKE %s)' not in source:
        raise ValueError('La consulta del inventario ha cambiado; no se modificó nada.')
    if "UPDATE productos SET activo=1 WHERE id=%s AND activo=0" not in source:
        raise ValueError('La ruta de reactivación ha cambiado; no se modificó nada.')
    start = source.find("@inventario_bp.route('/producto/<int:id>/eliminar-definitivo', methods=['POST'])")
    if start < 0:
        raise ValueError('No se encontró el endpoint de eliminar definitivo; no se modificó nada.')
    # La ruta es la última sección en la versión revisada. No sobrescribimos código posterior.
    if source.find('@inventario_bp.route(', start + 10) != -1:
        raise ValueError('Hay más rutas tras eliminar-definitivo; se requiere revisión manual.')
    if 'name="_csrf_token"' not in page:
        raise ValueError('La plantilla no parece contener la corrección CSRF; se requiere revisión.')

    source = source.replace('WHERE p.activo = %s AND (p.sku LIKE %s OR p.nombre LIKE %s)',
                            'WHERE p.activo = %s AND p.archivado = 0 AND (p.sku LIKE %s OR p.nombre LIKE %s)', 1)
    source = source.replace('UPDATE productos SET activo=1 WHERE id=%s AND activo=0',
                            'UPDATE productos SET activo=1 WHERE id=%s AND activo=0 AND archivado=0', 1)
    source = source[:start] + '''@inventario_bp.route('/producto/<int:id>/eliminar-definitivo', methods=['POST'])
def borrar_producto_definitivo(id):
    """Retirada lógica: invisible en inventario, historial y claves externas intactos."""
    if 'user_id' not in session or session.get('rol') != 'Administrador':
        return redirect(url_for('inventario.inventario'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id,activo,cantidad,stock_reservado,archivado FROM productos WHERE id=%s FOR UPDATE', (id,))
            p = cur.fetchone()
            if not p:
                flash('Producto inexistente.', 'warning')
            elif p['archivado']:
                flash('El producto ya estaba retirado.', 'warning')
            elif p['activo'] or p['cantidad'] != 0 or p['stock_reservado'] != 0:
                flash('Para retirar un producto debe estar inactivo, sin stock y sin reservas.', 'warning')
            else:
                cur.execute('UPDATE productos SET archivado=1, activo=0 WHERE id=%s AND archivado=0', (id,))
                cur.execute('INSERT INTO movimientos (producto_id,usuario_id,tipo,cantidad) VALUES (%s,%s,%s,0)',
                            (id, session['user_id'], 'Retiro definitivo del inventario'))
                flash('Producto retirado del inventario. Los movimientos se conservaron para reportes.', 'success')
        conn.commit()
    except Exception:
        conn.rollback()
        current_app.logger.exception('Error archivando producto')
        flash('No se pudo retirar el producto. Revisa los registros.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventario.inventario', estado='inactivos'))
'''
    old = "Eliminar DEFINITIVAMENTE este producto solo si no tiene existencias ni movimientos. ¿Continuar?"
    if old not in page:
        raise ValueError('La confirmación del botón cambió; no se modificó nada.')
    page = page.replace(old, 'Retirar este producto del inventario, conservando todos sus movimientos históricos. ¿Continuar?')
    page = page.replace('>Eliminar</button>', '>Retirar</button>')
    compile(source, str(PYFILE), 'exec')
    backup = Path('/root/backups-equiparts') / ('archivado_117_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(PYFILE, backup/'inventario.py')
    shutil.copy2(HTML, backup/'inventario.html')
    PYFILE.write_text(source, encoding='utf-8')
    HTML.write_text(page, encoding='utf-8')
    print('Parche aplicado. Copias de código en:', backup)
    print('La base de datos NO se modificó mediante este script.')
except Exception as exc:
    print('NO APLICADO:', str(exc), file=sys.stderr)
    raise SystemExit(1)
