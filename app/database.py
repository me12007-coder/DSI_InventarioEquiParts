import pymysql

def get_db_connection():
    # Retorna la conexión a MariaDB. Asegúrate de que el nombre de esta función 
    # coincida con el que ya usabas en tus blueprints (ej. get_db o get_connection)
    return pymysql.connect(
        host='localhost',
        user='equiparts_user',
        password='XG0szw$G',
        database='equiparts_db',
        cursorclass=pymysql.cursors.DictCursor
    )
