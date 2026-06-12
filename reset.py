import sqlite3
from werkzeug.security import generate_password_hash

def reset_passwords():
    conn = sqlite3.connect('inventario.db')
    
    # Encriptamos la clave 'admin123' con el nuevo sistema de seguridad
    nueva_clave = generate_password_hash('admin123')
    
    # Actualizamos la contraseña del usuario 'admin'
    cursor = conn.execute("UPDATE usuarios SET password = ? WHERE username = 'admin'", (nueva_clave,))
    
    # Si el usuario 'admin' no existía por alguna razón, lo creamos desde cero
    if cursor.rowcount == 0:
        conn.execute("INSERT INTO usuarios (username, password, rol, email) VALUES ('admin', ?, 'Administrador', 'admin@equi-parts.com')", (nueva_clave,))
        
    conn.commit()
    conn.close()
    print("¡Contraseña de administrador actualizada con éxito!")

if __name__ == '__main__':
    reset_passwords()
