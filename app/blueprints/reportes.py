from flask import Blueprint, render_template, redirect, url_for, session, Response, flash
import csv
import io
from app.database import get_db_connection

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/auditoria')
def auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        flash('No tienes permisos para ver la auditoría.', 'danger')
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    query = '''SELECT m.id AS transaccion_id, m.fecha, m.tipo, m.cantidad, 
               u.username, u.rol, p.sku, p.nombre
               FROM movimientos m 
               LEFT JOIN usuarios u ON m.usuario_id = u.id 
               LEFT JOIN productos p ON m.producto_id = p.id
               ORDER BY m.fecha DESC'''
    logs = conn.execute(query).fetchall()
    conn.close()
    return render_template('auditoria.html', logs=logs, username=session.get('username'))

@reportes_bp.route('/exportar_auditoria')
def exportar_auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    query = '''SELECT m.id, m.fecha, u.username, u.rol, m.tipo, p.sku, p.nombre, m.cantidad
               FROM movimientos m 
               LEFT JOIN usuarios u ON m.usuario_id = u.id 
               LEFT JOIN productos p ON m.producto_id = p.id
               ORDER BY m.fecha DESC'''
    logs = conn.execute(query).fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID Transaccion', 'Fecha', 'Usuario', 'Rol', 'Operacion', 'SKU', 'Repuesto', 'Cantidad'])
    for log in logs:
        cw.writerow([log['id'], log['fecha'], log['username'], log['rol'], log['tipo'], log['sku'], log['nombre'], log['cantidad']])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=auditoria_movimientos.csv"})

@reportes_bp.route('/generar_reporte')
def generar_reporte():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    
    # 1. Calculamos el valor total del inventario (Cantidad * Precio)
    valor_total = conn.execute('SELECT SUM(cantidad * precio) as total FROM productos WHERE activo = 1').fetchone()['total'] or 0.0
    
    # 2. Obtenemos los productos que están en estado crítico
    criticos = conn.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1''').fetchall()
    conn.close()
    
    return render_template('reporte_inventario.html', valor_total=valor_total, criticos=criticos, username=session.get('username'))


@reportes_bp.route('/exportar_reporte_csv')
def exportar_reporte_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    # Obtenemos los productos críticos
    criticos = conn.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1''').fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    # Escribimos los encabezados del Excel/CSV
    cw.writerow(['SKU', 'Repuesto', 'Stock Fisico', 'Stock Reservado', 'Stock Real Disponible', 'Stock Minimo', 'Precio'])
    
    # Llenamos los datos
    for c in criticos:
        stock_real = c['cantidad'] - c['stock_reservado']
        cw.writerow([c['sku'], c['nombre'], c['cantidad'], c['stock_reservado'], stock_real, c['stock_minimo'], c['precio']])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Reporte_Critico_EquiParts.csv"})