#!/usr/bin/env python3
"""Parche conservador 1.1.10: Bodeguero-Categorías + exportación CSV stock actual."""
from pathlib import Path
import ast, datetime, shutil, sys, tempfile, os
from jinja2 import Environment

ROOT = Path('/var/www/equiparts')
FILES = {
    'nav': ROOT / 'app/plantillas/includes/navbar.html',
    'cat': ROOT / 'app/plantillas/categorias.html',
    'reportes': ROOT / 'app/blueprints/reportes.py',
    'estado': ROOT / 'app/plantillas/estado_financiero.html',
    'dashboard': ROOT / 'app/plantillas/reporte_inventario.html',
}
for nombre, path in FILES.items():
    if not path.is_file():
        sys.exit(f'NO APLICADO: falta archivo {nombre}: {path}')
orig = {key:path.read_text(encoding='utf-8') for key,path in FILES.items()}
new = dict(orig)

# Menú. No modifica el bloque Administrador.
if '<!-- bodeguero-categorias-119 -->' not in new['nav']:
    anchor = "    {% if session.get('rol') == 'Administrador' %}"
    link = "href=\"{{ url_for('inventario.categorias') }}\""
    if new['nav'].count(anchor) != 1 or link not in new['nav']:
        sys.exit('NO APLICADO: menú distinto del esperado; no se modificó nada.')
    block = """    <!-- bodeguero-categorias-119 -->
    {% if session.get('rol') == 'Bodeguero' %}
    <a class="nav-link nav-categories {% if request.endpoint == 'inventario.categorias' %}active{% endif %}" href="{{ url_for('inventario.categorias') }}">
      <i class="bi bi-tags"></i><span>Categorías</span>
    </a>
    {% endif %}

"""
    new['nav'] = new['nav'].replace(anchor, block + anchor, 1)

# Limita acciones de edición y eliminación de categorías a administradores en la UI.
if 'bodeguero-solo-crear-119' not in new['cat']:
    start = '<!-- Botón Editar (Totalmente independiente) -->'
    end = '                    </td>'
    pos = new['cat'].find(start)
    stop = new['cat'].find(end, pos) if pos >= 0 else -1
    if pos < 0 or stop < 0 or 'modalEditarCat' not in new['cat'][pos:stop] or 'inventario.eliminar_categoria' not in new['cat'][pos:stop]:
        sys.exit('NO APLICADO: estructura de categorías no reconocida; no se modificó nada.')
    new['cat'] = (new['cat'][:pos] + '<!-- bodeguero-solo-crear-119 -->\n'
                  + "{% if session.get('rol') == 'Administrador' %}\n"
                  + new['cat'][pos:stop]
                  + "{% else %}<span class=\"text-muted small\">Solo consulta</span>{% endif %}\n"
                  + new['cat'][stop:])

# Ruta aditiva, NO reescribe otros reportes.
marker = '# EQUIPARTS-STOCK-ACTUAL-1110'
if marker not in new['reportes']:
    if 'reportes_bp = Blueprint(' not in new['reportes'] or 'def estado_financiero(' not in new['reportes']:
        sys.exit('NO APLICADO: estructura del módulo reportes no reconocida.')
    new['reportes'] += Path(__file__).with_name('ruta_csv_actual.pyfrag').read_text(encoding='utf-8')

# En Estado financiero, botón CSV junto a Imprimir. Mantiene presentación / colores existentes.
link_actual = "url_for('reportes.exportar_inventario_actual_csv')"
if link_actual not in new['estado']:
    imprimir = '<button onclick="window.print()"'
    if new['estado'].count(imprimir) != 1:
        sys.exit('NO APLICADO: botón Imprimir de Estado Financiero no reconocido.')
    nuevo_boton = ("<a href=\"{{ url_for('reportes.exportar_inventario_actual_csv') }}\" "
                    "class=\"btn btn-sm fw-bold shadow-sm me-2\" "
                    "style=\"background-color:#5B708D;color:#fff;\">"
                    "<i class=\"bi bi-filetype-csv me-1\"></i> CSV Inventario actual</a>\n            ")
    new['estado'] = new['estado'].replace(imprimir, nuevo_boton + imprimir, 1)

# Acceso adicional en Reportes, sin tocar la cabecera del Inventario que ya ha dado problemas.
if link_actual not in new['dashboard']:
    anchor = "<a href=\"{{ url_for('reportes.exportar_reporte_csv') }}\""
    if new['dashboard'].count(anchor) != 1:
        sys.exit('NO APLICADO: acceso a CSV críticos no reconocido.')
    nuevo_boton = ('<a href="{{ url_for(\'reportes.exportar_inventario_actual_csv\') }}" '
                   'class="btn btn-sm fw-bold shadow-sm" style="background:#5B708D;color:#fff;">'
                   '<i class="bi bi-filetype-csv me-1"></i> CSV Inventario actual</a>\n                    ')
    new['dashboard'] = new['dashboard'].replace(anchor, nuevo_boton + anchor, 1)

try:
    ast.parse(new['reportes'], filename='reportes.py')
    env = Environment()
    for key in ('nav','cat','estado','dashboard'):
        env.parse(new[key])
except Exception as e:
    sys.exit(f'NO APLICADO: validación sintáctica falló: {e}')

modified=[key for key in FILES if new[key] != orig[key]]
if not modified:
    print('YA APLICADO: no hay cambios pendientes.'); sys.exit(0)

backups=Path('/root/backups-equiparts')
backups.mkdir(parents=True,exist_ok=True)
backup=backups/('parche_1110_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup.mkdir(mode=0o700)
for key in modified:
    shutil.copy2(FILES[key],backup/(key+FILES[key].suffix))

written=[]
try:
    for key in modified:
        target=FILES[key]
        fd,tmp=tempfile.mkstemp(prefix='.parche1110-',dir=str(target.parent))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(new[key])
            os.chmod(tmp,target.stat().st_mode & 0o777)
            os.replace(tmp,target)
            written.append(key)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
except Exception as e:
    for key in written:
        shutil.copy2(backup/(key+FILES[key].suffix),FILES[key])
    sys.exit(f'NO APLICADO: error y restauración ejecutada: {e}')
print('APLICADO correctamente. Archivos:',', '.join(modified))
print('Respaldo:',backup)
print('Sin cambios en MariaDB. Reinicia equiparts.service y comprueba la descarga.')
