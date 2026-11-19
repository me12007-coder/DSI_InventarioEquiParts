#!/usr/bin/env python3
"""Diagnóstico de solo lectura de SMTP y eliminación de fotos en Equi-Parts.
No imprime contraseñas, no envía correo, no modifica archivos ni base de datos.
"""
from pathlib import Path
import os
import shlex
import socket
import smtplib
import ssl
import sys

ROOT = Path('/var/www/equiparts')
ENV = Path('/etc/equiparts/equiparts.env')


def load_env(path):
    values = {}
    if not path.exists():
        print('ENTORNO: no se encontró', path)
        return values
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export '):]
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        try:
            parts = shlex.split(v, comments=False, posix=True)
            if len(parts) == 1:
                values[k] = parts[0]
            elif not v.strip():
                values[k] = ''
        except ValueError:
            print('ENTORNO: valor mal formado en', k, '(no se muestra)')
    return values


def main():
    print('=== DIAGNÓSTICO EQUIPARTS (SOLO LECTURA) ===')
    e = load_env(ENV)
    for k in ('EQUIPARTS_MAIL_USERNAME', 'EQUIPARTS_MAIL_PASSWORD'):
        print(k, ':', 'CONFIGURADA' if e.get(k) else 'FALTA')
    print('NOTA: también hay que comprobar que systemd cargue el archivo de entorno.')

    try:
        import subprocess
        result = subprocess.run(['systemctl', 'show', 'equiparts.service', '--property=EnvironmentFiles'],
                                capture_output=True, text=True, timeout=8)
        print('SYSTEMD ENV FILE:', 'configurado' if str(ENV) in result.stdout else 'no confirmado')
    except Exception as ex:
        print('SYSTEMD:', type(ex).__name__)

    # Configuración vista en la última fuente compartida. No lee contraseñas del código.
    host = e.get('EQUIPARTS_MAIL_SERVER', 'smtp.gmail.com')
    port_text = e.get('EQUIPARTS_MAIL_PORT', '587')
    try:
        port = int(port_text)
    except ValueError:
        print('SMTP: puerto inválido')
        return
    print('SMTP DESTINO:', host, port)
    print('SMTP RED: probando TCP y STARTTLS (NO envía mensajes)')
    try:
        with socket.create_connection((host, port), timeout=8):
            print('TCP: OK')
        if port == 587:
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                smtp.ehlo()
                if not smtp.has_extn('starttls'):
                    print('STARTTLS: servidor no anuncia STARTTLS')
                else:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                    print('STARTTLS: OK')
        else:
            print('STARTTLS: no se prueba automáticamente en puertos distintos de 587')
    except Exception as ex:
        print('SMTP CONEXIÓN:', type(ex).__name__, str(ex)[:180])

    inv = ROOT / 'app/blueprints/inventario.py'
    edit = ROOT / 'app/plantillas/editar_producto.html'
    if inv.exists() and edit.exists():
        code = inv.read_text(encoding='utf-8', errors='replace')
        html = edit.read_text(encoding='utf-8', errors='replace')
        print('FOTOS RUTA ELIMINAR:', 'SÍ' if 'def eliminar_foto_producto(' in code else 'NO')
        print('FOTOS BOTÓN ELIMINAR:', 'SÍ' if 'inventario.eliminar_foto_producto' in html else 'NO')
        print('FOTOS TABLA:', 'consultada desde código' if 'producto_fotos' in code else 'no localizada')
    else:
        print('FOTOS: no se encontraron archivos conocidos')
    print('=== FIN ===')


if __name__ == '__main__':
    main()
