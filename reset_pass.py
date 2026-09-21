from werkzeug.security import generate_password_hash
from app.database import get_db_connection

def reset_passwords():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Encriptamos la clave 'admin123'
    nueva_clave = generate_password_hash('admin123')
    
    # Actualizamos la contraseña del usuario 'admin'
    cursor.execute("UPDATE usuarios SET password = %s WHERE username = 'admin'", (nueva_clave,))
    
    # Si el usuario 'admin' no existía, lo creamos desde cero
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO usuarios (username, password, rol, email) VALUES ('admin', %s, 'Administrador', 'admin@equi-parts.com')", (nueva_clave,))
        
    conn.commit()
    cursor.close()
    conn.close()
    print("¡Contraseña de administrador actualizada con éxito en MariaDB!")

if __name__ == '__main__':
    reset_passwords()
