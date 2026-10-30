#!/usr/bin/env python3
"""Parche conservador: CSRF en edición y stock solo lectura, sin tocar MariaDB."""
from pathlib import Path
from datetime import datetime, timezone
import shutil, sys, re
base=Path('/var/www/equiparts')
html=base/'app/plantillas/editar_producto.html'
py=base/'app/blueprints/inventario.py'
backup=Path('/root/backups-equiparts')/('edicion_115_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S'))
try:
    h=html.read_text(encoding='utf-8'); p=py.read_text(encoding='utf-8')
    if '<form method="POST" enctype="multipart/form-data">' not in h: raise ValueError('Formulario distinto: no se parcheó.')
    form_start=h.index('<form method="POST" enctype="multipart/form-data">')
    form_end=h.index('</form>', form_start)
    if '_csrf_token' not in h[form_start:form_end]:
        h=h[:form_start]+h[form_start:].replace('<form method="POST" enctype="multipart/form-data">','<form method="POST" enctype="multipart/form-data">\n<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">',1)
    pat=r'<input type="number" name="cantidad" class="form-control fw-bold fs-5" value="{{ p.cantidad }}" min="0" required>'
    replacement='<output class="form-control fw-bold fs-5" aria-label="Stock físico actual">{{ p.cantidad }}</output>'
    if pat not in h and replacement not in h: raise ValueError('Campo de stock inesperado: no se parcheó.')
    h=h.replace(pat,replacement)
    h=h.replace('Actualiza la información, existencias, ubicación y documentos asociados.','Actualiza la ficha, ubicación y documentos. Las existencias se registran en Entradas/Salidas.')
    h=h.replace('Existencias, punto de alerta y precio del producto.','Stock de consulta, punto de alerta y precio del producto.')
    h=h.replace('Unidades existentes en bodega.','Solo lectura: modifica el stock desde Entradas/Salidas.')
    old='categoria_id = %s, cantidad = %s, stock_minimo = %s,'
    new='categoria_id = %s, stock_minimo = %s,'
    if old not in p and new not in p: raise ValueError('SQL de edición distinto: no se parcheó.')
    p=p.replace(old,new,1)
    expr="categoria_id, (int(data.get('cantidad', 0)) if prod_actual['activo'] else prod_actual['cantidad']), stock_minimo,"
    replacement2='categoria_id, stock_minimo,'
    if expr not in p and replacement2 not in p: raise ValueError('Parámetros de SQL diferentes: no se parcheó.')
    p=p.replace(expr,replacement2,1)
    compile(p, str(py), 'exec')
    backup.mkdir(parents=True,exist_ok=False)
    shutil.copy2(html,backup/html.name);shutil.copy2(py,backup/py.name)
    html.write_text(h,encoding='utf-8');py.write_text(p,encoding='utf-8')
    print('APLICADO. Backup:',backup)
    print('Edición: token CSRF, stock solo lectura; actualización SQL sin cantidad.')
    print('Reinicia equiparts.service tras comprobar archivos.')
except Exception as e:
    print('NO APLICADO:',e,file=sys.stderr)
    raise SystemExit(1)
