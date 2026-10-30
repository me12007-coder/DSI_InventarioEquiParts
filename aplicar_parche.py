#!/usr/bin/env python3
"""Parche conservador para plantillas actuales de Equi-Parts (sin cambios SQL/Python backend)."""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path('/var/www/equiparts')
TEMPLATES = ROOT / 'app/plantillas'
CSRF = '<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">'


def add_csrf(source):
    # Inserta en formularios POST, incluso los generados mediante plantillas JS.
    # Evita insertar dos veces si el formulario ya incluye el token.
    regex = re.compile(r'(<form\b(?=[^>]*\bmethod\s*=\s*[\"\']post[\"\'])[^>]*>)(.*?)(</form\s*>)', re.I | re.S)
    count = 0
    def fix(match):
        nonlocal count
        start, body, end = match.groups()
        if re.search(r'name\s*=\s*[\"\']_csrf_token[\"\']', body):
            return match.group(0)
        count += 1
        return start + CSRF + body + end
    source = regex.sub(fix, source)
    return source, count


def fix_inventory(s):
    s, n = add_csrf(s)
    # Resalta los accesos con clases Bootstrap compatibles con temas existentes.
    s = s.replace('class="btn btn-outline-warning btn-sm" href="{{ url_for(\'inventario.inventario\',estado=\'inactivos\') }}"',
                  'class="btn btn-warning btn-sm fw-semibold ep-inactive-link" href="{{ url_for(\'inventario.inventario\',estado=\'inactivos\') }}"')
    s = s.replace('class="btn btn-outline-primary btn-sm" href="{{ url_for(\'reportes.conciliacion\') }}"',
                  'class="btn btn-primary btn-sm fw-semibold ep-reconcile-link" href="{{ url_for(\'reportes.conciliacion\') }}"')
    if 'ep-inventory-toolbar' not in s:
        old = 'd-flex justify-content-between align-items-center mb-4 bg-white p-3 rounded shadow-sm border flex-wrap gap-3 esconder-impresion'
        if old not in s:
            raise RuntimeError('Cabecera distinta de la versión esperada: no se aplicó el cambio visual.')
        s = s.replace(old, old + ' ep-inventory-toolbar', 1)
    if 'id="ep-toolbar-styles"' not in s:
        style = '''<style id="ep-toolbar-styles">
.ep-inventory-toolbar {display:flex; align-items:center; gap:1rem 1.25rem; flex-wrap:wrap;}
.ep-inventory-toolbar .page-title-row {flex:1 1 320px; min-width:240px;}
.ep-inventory-toolbar .mx-auto {margin-left:0 !important; margin-right:0 !important;}
.ep-inventory-toolbar > .d-flex.gap-2 {flex-wrap:wrap; align-items:center;}
.ep-inventory-toolbar .ep-inactive-link {color:#332600; border-color:#c99522;}
.ep-inventory-toolbar .ep-inactive-link:hover {color:#221a00;}
.ep-inventory-toolbar .ep-reconcile-link {white-space:normal;}
@media (max-width:760px) {.ep-inventory-toolbar > * {max-width:100%;}.ep-inventory-toolbar .capsula-estado {flex-wrap:wrap;}}
</style>'''
        s=s.replace('</head>',style+'\n</head>',1)
    return s,n


def fix_reconciliation(s):
    s,n=add_csrf(s)
    # El formulario conserva los estilos existentes y el token via POST.
    return s,n


def main():
    init = ROOT / 'app/__init__.py'
    if not init.is_file() or "_csrf_token" not in init.read_text() or 'csrf_token' not in init.read_text():
        raise RuntimeError('No se reconoce el control CSRF esperado en el código del VPS; no se realizaron cambios.')
    targets={'inventario.html':fix_inventory,'conciliacion.html':fix_reconciliation}
    rewritten={}
    for name, fix in targets.items():
        p=TEMPLATES/name
        if not p.is_file():
            raise RuntimeError(f'No existe {p}; no se realizaron cambios.')
        original=p.read_text(encoding='utf-8')
        adjusted,n=fix(original)
        if name=='inventario.html' and not all(x in adjusted for x in ['ep-inventory-toolbar','_csrf_token']):
            raise RuntimeError('Validación de Inventario fallida; no se realizaron cambios.')
        if name=='conciliacion.html' and (not re.search(r'<form[^>]*method=["\']post',adjusted,re.I)):
            raise RuntimeError('Formulario CSV no encontrado; no se realizaron cambios.')
        rewritten[name]=(original,adjusted,n)
    # No sobreescribir sin respaldo íntegro de los dos originales.
    backup=Path('/root/backups-equiparts') / ('plantillas_antes_hotfix_113_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    for name,(original,_,_) in rewritten.items():
        (backup/name).write_text(original,encoding='utf-8')
    for name,(_,adjusted,n) in rewritten.items():
        p=TEMPLATES/name
        tmp=p.with_name(p.name+'.tmp_hotfix_113')
        tmp.write_text(adjusted,encoding='utf-8')
        shutil.copymode(p,tmp)
        tmp.replace(p)
        print(f'{name}: {n} formulario(s) POST corregido(s)')
    print('Respaldo de plantillas:',backup)
    print('No se modificaron Python, MariaDB, secretos ni fotografías.')
    print('Si la sesión actual ya expiró, vuelve a iniciar sesión y actualiza la página.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('PARCHE DETENIDO:',exc,file=sys.stderr)
        sys.exit(1)
