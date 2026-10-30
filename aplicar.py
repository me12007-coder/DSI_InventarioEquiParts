#!/usr/bin/env python3
"""Inserta CSRF en formularios POST de categorías/edición de producto sin sustituir plantillas."""
from pathlib import Path
from datetime import datetime, timezone
import re, shutil, sys, tempfile, os

BASE = Path('/var/www/equiparts')
NAMES = ['categorias.html', 'editar_producto.html']
CSRF = '<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">'
FORM = re.compile(r'(<form\b[^>]*>)(.*?)(</form\s*>)', re.I | re.S)
METHOD = re.compile(r'\bmethod\s*=\s*(["\']?)post\1(?=[\s>])', re.I)
TOKEN = re.compile(r'name\s*=\s*["\']_csrf_token["\']', re.I)

def patch(s):
    count = 0
    def f(m):
        nonlocal count
        op, body, cl = m.groups()
        if METHOD.search(op) and not TOKEN.search(body):
            count += 1
            return op + '\n' + CSRF + '\n' + body + cl
        return m.group(0)
    return FORM.sub(f,s),count

def main():
    path=BASE/'app/plantillas'
    planned={}
    for name in NAMES:
        file=path/name
        if not file.is_file():
            raise RuntimeError(f'No existe: {file}; no se modificó nada')
        old=file.read_text(encoding='utf8')
        new,count=patch(old)
        if not FORM.search(old) or 'csrf_token()' not in new:
            raise RuntimeError(f'Plantilla inesperada {name}; no se modificó nada')
        planned[file]=(old,new,count)
    backup=Path('/root/backups-equiparts')/('csrf_categoria_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    backup.mkdir(parents=True, exist_ok=False)
    for file,(old,new,count) in planned.items():
        (backup/file.name).write_text(old,encoding='utf8')
    for file,(old,new,count) in planned.items():
        if old == new:
            print(f'{file.name}: ya tenía tokens CSRF')
            continue
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=file.parent, prefix='.csrf_',delete=False) as f:
            f.write(new)
            tmp=Path(f.name)
        shutil.copymode(file,tmp)
        os.replace(tmp,file)
        print(f'{file.name}: {count} formulario(s) corregido(s)')
    print('Respaldo:',backup)
    print('No se modificó base de datos ni lógica de eliminación.')
if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('NO APLICADO:',exc,file=sys.stderr)
        raise SystemExit(1)
