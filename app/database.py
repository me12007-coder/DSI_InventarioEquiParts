import sqlite3

def get_db_connection():
    # Como ejecutaremos la app desde la raíz, buscará inventario.db ahí
    conn = sqlite3.connect('inventario.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn