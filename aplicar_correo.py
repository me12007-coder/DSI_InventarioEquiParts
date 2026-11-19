#!/usr/bin/env python3
"""Hotfix SMTP Equi-Parts: solo app/__init__.py y, si hace falta, email_service.py.
No ejecuta SQL, no toca .env, fotos ni inventario.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import os
import re
import shutil
import sys
import tempfile

ROOT = Path('/var/www/equiparts')
CFG = ROOT / 'app/__init__.py'
MAIL = ROOT / 'app/services/email_service.py'
HERE = Path(__file__).resolve().parent


def reemplazar_uno(texto, patron, reemplazo, nombre):
    nuevo, n = re.subn(patron, reemplazo, texto, count=1, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError('Estructura SMTP no reconocida: ' + nombre + '. No se aplican cambios.')
    return nuevo


def configurar_smtp(original):
    s = original
    # Contraseñas de aplicación de Google: los espacios de presentación NO forman parte del código.
    if "''.join(os.getenv('EQUIPARTS_MAIL_PASSWORD', '').split())" not in s:
        s = reemplazar_uno(
            s,
            r"^(\s*app\.config\['MAIL_PASSWORD'\]\s*=\s*)os\.getenv\('EQUIPARTS_MAIL_PASSWORD',\s*''\)([ \t]*)$",
            r"\g<1>''.join(os.getenv('EQUIPARTS_MAIL_PASSWORD', '').split())\g<2>",
            'MAIL_PASSWORD')
    if 'EQUIPARTS_MAIL_PORT' not in s:
        s = reemplazar_uno(s, r"^(\s*app\.config\['MAIL_PORT'\]\s*=\s*)587([ \t]*)$",
                             r"\g<1>int(os.getenv('EQUIPARTS_MAIL_PORT', '587'))\g<2>", 'MAIL_PORT')
        s = reemplazar_uno(s, r"^(\s*)app\.config\['MAIL_USE_TLS'\]\s*=\s*True([ \t]*)$",
                             r"\g<1>app.config['MAIL_USE_SSL'] = app.config['MAIL_PORT'] == 465\n\g<1>app.config['MAIL_USE_TLS'] = app.config['MAIL_PORT'] == 587\g<2>", 'MAIL_USE_TLS')
    if "app.config['MAIL_TIMEOUT']" not in s:
        s = reemplazar_uno(s, r"^(\s*)app\.config\['MAIL_USERNAME'\]",
                             r"\g<1>app.config['MAIL_TIMEOUT'] = 20\n\g<1>app.config['MAIL_USERNAME']", 'MAIL_USERNAME')
    return s


def reparar_auditoria_correo(original):
    # 1.1.15 ya separó notificación SMTP y movimientos; no reemplazar versiones reparadas.
    if 'conn.execute(' not in original and 'VALUES (?, ?,' not in original:
        return original
    if not all(k in original for k in ('def enviar_alerta_stock(', 'mail.send(msg)', 'conn.execute(', "VALUES (?, ?, 'Alerta de Stock (Correo)', ?)")):
        raise RuntimeError('Servicio de correo distinto del conocido. No se sobrescribe.')
    return (HERE / 'email_service.py.new').read_text(encoding='utf8')


def guardar_atomico(path, contenido):
    fd, nombre = tempfile.mkstemp(prefix='.equicorreo-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as salida:
            salida.write(contenido)
        shutil.copymode(path, nombre)
        os.replace(nombre, path)
    finally:
        if os.path.exists(nombre):
            os.unlink(nombre)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Ejecutar como root.')
    originales = {p: p.read_text(encoding='utf8') for p in (CFG, MAIL)}
    cambios = {CFG: configurar_smtp(originales[CFG]), MAIL: reparar_auditoria_correo(originales[MAIL])}
    for path, codigo in cambios.items():
        ast.parse(codigo, filename=str(path))
    modificados = [p for p in cambios if cambios[p] != originales[p]]
    if not modificados:
        print('YA CONFIGURADO: no hubo que modificar los archivos.')
        return
    bdir = Path('/root/backups-equiparts') / ('correo_116_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    bdir.mkdir(parents=True, exist_ok=False)
    for path in originales:
        shutil.copy2(path, bdir / path.name)
    escritos = []
    try:
        for path in modificados:
            guardar_atomico(path, cambios[path]); escritos.append(path)
    except Exception:
        for path in escritos:
            shutil.copy2(bdir / path.name, path)
        raise
    print('APLICADO. Respaldo:', bdir)
    print('Archivos actualizados:', ', '.join(str(p.relative_to(ROOT)) for p in modificados))
    print('Antes de reiniciar, comprueba la sintaxis con py_compile.')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('NO APLICADO:', str(e), file=sys.stderr)
        sys.exit(1)
