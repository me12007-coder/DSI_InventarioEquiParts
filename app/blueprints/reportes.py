from flask import Blueprint, render_template, redirect, url_for, session, Response, flash, request
import csv
import io
from datetime import datetime, date
from app.database import get_db_connection

reportes_bp = Blueprint('reportes', __name__)

# --- NUEVA FUNCIÓN DE VALIDACIÓN ---
def validar_fechas(fecha_str_1, fecha_str_2=None):
    """Retorna (es_valido, mensaje_error)"""
    try:
        dt1 = datetime.strptime(fecha_str_1, '%Y-%m-%d') if fecha_str_1 else None
        dt2 = datetime.strptime(fecha_str_2, '%Y-%m-%d') if fecha_str_2 else None
        
        if (dt1 and dt1.year < 2024) or (dt2 and dt2.year < 2024):
            return False, "No se permiten reportes con fechas anteriores al año 2024."
            
        if (dt1 and dt1.date() > date.today()) or (dt2 and dt2.date() > date.today()):
            return False, "No se permiten fechas futuras en los reportes históricos."
        if dt1 and dt2 and dt1 > dt2:
            return False, "La fecha de inicio no puede ser mayor a la fecha de fin."
            
        return True, ""
    except ValueError:
        return False, "Formato de fecha inválido."

@reportes_bp.route('/auditoria')
def auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        flash('No tienes permisos para ver la auditoría.', 'danger')
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''SELECT m.id AS transaccion_id, m.fecha, m.tipo, m.cantidad, 
               u.username, u.rol, p.sku, p.nombre
               FROM movimientos m 
               LEFT JOIN usuarios u ON m.usuario_id = u.id 
               LEFT JOIN productos p ON m.producto_id = p.id
               ORDER BY m.fecha DESC'''
    cursor.execute(query)
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('auditoria.html', logs=logs, username=session.get('username'))

@reportes_bp.route('/exportar_auditoria')
def exportar_auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''SELECT m.id, m.fecha, u.username, u.rol, m.tipo, p.sku, p.nombre, m.cantidad
               FROM movimientos m 
               LEFT JOIN usuarios u ON m.usuario_id = u.id 
               LEFT JOIN productos p ON m.producto_id = p.id
               ORDER BY m.fecha DESC'''
    cursor.execute(query)
    logs = cursor.fetchall()
    cursor.close()
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
    cursor = conn.cursor()
    
    # 1. Calculamos el valor total del inventario
    cursor.execute('SELECT SUM(cantidad * precio) as total FROM productos WHERE activo = 1')
    row = cursor.fetchone()
    valor_total = row['total'] if row and row['total'] else 0.0
    
    # 2. Obtenemos los productos críticos ORDENADOS por gravedad (los de menor stock de primero)
    cursor.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1
                               ORDER BY (cantidad - stock_reservado) ASC''')
    criticos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('reporte_inventario.html', valor_total=valor_total, criticos=criticos, username=session.get('username'))

@reportes_bp.route('/exportar_reporte_csv')
def exportar_reporte_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT sku, nombre, cantidad, stock_reservado, stock_minimo, precio 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1
                               ORDER BY (cantidad - stock_reservado) ASC''')
    criticos = cursor.fetchall()
    cursor.close()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['SKU', 'Repuesto', 'Stock Fisico', 'Stock Reservado', 'Stock Real Disponible', 'Stock Minimo', 'Precio', 'Estado'])
    
    for c in criticos:
        stock_real = c['cantidad'] - c['stock_reservado']
        estado = 'Agotado (Crítico)' if stock_real <= 0 else 'Por Agotarse'
        cw.writerow([c['sku'], c['nombre'], c['cantidad'], c['stock_reservado'], stock_real, c['stock_minimo'], c['precio'], estado])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Reporte_Critico_EquiParts.csv"})

