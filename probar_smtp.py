#!/usr/bin/env python3
"""Diagnóstico SMTP. No envía correo salvo con --enviar-prueba."""
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from shlex import split

archivo = Path('/etc/equiparts/equiparts.env')
if not archivo.is_file():
    raise SystemExit('No existe el archivo de configuración de Equi-Parts.')
cfg = {}
for linea in archivo.read_text(encoding='utf8').splitlines():
    linea = linea.strip()
    if linea and not linea.startswith('#') and '=' in linea:
        try:
            partes = split(linea, posix=True)
            if len(partes) == 1 and '=' in partes[0]:
                k, v = partes[0].split('=', 1)
                cfg[k] = v
        except ValueError:
            raise SystemExit('No pudo interpretarse el archivo de entorno.')
usuario = cfg.get('EQUIPARTS_MAIL_USERNAME', '').strip()
password = ''.join(cfg.get('EQUIPARTS_MAIL_PASSWORD', '').split())
if not usuario or not password:
    raise SystemExit('Faltan variables EQUIPARTS_MAIL_USERNAME / PASSWORD.')


enviar_prueba = '--enviar-prueba' in sys.argv

def prueba_entrega(client):
    if not enviar_prueba:
        return
    mensaje = EmailMessage()
    mensaje['From'] = usuario
    mensaje['To'] = usuario
    mensaje['Subject'] = 'Prueba de correo Equi-Parts S&S'
    mensaje.set_content('Prueba SMTP manual autorizada. No modifica inventario.')
    client.send_message(mensaje)
    print('ENVIO A LA MISMA CASILLA: ACEPTADO POR SMTP (verifica la bandeja y spam)')

def probar(port):
    print(f'Puerto {port}: conectando...')
    etapa = 'conexión'
    try:
        if port == 587:
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as client:
                client.ehlo()
                etapa = 'STARTTLS'
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
                etapa = 'autenticación'
                client.login(usuario, password)
                prueba_entrega(client)
        else:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15, context=ssl.create_default_context()) as client:
                client.ehlo()
                etapa = 'autenticación'
                client.login(usuario, password)
                prueba_entrega(client)
        print(f'Puerto {port}: AUTENTICACION CORRECTA' + ('; prueba de envio solicitada' if enviar_prueba else ' (sin enviar mensajes)'))
        return True
    except smtplib.SMTPAuthenticationError as exc:
        print(f'Puerto {port}: AUTH RECHAZADA, código {exc.smtp_code}')
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        print(f'Puerto {port}: fallo en {etapa}: {type(exc).__name__}')
    return False

ok587 = probar(587)
if not ok587:
    ok465 = probar(465)
    if ok465:
        print('SOLUCION: añade EQUIPARTS_MAIL_PORT="465" al .env y reinicia el servicio.')
    else:
        print('El SMTP continúa rechazando/interrumpiendo la autenticación. Revisar política Google Workspace o credenciales.')
else:
    print('SOLUCION: usa el puerto 587 (predeterminado) y verifica un correo de alerta controlado.')
