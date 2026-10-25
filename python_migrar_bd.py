import sys
import os

# Aseguramos que Python encuentre el módulo 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db_connection
import pymysql

def actualizar_base_datos():
    print("Conectando a MariaDB...")
    try:
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        print("Ejecutando actualización en la tabla 'usuarios'...")
        cursor.execute("ALTER TABLE usuarios ADD COLUMN activo BOOLEAN DEFAULT 1;")
        conexion.commit()
        
        print("✅ ¡Éxito! La columna 'activo' se agregó correctamente.")
        
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1060: # Código de error de MySQL/MariaDB para "Duplicate column name"
            print("⚠️ La columna 'activo' ya existe en la base de datos. Todo está listo.")
        else:
            print(f"❌ Error operativo: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conexion' in locals():
            conexion.close()

if __name__ == "__main__":
    actualizar_base_datos()