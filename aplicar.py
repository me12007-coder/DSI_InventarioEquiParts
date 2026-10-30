#!/usr/bin/env python3
"""Repara CSRF de formularios POST de detalle_producto.html; no altera BD."""
from pathlib import Path
from datetime import datetime, timezone
import re, shutil, sys

ROOT=Path('/var/www/equiparts')
TEMPLATE=ROOT/'app/plantillas/detalle_producto.html'
INIT=ROOT/'app/__init__.py'
TOKEN='<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">'
RX=re.compile(r'(<form\b[^>]*>)(.*?)(</form\s*>)', re.S|re.I)

def fix(src):
    counts=[0,0]
    def replace(m):
        start,content,end=m.groups()
        if not re.search(r'\bmethod\s*=\s*[\'\"]post[\'\"]',start,re.I):
            return m.group(0)
        counts[0]+=1
        if re.search(r'\bname\s*=\s*[\'\"]_csrf_token[\'\"]',content,re.I):
            return m.group(0)
        counts[1]+=1
        return start+'\n            '+TOKEN+'\n'+content+end
    return RX.sub(replace,src),counts

def main():
    if not INIT.is_file() or '_csrf_token' not in INIT.read_text(encoding='utf-8'):
        raise RuntimeError('El control CSRF instalado no coincide con el esperado; no se aplica.')
    original=TEMPLATE.read_text(encoding='utf-8')
    if 'id="formTransaccion"' not in original:
        raise RuntimeError('No se encontró formTransaccion; no se aplica.')
    edited,counts=fix(original)
    if counts[0]<1 or counts[0]>12:
        raise RuntimeError('Cantidad inesperada de formularios POST; no se aplica.')
    if re.search(r'<form[^>]*id="formTransaccion"',edited,re.I) is None:
        raise RuntimeError('Falta el formulario de transacciones; no se aplica.')
    if counts[1]==0:
        print('Sin cambios: los formularios POST ya tienen token CSRF.')
        return
    try:
        from jinja2 import Environment
        Environment().parse(edited)
    except Exception as exc:
        raise RuntimeError(f'Plantilla Jinja no válida: {exc}')
    backup=Path('/root/backups-equiparts')/('detalle_csrf_116_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(TEMPLATE,backup/TEMPLATE.name)
    tmp=TEMPLATE.with_name(TEMPLATE.name+'.tmp_116')
    tmp.write_text(edited,encoding='utf-8')
    shutil.copymode(TEMPLATE,tmp)
    tmp.replace(TEMPLATE)
    print(f'CORRECTO: {counts[1]} formularios POST corregidos de {counts[0]} detectados.')
    print('Respaldo:',backup/TEMPLATE.name)
    print('No se modificaron Python, contraseñas ni MariaDB.')

if __name__=='__main__':
    try: main()
    except Exception as e:
        print('NO APLICADO:',e,file=sys.stderr)
        sys.exit(1)
