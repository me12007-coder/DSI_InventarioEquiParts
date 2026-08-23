from flask import Blueprint, render_template, redirect, url_for, session, Response, flash, request
import csv
import io
from datetime import datetime
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
    
    # 1. Calculamos el valor total del inventario
    valor_total = conn.execute('SELECT SUM(cantidad * precio) as total FROM productos WHERE activo = 1').fetchone()['total'] or 0.0
    
    # 2. Obtenemos los productos críticos ORDENADOS por gravedad (los de menor stock de primero)
    criticos = conn.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1
                               ORDER BY (cantidad - stock_reservado) ASC''').fetchall()
    conn.close()
    
    return render_template('reporte_inventario.html', valor_total=valor_total, criticos=criticos, username=session.get('username'))

@reportes_bp.route('/exportar_reporte_csv')
def exportar_reporte_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    criticos = conn.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1
                               ORDER BY (cantidad - stock_reservado) ASC''').fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    # Agregamos la columna 'Estado' al CSV
    cw.writerow(['SKU', 'Repuesto', 'Stock Fisico', 'Stock Reservado', 'Stock Real Disponible', 'Stock Minimo', 'Precio', 'Estado'])
    
    for c in criticos:
        stock_real = c['cantidad'] - c['stock_reservado']
        # Lógica de clasificación para el CSV
        estado = 'Agotado (Crítico)' if stock_real <= 0 else 'Por Agotarse'
        cw.writerow([c['sku'], c['nombre'], c['cantidad'], c['stock_reservado'], stock_real, c['stock_minimo'], c['precio'], estado])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Reporte_Critico_EquiParts.csv"})

# --- NUEVO CÓDIGO PARA HU-24: INVENTARIO HISTÓRICO ---
@reportes_bp.route('/reporte_historico', methods=['GET', 'POST'])
def reporte_historico():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    productos = []
    fecha_consulta = ""

    if request.method == 'POST':
        fecha_consulta = request.form.get('fecha_limite')
        
        if fecha_consulta:
            fecha_fin = f"{fecha_consulta} 23:59:59"
            prod_actuales = conn.execute('SELECT id, sku, nombre, descripcion, cantidad FROM productos WHERE activo = 1').fetchall()
            
            for p in prod_actuales:
                movs = conn.execute('''SELECT tipo, cantidad FROM movimientos 
                                       WHERE producto_id = ? AND fecha > ?''', (p['id'], fecha_fin)).fetchall()
                
                stock_historico = p['cantidad']
                
                for m in movs:
                    tipo = str(m['tipo'])
                    cant = m['cantidad']
                    
                    if tipo == 'Entrada' or tipo.startswith('Devolución'):
                        stock_historico -= cant
                    elif tipo in ['Salida', 'Venta_Cotizacion']:
                        stock_historico += cant
                    elif tipo.startswith('Ajuste'):
                        stock_historico -= cant 
                
                productos.append({
                    'sku': p['sku'],
                    'nombre': p['nombre'],
                    'descripcion': p['descripcion'],
                    'cantidad_historica': max(0, stock_historico)
                })

    conn.close()
    return render_template('reporte_historico.html', productos=productos, fecha_consulta=fecha_consulta, username=session.get('username'))

@reportes_bp.route('/exportar_historico_csv')
def exportar_historico_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    fecha_consulta = request.args.get('fecha')
    if not fecha_consulta:
        return redirect(url_for('reportes.reporte_historico'))
        
    conn = get_db_connection()
    fecha_fin = f"{fecha_consulta} 23:59:59"
    prod_actuales = conn.execute('SELECT id, sku, nombre, descripcion, cantidad FROM productos WHERE activo = 1').fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Codigo (SKU)', 'Nombre del Repuesto', 'Descripcion', f'Cantidad Calculada al {fecha_consulta}'])
    
    for p in prod_actuales:
        movs = conn.execute('''SELECT tipo, cantidad FROM movimientos 
                               WHERE producto_id = ? AND fecha > ?''', (p['id'], fecha_fin)).fetchall()
        stock_historico = p['cantidad']
        
        for m in movs:
            tipo = str(m['tipo'])
            cant = m['cantidad']
            if tipo == 'Entrada' or tipo.startswith('Devolución'):
                stock_historico -= cant
            elif tipo in ['Salida', 'Venta_Cotizacion']:
                stock_historico += cant
            elif tipo.startswith('Ajuste'):
                stock_historico -= cant 
        
        cw.writerow([p['sku'], p['nombre'], p['descripcion'] or 'Sin descripcion', max(0, stock_historico)])
    
    conn.close()
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Inventario_Historico_{fecha_consulta}.csv"})

# --- NUEVO CÓDIGO PARA HU-25: FLUJO DE ENTRADAS Y SALIDAS ---
@reportes_bp.route('/flujo_movimientos', methods=['GET'])
def flujo_movimientos():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    # Capturamos los filtros de la URL (si existen)
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    conn = get_db_connection()
    
    # AGREGAMOS m.id A LA CONSULTA PARA PODER ABRIR EL COMPROBANTE
    query = '''SELECT m.id, p.sku, p.nombre, m.tipo, m.fecha, m.cantidad, u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    
    # 1. Filtro por rango de fechas
    if fecha_inicio:
        query += ' AND m.fecha >= ?'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= ?'
        params.append(f"{fecha_fin} 23:59:59")
        
    # 2. Filtro por tipo de movimiento
    if tipo_filtro == 'Entradas':
        query += " AND (m.tipo = 'Entrada' OR m.tipo LIKE 'Devolución%' OR m.tipo = 'Creación de Producto')"
    elif tipo_filtro == 'Salidas':
        query += " AND (m.tipo IN ('Salida', 'Venta_Cotizacion', 'Eliminación de Producto'))"
    elif tipo_filtro == 'Ajustes':
        query += " AND m.tipo LIKE 'Ajuste%'"
        
    # 3. Orden cronológico descendente (el más reciente primero)
    query += ' ORDER BY m.fecha DESC'
    
    movimientos = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('reporte_movimientos.html', 
                           movimientos=movimientos, 
                           fecha_inicio=fecha_inicio, 
                           fecha_fin=fecha_fin, 
                           tipo_filtro=tipo_filtro,
                           username=session.get('username'))

@reportes_bp.route('/exportar_flujo_csv', methods=['GET'])
def exportar_flujo_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
        
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    conn = get_db_connection()
    query = '''SELECT p.sku, p.nombre, m.tipo, m.fecha, m.cantidad, u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    
    if fecha_inicio:
        query += ' AND m.fecha >= ?'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= ?'
        params.append(f"{fecha_fin} 23:59:59")
        
    if tipo_filtro == 'Entradas':
        query += " AND (m.tipo = 'Entrada' OR m.tipo LIKE 'Devolución%' OR m.tipo = 'Creación de Producto')"
    elif tipo_filtro == 'Salidas':
        query += " AND (m.tipo IN ('Salida', 'Venta_Cotizacion', 'Eliminación de Producto'))"
    elif tipo_filtro == 'Ajustes':
        query += " AND m.tipo LIKE 'Ajuste%'"
        
    query += ' ORDER BY m.fecha DESC'
    movimientos = conn.execute(query, params).fetchall()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Codigo (SKU)', 'Repuesto', 'Tipo de Movimiento', 'Fecha', 'Cantidad', 'Responsable'])
    
    for m in movimientos:
        cw.writerow([m['sku'], m['nombre'], m['tipo'], m['fecha'], m['cantidad'], m['responsable']])
        
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Flujo_Movimientos_{tipo_filtro}.csv"})

    