@reportes_bp.route('/reporte_historico', methods=['GET', 'POST'])
def reporte_historico():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    productos = []
    fecha_consulta = ""

    if request.method == 'POST':
        fecha_consulta = request.form.get('fecha_limite')
        
        # VALIDACIÓN AQUÍ
        if fecha_consulta:
            valido, msg = validar_fechas(fecha_consulta)
            if not valido:
                flash(msg, 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('reportes.reporte_historico'))
                
            fecha_fin = f"{fecha_consulta} 23:59:59"
            cursor.execute('SELECT id, sku, nombre, descripcion, cantidad FROM productos WHERE activo = 1')
            # ... (el resto del bucle for se mantiene exactamente igual) ...
            prod_actuales = cursor.fetchall()
            
            for p in prod_actuales:
                cursor.execute('''SELECT tipo, cantidad FROM movimientos 
                                       WHERE producto_id = %s AND fecha > %s''', (p['id'], fecha_fin))
                movs = cursor.fetchall()
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

    cursor.close()
    conn.close()
    return render_template('reporte_historico.html', productos=productos, fecha_consulta=fecha_consulta, username=session.get('username'))

@reportes_bp.route('/exportar_historico_csv')
def exportar_historico_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    fecha_consulta = request.args.get('fecha')
    valido, mensaje = validar_fechas(fecha_consulta)
    if not valido:
        flash(mensaje, 'danger')
        return redirect(url_for('reportes.reporte_historico'))
    if not fecha_consulta:
        return redirect(url_for('reportes.reporte_historico'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    fecha_fin = f"{fecha_consulta} 23:59:59"
    cursor.execute('SELECT id, sku, nombre, descripcion, cantidad FROM productos WHERE activo = 1')
    prod_actuales = cursor.fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Codigo (SKU)', 'Nombre del Repuesto', 'Descripcion', f'Cantidad Calculada al {fecha_consulta}'])
    
    for p in prod_actuales:
        cursor.execute('''SELECT tipo, cantidad FROM movimientos 
                               WHERE producto_id = %s AND fecha > %s''', (p['id'], fecha_fin))
        movs = cursor.fetchall()
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
    
    cursor.close()
    conn.close()
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Inventario_Historico_{fecha_consulta}.csv"})

@reportes_bp.route('/flujo_movimientos', methods=['GET'])
def flujo_movimientos():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    valido, mensaje = validar_fechas(fecha_inicio, fecha_fin)
    if not valido:
        flash(mensaje, 'danger')
        return redirect(url_for('reportes.flujo_movimientos'))
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''SELECT m.id, p.sku, p.nombre, m.tipo, m.fecha, m.cantidad, u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    
    if fecha_inicio:
        query += ' AND m.fecha >= %s'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= %s'
        params.append(f"{fecha_fin} 23:59:59")
        
    if tipo_filtro == 'Entradas':
        query += " AND (m.tipo = 'Entrada' OR m.tipo LIKE 'Devolución%%' OR m.tipo = 'Creación de Producto')"
    elif tipo_filtro == 'Salidas':
        query += " AND (m.tipo IN ('Salida', 'Venta_Cotizacion', 'Eliminación de Producto'))"
    elif tipo_filtro == 'Ajustes':
        query += " AND m.tipo LIKE 'Ajuste%%'"
        
    query += ' ORDER BY m.fecha DESC'
    
    cursor.execute(query, params)
    movimientos = cursor.fetchall()
    cursor.close()
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
    valido, mensaje = validar_fechas(fecha_inicio, fecha_fin)
    if not valido:
        flash(mensaje, 'danger')
        return redirect(url_for('reportes.flujo_movimientos'))
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''SELECT p.sku, p.nombre, m.tipo, m.fecha, m.cantidad, u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    
    if fecha_inicio:
        query += ' AND m.fecha >= %s'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= %s'
        params.append(f"{fecha_fin} 23:59:59")
        
    if tipo_filtro == 'Entradas':
        query += " AND (m.tipo = 'Entrada' OR m.tipo LIKE 'Devolución%%' OR m.tipo = 'Creación de Producto')"
    elif tipo_filtro == 'Salidas':
        query += " AND (m.tipo IN ('Salida', 'Venta_Cotizacion', 'Eliminación de Producto'))"
    elif tipo_filtro == 'Ajustes':
        query += " AND m.tipo LIKE 'Ajuste%%'"
        
    query += ' ORDER BY m.fecha DESC'
    cursor.execute(query, params)
    movimientos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Codigo (SKU)', 'Repuesto', 'Tipo de Movimiento', 'Fecha', 'Cantidad', 'Responsable'])
    
    for m in movimientos:
        cw.writerow([m['sku'], m['nombre'], m['tipo'], m['fecha'], m['cantidad'], m['responsable']])
        
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Flujo_Movimientos_{tipo_filtro}.csv"})

@reportes_bp.route('/flujo_valorizado', methods=['GET'])
def flujo_valorizado():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    # --- INICIO DE VALIDACIÓN DE FECHAS ---
    valido, msg = validar_fechas(fecha_inicio, fecha_fin)
    if not valido:
        flash(msg, 'danger')
        return redirect(url_for('reportes.flujo_valorizado'))
    # --- FIN DE VALIDACIÓN ---
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # IMPORTANTE: Usamos COALESCE para evitar los errores NoneType cuando el producto es NULL
    query = '''SELECT m.id, 
                      COALESCE(p.sku, 'N/A') as sku, 
                      COALESCE(p.nombre, 'Registro Global') as nombre, 
                      m.tipo, m.fecha, m.cantidad, 
                      COALESCE(p.precio, 0) as precio, 
                      COALESCE(m.cantidad * p.precio, 0) as total_movimiento, 
                      u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    
    if fecha_inicio:
        query += ' AND m.fecha >= %s'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= %s'
        params.append(f"{fecha_fin} 23:59:59")
    if tipo_filtro == 'Entradas':
        query += " AND (m.tipo = 'Entrada' OR m.tipo LIKE 'Devolución%%' OR m.tipo = 'Creación de Producto')"
    elif tipo_filtro == 'Salidas':
        query += " AND (m.tipo IN ('Salida', 'Venta_Cotizacion', 'Eliminación de Producto'))"
    elif tipo_filtro == 'Ajustes':
        query += " AND m.tipo LIKE 'Ajuste%%'"
        
    query += ' ORDER BY m.fecha DESC'
    cursor.execute(query, params)
    movimientos = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('flujo_valorizado.html', 
                           movimientos=movimientos, 
                           fecha_inicio=fecha_inicio, 
                           fecha_fin=fecha_fin, 
                           tipo_filtro=tipo_filtro,
                           username=session.get('username'))

@reportes_bp.route('/exportar_flujo_valorizado_csv', methods=['GET'])
def exportar_flujo_valorizado_csv():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
        
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    valido, mensaje = validar_fechas(fecha_inicio, fecha_fin)
    if not valido:
        flash(mensaje, 'danger')
        return redirect(url_for('reportes.flujo_movimientos'))
    tipo_filtro = request.args.get('tipo_filtro', 'Todos')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Misma corrección de COALESCE para evitar caídas en el CSV
    query = '''SELECT COALESCE(p.sku, 'N/A') as sku, 
                      COALESCE(p.nombre, 'Registro Global') as nombre, 
                      m.tipo, m.fecha, m.cantidad, 
                      COALESCE(p.precio, 0) as precio, 
                      COALESCE(m.cantidad * p.precio, 0) as total_movimiento, 
                      u.username as responsable
               FROM movimientos m
               LEFT JOIN productos p ON m.producto_id = p.id
               LEFT JOIN usuarios u ON m.usuario_id = u.id
               WHERE 1=1'''
    params = []
    if fecha_inicio:
        query += ' AND m.fecha >= %s'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query += ' AND m.fecha <= %s'
        params.append(f"{fecha_fin} 23:59:59")
        
    query += ' ORDER BY m.fecha DESC'
    cursor.execute(query, params)
    movimientos = cursor.fetchall()
    cursor.close()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Fecha', 'SKU', 'Repuesto', 'Operacion', 'Cantidad', 'Precio Unitario', 'Valor Total', 'Responsable'])
    for m in movimientos:
        cw.writerow([m['fecha'], m['sku'], m['nombre'], m['tipo'], m['cantidad'], f"${m['precio']:.2f}", f"${m['total_movimiento']:.2f}", m['responsable']])
        
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Flujo_Valorizado.csv"})

@reportes_bp.route('/estado_financiero', methods=['GET'])
def estado_financiero():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')
    valido, mensaje = validar_fechas(fecha_inicio, fecha_fin)
    if not valido:
        flash(mensaje, 'danger')
        return redirect(url_for('reportes.flujo_movimientos'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Valor actual total
    cursor.execute('SELECT SUM(cantidad * precio) as total FROM productos WHERE activo = 1')
    valor_actual = cursor.fetchone()['total'] or 0.0

    # 2. Resumen de movimientos en el periodo
    query_movs = '''SELECT m.tipo, SUM(m.cantidad * p.precio) as total_valor
                    FROM movimientos m
                    JOIN productos p ON m.producto_id = p.id
                    WHERE 1=1'''
    params = []
    if fecha_inicio:
        query_movs += ' AND m.fecha >= %s'
        params.append(f"{fecha_inicio} 00:00:00")
    if fecha_fin:
        query_movs += ' AND m.fecha <= %s'
        params.append(f"{fecha_fin} 23:59:59")
    query_movs += ' GROUP BY m.tipo'
    
    cursor.execute(query_movs, params)
    res_movs = cursor.fetchall()
    
    entradas = 0.0
    salidas = 0.0
    ajustes = 0.0
    
    for r in res_movs:
        tipo = r['tipo']
        val = float(r['total_valor']) if r['total_valor'] else 0.0
        
        if 'Entrada' in tipo or 'Devolución' in tipo or 'Creación' in tipo:
            entradas += val
        elif 'Salida' in tipo or 'Venta' in tipo:
            salidas += val
        elif 'Ajuste' in tipo:
            ajustes += val

    # 3. Desglose del valor actual por categoría
    cursor.execute('''SELECT c.nombre, SUM(p.cantidad) as total_items, SUM(p.cantidad * p.precio) as valor_total
                      FROM productos p
                      LEFT JOIN categorias c ON p.categoria_id = c.id
                      WHERE p.activo = 1
                      GROUP BY c.id, c.nombre
                      ORDER BY valor_total DESC''')
    categorias_valor = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('estado_financiero.html', 
                           valor_actual=valor_actual,
                           entradas=entradas,
                           salidas=salidas,
                           ajustes=ajustes,
                           categorias_valor=categorias_valor,
                           fecha_inicio=fecha_inicio,
                           fecha_fin=fecha_fin,
                           username=session.get('username'))

@reportes_bp.route('/personalizado', methods=['GET', 'POST'])
def reporte_personalizado():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    columnas_disponibles = {
        'sku': 'Código (SKU)',
        'nombre': 'Nombre del Repuesto',
        'categoria_nombre': 'Categoría',
        'descripcion': 'Descripción',
        'ubicacion': 'Ubicación en Bodega',
        'cantidad': 'Stock Físico Actual',
        'stock_minimo': 'Límite de Alerta',
        'precio': 'Precio Unitario ($)',
        'valor_total': 'Valor Totalizado ($)'
    }
    
    columnas_seleccionadas = []
    productos_data = []

    if request.method == 'POST':
        columnas_seleccionadas = request.form.getlist('columnas')
        accion = request.form.get('accion') 
        
        if not columnas_seleccionadas:
            flash('Debe seleccionar al menos una columna para generar el reporte.', 'warning')
            return redirect(url_for('reportes.reporte_personalizado'))
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT p.*, c.nombre as categoria_nombre 
                          FROM productos p 
                          LEFT JOIN categorias c ON p.categoria_id = c.id 
                          WHERE p.activo = 1''')
        productos = cursor.fetchall()
        
        for p in productos:
            p_dict = dict(p)
            p_dict['valor_total'] = float(p['cantidad'] * p['precio'])
            if not p_dict['categoria_nombre']:
                p_dict['categoria_nombre'] = 'Sin Categoría'
            productos_data.append(p_dict)
            
        cursor.close()
        conn.close()

        if accion == 'csv':
            si = io.StringIO()
            cw = csv.writer(si)
            
            headers = [columnas_disponibles[col] for col in columnas_seleccionadas]
            cw.writerow(headers)
            
            for p in productos_data:
                row = []
                for col in columnas_seleccionadas:
                    val = p.get(col, '')
                    if col in ['precio', 'valor_total']:
                        val = f"${float(val):.2f}"
                    row.append(val)
                cw.writerow(row)
            
            output = si.getvalue()
            return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Reporte_A_Medida.csv"})

    return render_template('reporte_personalizado.html', 
                           columnas_disponibles=columnas_disponibles,
                           columnas_seleccionadas=columnas_seleccionadas,
                           productos=productos_data,
                           username=session.get('username'))

@reportes_bp.route('/auditoria/purgar_global', methods=['POST'])
def purgar_auditoria_global():
    if 'user_id' not in session or session.get('rol') != 'Administrador':
        return "<script>alert('Acceso denegado'); window.close();</script>"
    
    pwd = request.form.get('password_admin', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT password FROM usuarios WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()
    
    from werkzeug.security import check_password_hash
    es_valida = False
    try:
        es_valida = check_password_hash(user['password'], pwd)
    except:
        es_valida = (user['password'] == pwd)
        
    if not es_valida:
        cursor.close()
        conn.close()
        return "<script>alert('Error: Contraseña de administrador incorrecta.'); window.close();</script>"
        
    cursor.execute('''SELECT m.id, m.fecha, u.username, m.tipo, p.sku, p.nombre, m.cantidad 
                      FROM movimientos m 
                      LEFT JOIN usuarios u ON m.usuario_id = u.id 
                      LEFT JOIN productos p ON m.producto_id = p.id
                      ORDER BY m.fecha DESC''')
    historial = cursor.fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['EQUIPARTS S&S - RESPALDO MAESTRO DE AUDITORIA (PURGA GLOBAL)'])
    cw.writerow(['Ejecutado por:', session.get('username'), 'Fecha de Purga:', datetime.now().strftime('%Y-%m-%d %H:%M')])
    cw.writerow([])
    cw.writerow(['ID Trans.', 'Fecha', 'Operario', 'Movimiento', 'SKU', 'Producto', 'Cantidad'])
    
    for h in historial:
        cw.writerow([h['id'], h['fecha'], h['username'], h['tipo'], h['sku'], h['nombre'], h['cantidad']])
        
    output = si.getvalue()
    
    cursor.execute('DELETE FROM movimientos')
    
    try:
        cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                          VALUES (NULL, %s, 'Purga Global de Sistema (CSV Respaldo Descargado)', 0)''', 
                       (session['user_id'],))
    except Exception as e:
        pass

    conn.commit()
    cursor.close()
    conn.close()
    
    return Response(
        output, 
        mimetype="text/csv", 
        headers={"Content-Disposition": f"attachment;filename=Respaldo_Maestro_Auditoria_{datetime.now().strftime('%Y%m%d')}.csv"}
    )