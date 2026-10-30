#!/usr/bin/env python3
"""Solo localhost; configura conexión sin ejecutar SQL ni restablecer cuentas."""
import os,sys,secrets,getpass
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CFG=ROOT/'.equiparts-local.env'
FIELDS=('EQUIPARTS_DB_HOST','EQUIPARTS_DB_USER','EQUIPARTS_DB_NAME','EQUIPARTS_DB_PASSWORD','EQUIPARTS_SECRET_KEY')

def load():
    if not CFG.exists(): return {}
    if CFG.stat().st_mode & 0o077:
        raise RuntimeError('Configuración con permisos inseguros: chmod 600 .equiparts-local.env')
    pairs={}
    for line in CFG.read_text(encoding='utf8').splitlines():
        k,sep,v=line.partition('=')
        if sep and k in FIELDS:pairs[k]=v
    return pairs

def configure():
    print('Configuración de PRUEBA LOCAL. No modifica la base de datos.')
    host=input('Host MariaDB local [localhost]: ').strip() or 'localhost'
    user=input('Usuario MariaDB existente: ').strip()
    db=input('Nombre de la base existente: ').strip()
    password=getpass.getpass('Contraseña de ese usuario MariaDB: ')
    if not all((host,user,db,password)):raise RuntimeError('Faltan datos de la base local.')
    import pymysql
    try:
        conn=pymysql.connect(host=host,user=user,password=password,database=db,connect_timeout=5,read_timeout=5)
        with conn.cursor() as cur:
            cur.execute('SELECT DATABASE()'); name=cur.fetchone()[0]
            cur.execute("SHOW TABLES LIKE 'usuarios'"); present=cur.fetchone() is not None
        conn.close()
        if not present: raise RuntimeError('La base conecta, pero no tiene tabla usuarios. No se guardó configuración.')
    except pymysql.MySQLError as e:
        raise RuntimeError('MariaDB rechazó la conexión. No se modificó nada. Error: '+str(e.args[0])) from None
    result=dict(zip(FIELDS,(host,user,db,password,secrets.token_urlsafe(48))))
    if any('\n' in v or '\r' in v for v in result.values()):raise RuntimeError('Valor de configuración no válido')
    fd=os.open(CFG,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf8') as f:
        for k,v in result.items():f.write(k+'='+v+'\n')
    CFG.chmod(0o600)
    print('Conexión verificada con base:',name)
    return result

def main():
    try:
        if '--configurar' in sys.argv or not all(load().get(k) for k in FIELDS):cfg=configure()
        else:cfg=load()
        os.environ.update(cfg)
        os.environ.update(EQUIPARTS_HOST='127.0.0.1',EQUIPARTS_PORT='5000',EQUIPARTS_HTTPS='0')
        from app import create_app
        app=create_app()
        print('Inicia sesión con tus usuarios EXISTENTES en http://127.0.0.1:5000')
        app.run(debug=False,host='127.0.0.1',port=5000)
    except (RuntimeError,ImportError,OSError) as e:
        print('ERROR:',e,file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
