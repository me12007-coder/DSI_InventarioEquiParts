#!/usr/bin/env python3
"""Instalación incremental de reporte de cierre diario, NO migra ni escribe en DB."""
from pathlib import Path
import ast, datetime, os, shutil, sys, tempfile
from jinja2 import Environment

ROOT = Path('/var/www/equiparts')
HERE = Path(__file__).resolve().parent
reportes = ROOT/'app/blueprints/reportes.py'
dashboard = ROOT/'app/plantillas/reporte_inventario.html'
helper = ROOT/'app/cierre_diario.py'
template = ROOT/'app/plantillas/cierre_diario.html'
for f in (reportes, dashboard):
    if not f.is_file(): sys.exit(f'NO APLICADO: falta {f}')
for f in ('cierre_diario.py', 'cierre_diario.html', 'ruta_cierre.pyfrag'):
    if not (HERE/f).is_file(): sys.exit(f'NO APLICADO: falta {HERE/f}')
old_r = reportes.read_text(encoding='utf-8')
old_d = dashboard.read_text(encoding='utf-8')
if '# EQUIPARTS-CIERRE-DIARIO-1111' in old_r:
    sys.exit('YA APLICADO: la ruta de cierre diario ya está en reportes.py')
if 'reportes_bp = Blueprint(' not in old_r or 'def reporte_historico(' not in old_r:
    sys.exit('NO APLICADO: no se reconoció reportes.py')
anchor = '<!-- 1. Reporte Histórico -->'
if old_d.count(anchor) != 1:
    sys.exit('NO APLICADO: estructura del panel de reportes desconocida')
if helper.exists() or template.exists():
    sys.exit('NO APLICADO: ya existen los archivos de cierre diario. Revisar antes de sobrescribir.')
route = (HERE/'ruta_cierre.pyfrag').read_text(encoding='utf-8')
new_r = old_r.rstrip() + '\n' + route
link = '''<!-- EQUIPARTS-CIERRE-DIARIO-1111 -->
        <div class="col-md-6 col-xl-3">
            <div class="card shadow-sm border-0 h-100" style="border-top:4px solid #5B708D !important;">
                <div class="card-body d-flex flex-column">
                    <h6 class="fw-bold"><i class="bi bi-calendar-range me-2"></i>Stock al cierre por día</h6>
                    <p class="text-muted small mb-3">Consulta los cierres estimados de cada producto durante un período y descarga CSV.</p>
                    <a href="{{ url_for('reportes.reporte_cierre_diario') }}" class="btn btn-sm w-100 mt-auto" style="background:#5B708D;color:#fff">Ver cierres diarios</a>
                </div>
            </div>
        </div>
        '''
new_d = old_d.replace(anchor,link+anchor,1)
try:
    ast.parse(new_r,filename='reportes.py')
    ast.parse((HERE/'cierre_diario.py').read_text(encoding='utf-8'))
    for markup in (new_d,(HERE/'cierre_diario.html').read_text(encoding='utf-8')):
        Environment().parse(markup)
except Exception as exc:
    sys.exit(f'NO APLICADO: validación de código/plantillas: {exc}')
backup_dir=Path('/root/backups-equiparts')/('cierre_diario_1111_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
backup_dir.mkdir(parents=True,exist_ok=False,mode=0o700)
shutil.copy2(reportes,backup_dir/'reportes.py')
shutil.copy2(dashboard,backup_dir/'reporte_inventario.html')
changed=[]
try:
    for path,contenido in ((reportes,new_r),(dashboard,new_d)):
        fd,temp=tempfile.mkstemp(prefix='.cierre1111_',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(contenido)
            os.chmod(temp,path.stat().st_mode & 0o777)
            os.replace(temp,path)
            changed.append(path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    shutil.copy2(HERE/'cierre_diario.py',helper)
    shutil.copy2(HERE/'cierre_diario.html',template)
except Exception as exc:
    for path in changed:
        src=backup_dir/('reportes.py' if path==reportes else 'reporte_inventario.html')
        shutil.copy2(src,path)
    helper.unlink(missing_ok=True)
    template.unlink(missing_ok=True)
    sys.exit(f'NO APLICADO: se revirtieron los archivos: {exc}')
print('APLICADO: ruta y plantilla de cierre diario instaladas')
print('Respaldo de archivos:',backup_dir)
print('No se modificó MariaDB. Comprueba sintaxis y reinicia equiparts.service.')
