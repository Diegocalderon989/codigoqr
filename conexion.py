import pymysql

def conectar_db():
    conexion = pymysql.connect(
        host='localhost',
        user='root',
        password='123456',
        database='codigoqr',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return conexion
