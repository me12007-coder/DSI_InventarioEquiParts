import sqlite3

def init_db():
    conn = sqlite3.connect('inventario.db')
    cursor = conn.cursor()

    # Tabla de usuarios con EMAIL
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE NOT NULL, 
            password TEXT NOT NULL, 
            rol TEXT NOT NULL,
            email TEXT)''') # Se agregó email

    # Tabla de categorías
    cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nombre TEXT UNIQUE NOT NULL)''')

    # Tabla de productos con STOCK MÍNIMO
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            sku TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL, 
            descripcion TEXT, 
            cantidad INTEGER NOT NULL DEFAULT 0,
            stock_reservado INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5, -- Se agregó stock mínimo
            precio REAL NOT NULL, 
            categoria_id INTEGER, 
            ubicacion TEXT,
            foto TEXT, 
            ficha_pdf TEXT,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (categoria_id) REFERENCES categorias (id))''')

    # Tabla de movimientos
    cursor.execute('''CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            producto_id INTEGER,
            usuario_id INTEGER, 
            tipo TEXT NOT NULL, 
            cantidad INTEGER NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')

    # Intentar actualizar tablas existentes sin borrar datos (Migraciones manuales)
    try: conn.execute('ALTER TABLE usuarios ADD COLUMN email TEXT')
    except sqlite3.OperationalError: pass

    try: conn.execute('ALTER TABLE productos ADD COLUMN stock_minimo INTEGER NOT NULL DEFAULT 5')
    except sqlite3.OperationalError: pass

    # Cuentas por defecto
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol, email) VALUES ('admin', 'scrypt:32768:8:1$12345$hashdummy', 'Administrador', 'admin@equi-parts.com')")
    
    conn.commit()
    conn.close()
    print("¡BD actualizada con Email de usuarios y Stock Mínimo!")

if __name__ == '__main__':
    init_db()