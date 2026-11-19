#!/usr/bin/env python3
"""Instalador conservador: corrige alertas de correo y añade botón eliminar foto.
No toca MariaDB ni secretos ni reinicia servicios.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast, os, shutil, sys, tempfile

BASE = Path('/var/www/equiparts')
HERE = Path(__file__).resolve().parent
INV = BASE / 'app/blueprints/inventario.py'
TPL = BASE / 'app/plantillas/editar_producto.html'
MAIL = BASE / 'app/services/email_service.py'
ROUTE_MARK = 'def eliminar_foto_producto(id, foto_id):'
ENDPOINT = 'inventario.eliminar_foto_producto'

def fail(message):
    raise RuntimeError(message)

def patch_inv(source):
    if ROUTE_MARK in source:
        if '/foto/<int:foto_id>/eliminar' not in source:
            fail('Existe una función eliminar_foto_producto distinta; requiere revisión manual.')
        print('RUTA: ya existe, conservada')
        return source
    if 'def foto_principal(id,foto_id):' not in source and 'def foto_principal(id, foto_id):' not in source:
        fail('No se encontró el flujo de galería esperado en inventario.py')
    anchor = "@inventario_bp.route('/categorias', methods=['GET', 'POST'])"
    if source.count(anchor) != 1:
        fail('No se encontró el lugar seguro para agregar ruta de fotografía.')
    return source.replace(anchor, (HERE/'ruta_foto.pyfrag').read_text(encoding='utf8') + anchor, 1)

def patch_tpl(source):
    if ENDPOINT in source:
        print('BOTÓN: ya existe, conservado')
        return source
    # Se exige el botón Principal ya existente: la inserción no afecta otros formularios.
    principal = "formaction=\"{{ url_for('inventario.foto_principal', id=p.id, foto_id=foto.id) }}\""
    if principal not in source:
        fail('No existe el botón Principal esperado en editar_producto.html')
    if source.count('{% for foto in galeria %}') != 1:
        fail('No se pudo identificar una sola galería de imágenes')
    if 'name="_csrf_token"' not in source:
        fail('La plantilla no tiene campo CSRF. Primero corregir esa protección.')
    a = source.index('{% for foto in galeria %}')
    b = source.index('{% endfor %}', a)
    group = source[a:b]
    if group.count(principal) != 1:
        fail('La galería usa un botón Principal distinto al esperado')
    # La fila de la galería es compacta; cerrar solo la caja del botón, no insertar un formulario anidado.
    close = '{% endif %}</div></div>'
    if group.count(close) != 1:
        fail('La galería cambió de estructura. No se ha modificado nada.')
    delete = """{% endif %}<button type="submit" formaction="{{ url_for('inventario.eliminar_foto_producto', id=p.id, foto_id=foto.id) }}" formmethod="post" formnovalidate class="btn btn-outline-danger btn-sm ms-1" onclick="return confirm('¿Eliminar esta fotografía de la galería?');" aria-label="Eliminar fotografía">Eliminar foto</button></div></div>"""
    return source[:a] + group.replace(close, delete, 1) + source[b:]

def patch_email(source):
    # Validar el contrato de integración; no sustituir un servicio ajeno o ya muy modificado.
    markers = ['def enviar_alerta_stock(', 'mail.send(msg)', 'conn.execute(', "VALUES (?, ?, 'Alerta de Stock (Correo)', ?)"]
    if 'EQUIPARTS_MAIL_FIX_115' in source:
        print('CORREO: ya corregido')
        return source
    if not all(m in source for m in markers):
        fail('email_service.py no coincide con el servicio defectuoso conocido. Se requiere revisión manual.')
    updated = (HERE/'email_service.py.new').read_text(encoding='utf8')
    return '# EQUIPARTS_MAIL_FIX_115\n' + updated

try:
    for path in (INV, TPL, MAIL):
        if not path.is_file(): fail('Falta archivo: ' + str(path))
    original = {INV: INV.read_text(encoding='utf8'), TPL: TPL.read_text(encoding='utf8'), MAIL: MAIL.read_text(encoding='utf8')}
    updated = {INV: patch_inv(original[INV]), TPL: patch_tpl(original[TPL]), MAIL: patch_email(original[MAIL])}
    for path in (INV, MAIL):
        compile(updated[path], str(path), 'exec')
    from jinja2 import Environment
    Environment().parse(updated[TPL])
    changes = [p for p in original if updated[p] != original[p]]
    if not changes:
        print('SIN CAMBIOS: las correcciones ya están presentes')
        raise SystemExit(0)
    folder = Path('/root/backups-equiparts') / ('correo_fotos_115_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True, exist_ok=False)
    for path in original:
        shutil.copy2(path, folder/path.name)
    replaced = []
    try:
        for path in changes:
            fd, temp = tempfile.mkstemp(prefix='.equiparts115-', dir=path.parent)
            try:
                with os.fdopen(fd, 'w', encoding='utf8') as f:
                    f.write(updated[path])
                shutil.copymode(path, temp)
                os.replace(temp, path)
                replaced.append(path)
            finally:
                if os.path.exists(temp): os.unlink(temp)
    except Exception:
        for path in replaced: shutil.copy2(folder/path.name, path)
        raise
    print('APLICADO: corrección de correo y botón eliminar foto')
    print('Respaldo original:', folder)
    print('Reinicia equiparts.service solo tras verificar sintaxis.')
except Exception as exc:
    print('NO APLICADO:', str(exc), file=sys.stderr)
    raise SystemExit(1)
