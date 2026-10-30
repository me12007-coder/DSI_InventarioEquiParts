import pymysql
import os

def get_db_connection():
    # Retorna la conexión a MariaDB. Asegúrate de que el nombre de esta función 
    # coincida con el que ya usabas en tus blueprints (ej. get_db o get_connection)
    return pymysql.connect(
        host=os.getenv('EQUIPARTS_DB_HOST', 'localhost'),
        user=os.getenv('EQUIPARTS_DB_USER', 'equiparts_user'),
        password=os.environ['EQUIPARTS_DB_PASSWORD'],
        database=os.getenv('EQUIPARTS_DB_NAME', 'equiparts_db'),
        cursorclass=pymysql.cursors.DictCursor
    )
