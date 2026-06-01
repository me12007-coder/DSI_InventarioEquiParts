# bd.py
import sqlite3

def init_db():
    conn = sqlite3.connect('inventario.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, 
            password TEXT NOT NULL, rol TEXT NOT NULL)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE NOT NULL)''')

    # SE AGREGÓ: stock_reservado
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL, descripcion TEXT, 
            cantidad INTEGER NOT NULL DEFAULT 0,
            stock_reservado INTEGER NOT NULL DEFAULT 0,
            precio REAL NOT NULL, categoria_id INTEGER, ubicacion TEXT,
            foto TEXT, ficha_pdf TEXT,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER,
            usuario_id INTEGER, tipo TEXT NOT NULL, cantidad INTEGER NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')

    # Cuentas por defecto para pruebas
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES ('admin', 'admin123', 'Administrador')")
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES ('bodega', 'bodega123', 'Bodeguero')")
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES ('ventas', 'ventas123', 'Vendedor')")
    cursor.execute("INSERT OR IGNORE INTO categorias (nombre) VALUES ('Motor'), ('Suspensión'), ('Frenos')")

    conn.commit()
    conn.close()
    print("¡BD actualizada con Reservas de Stock y nuevos roles!")

if __name__ == '__main__':
    init_db()
