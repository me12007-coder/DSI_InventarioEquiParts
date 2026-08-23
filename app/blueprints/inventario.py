from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify, Response
from werkzeug.utils import secure_filename
from threading import Thread
import os
import csv
import io

# Importaciones locales de tu arquitectura
from app.database import get_db_connection
from app.services.email_service import enviar_alerta_stock

inventario_bp = Blueprint('inventario', __name__)

@inventario_bp.route('/inventario', methods=['GET', 'POST'])
def inventario():
    if 'user_id' not in session: 
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST' and session.get('rol') in ['Administrador', 'Bodeguero']:
        foto = request.files.get('foto')
        pdf = request.files.get('pdf')
        foto_path = secure_filename(foto.filename) if foto and foto.filename else ""
        pdf_path = secure_filename(pdf.filename) if pdf and pdf.filename else ""
        
        # Guardar archivos
        if foto_path: 
            foto.save(os.path.join(current_app.config['UPLOAD_FOLDER'], foto_path))
        if pdf_path: 
            pdf.save(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_path))

        data = request.form
        sku = str(data.get('sku', '')).strip()
        nombre = str(data.get('nombre', '')).strip()
        descripcion = str(data.get('descripcion', '')).strip()
        cantidad = int(data.get('cantidad', 0))
        stock_minimo = int(data.get('stock_minimo', 5)) 
        precio = float(data.get('precio', 0.0))
        ubicacion = str(data.get('ubicacion', '')).strip()
        cat_id_raw = data.get('categoria_id')
        categoria_id = int(cat_id_raw) if cat_id_raw else None

        try:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO productos (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion, foto, ficha_pdf, activo) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                           (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion, foto_path, pdf_path))
            nuevo_id = cursor.lastrowid
            
            cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                              VALUES (?, ?, 'Creación de Producto', ?)''', 
                           (nuevo_id, session['user_id'], cantidad))
            conn.commit()
            flash('Producto creado exitosamente.', 'success')
        except Exception as e:
            flash('Error al crear el producto (Verifique que el SKU no exista).', 'danger')

    busqueda = request.args.get('q', '')
    query = '''SELECT p.*, c.nombre as categoria_nombre FROM productos p 
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.activo = 1 AND (p.sku LIKE ? OR p.nombre LIKE ?)'''
    productos = conn.execute(query, ('%'+busqueda+'%', '%'+busqueda+'%')).fetchall()
    categorias = conn.execute('SELECT * FROM categorias').fetchall()
    
    # Evaluar alertas de stock crítico para los popups
    alertas_stock = []
    for p in productos:
        stock_real = p['cantidad'] - p['stock_reservado']
        if stock_real <= p['stock_minimo']:
            alertas_stock.append({'nombre': p['nombre'], 'stock': stock_real, 'minimo': p['stock_minimo']})
            
    conn.close()
    
    return render_template('inventario.html', productos=productos, categorias=categorias, 
                           username=session.get('username'), rol=session.get('rol'), 
                           busqueda=busqueda, alertas_stock=alertas_stock)

@inventario_bp.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.form
        cat_raw = data.get('categoria_id')
        categoria_id = int(cat_raw) if cat_raw else None
        
        conn.execute('''UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, ubicacion = ?, categoria_id = ?, cantidad = ?
                        WHERE id = ?''', 
                     (str(data.get('nombre')), str(data.get('descripcion')), float(data.get('precio')), 
                      str(data.get('ubicacion')), categoria_id, int(data.get('cantidad', 0)), id))
        conn.commit()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('inventario.inventario'))
    
    p = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    c = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('editar_producto.html', p=p, categorias=c)

@inventario_bp.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    try:
        conn.execute('UPDATE productos SET activo = 0 WHERE id = ?', (id,))
        conn.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                        VALUES (?, ?, 'Eliminación de Producto', 0)''', 
                     (id, session['user_id']))
        conn.commit()
        flash('Producto eliminado.', 'success')
    except Exception as e: 
        flash(f'Error: {str(e)}', 'danger')
        
    conn.close()
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/categorias', methods=['GET', 'POST'])
def categorias():
    if 'user_id' not in session or session.get('rol') == 'Vendedor': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            conn.execute('INSERT INTO categorias (nombre) VALUES (?)', (str(request.form['nombre']),))
            conn.commit()
            flash('Categoría creada.', 'success')
        except: 
            flash('La categoría ya existe.', 'danger')
            
    c = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('categorias.html', categorias=c)

@inventario_bp.route('/eliminar_categoria/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    conn.execute('UPDATE productos SET categoria_id = NULL WHERE categoria_id = ?', (id,))
    conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventario.categorias'))

@inventario_bp.route('/producto/<int:id>', methods=['GET', 'POST'])
def detalle_producto(id):
    if 'user_id' not in session: 
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()

    if request.method == 'POST':
        tipo = request.form.get('tipo_movimiento', request.form.get('tipo'))
        cantidad_mov = int(request.form['cantidad'])
        p = conn.execute('SELECT nombre, sku, cantidad, stock_reservado, stock_minimo FROM productos WHERE id = ?', (id,)).fetchone()
        
        stock_fisico = p['cantidad']
        stock_reservado = p['stock_reservado']
        stock_disponible = stock_fisico - stock_reservado
        cursor = conn.cursor()
        error = False

        if tipo == 'Cotizacion':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock disponible para reservar.', 'danger')
                error = True
            else:
                cursor.execute('UPDATE productos SET stock_reservado = stock_reservado + ? WHERE id = ?', (cantidad_mov, id))
                flash('Cotización (Reserva) creada correctamente.', 'info')
                
        elif tipo == 'Venta_Cotizacion':
            if cantidad_mov > stock_reservado:
                flash('Error: La cantidad de venta supera a la cantidad que estaba reservada.', 'danger')
                error = True
            else:
                nueva_cantidad = stock_fisico - cantidad_mov
                cursor.execute('UPDATE productos SET cantidad = ?, stock_reservado = stock_reservado - ? WHERE id = ?', (nueva_cantidad, cantidad_mov, id))
                flash('Venta concretada desde la reserva.', 'success')
                
        elif tipo == 'Salida':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock para la venta directa.', 'danger')
                error = True
            else:
                nueva_cantidad = stock_fisico - cantidad_mov
                cursor.execute('UPDATE productos SET cantidad = ? WHERE id = ?', (nueva_cantidad, id))
                flash('Venta directa (Salida) registrada.', 'success')
                
        elif tipo == 'Entrada':
            cursor.execute('UPDATE productos SET cantidad = cantidad + ? WHERE id = ?', (cantidad_mov, id))
            flash('Ingreso de mercadería registrado exitosamente.', 'success')
        elif tipo == 'Entrada':
            cursor.execute('UPDATE productos SET cantidad = cantidad + ? WHERE id = ?', (cantidad_mov, id))
            flash('Ingreso de mercadería registrado exitosamente.', 'success')
            
        # --- NUEVO CÓDIGO PARA HU-17: AJUSTE MANUAL ---
        elif tipo == 'Ajuste':
            if session.get('rol') != 'Administrador':
                flash('Acceso denegado: Solo los administradores pueden realizar ajustes manuales.', 'danger')
                error = True
            else:
                justificacion = request.form.get('justificacion', '').strip()
                if not justificacion:
                    flash('Error: La justificación es obligatoria para un ajuste manual.', 'danger')
                    error = True
                else:
                    # En un ajuste, 'cantidad_mov' representa el NUEVO conteo físico total.
                    # Calculamos la diferencia para que el historial muestre cuánto se sumó o restó.
                    diferencia = cantidad_mov - stock_fisico 
                    
                    cursor.execute('UPDATE productos SET cantidad = ? WHERE id = ?', (cantidad_mov, id))
                    flash('Ajuste de inventario registrado correctamente.', 'success')
                    
                    # Modificamos las variables para que el INSERT posterior lo guarde bien
                    tipo = f"Ajuste manual: {justificacion}"
                    cantidad_mov = diferencia
        # ----------------------------------------------
        # --- NUEVO CÓDIGO PARA HU-20: DEVOLUCIONES ---
        elif tipo == 'Devolucion':
            if session.get('rol') != 'Administrador':
                flash('Acceso denegado: Solo los administradores pueden registrar devoluciones.', 'danger')
                error = True
            else:
                motivo = request.form.get('motivo_devolucion', '').strip()
                referencia = request.form.get('referencia_venta', '').strip()
                if not motivo or not referencia:
                    flash('Error: El motivo y la referencia son obligatorios para una devolución.', 'danger')
                    error = True
                else:
                    cursor.execute('UPDATE productos SET cantidad = cantidad + ? WHERE id = ?', (cantidad_mov, id))
                    flash('Devolución registrada, el stock ha reingresado.', 'success')
                    # Renombramos el tipo para que guarde los datos en el historial
                    tipo = f"Devolución: {motivo} (Ref: {referencia})"
        # ----------------------------------------------

        if not error:
            cursor.execute('INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) VALUES (?, ?, ?, ?)',
                           (id, session['user_id'], tipo, cantidad_mov))
            mov_id = cursor.lastrowid
            
            # --- LÓGICA DE ALERTAS POR CORREO (SEGUNDO PLANO) ---
            if tipo in ['Salida', 'Venta_Cotizacion', 'Cotizacion'] or tipo.startswith('Ajuste'):
                p_actualizado = conn.execute('SELECT sku, nombre, cantidad, stock_reservado, stock_minimo FROM productos WHERE id = ?', (id,)).fetchone()
                stock_real = p_actualizado['cantidad'] - p_actualizado['stock_reservado']
                
                if stock_real <= p_actualizado['stock_minimo']:
                    admins = conn.execute("SELECT email FROM usuarios WHERE rol = 'Administrador' AND email IS NOT NULL").fetchall()
                    correos_admin = [admin['email'] for admin in admins if admin['email']]
                    
                    if correos_admin:
                        app_actual = current_app._get_current_object()
                        def enviar_async(app, nombre, sku, stock, correos, p_id, u_id):
                            with app.app_context():
                                # Ahora enviamos también el ID del producto y del usuario
                                enviar_alerta_stock(nombre, sku, stock, correos, p_id, u_id)
        
                        hilo = Thread(target=enviar_async, args=(app_actual, p_actualizado['nombre'], p_actualizado['sku'], stock_real, correos_admin, id, session['user_id']))
                        hilo.start()
            # ------------------------------------------------------

            conn.commit()
            if tipo in ['Salida', 'Venta_Cotizacion', 'Cotizacion']or tipo.startswith('Devolución'):
                return redirect(url_for('inventario.comprobante', mov_id=mov_id))

    producto = conn.execute('SELECT p.*, c.nombre as categoria_nombre FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id WHERE p.id = ?', (id,)).fetchone()
    historial = conn.execute('''SELECT m.*, u.username FROM movimientos m 
                                JOIN usuarios u ON m.usuario_id = u.id 
                                WHERE m.producto_id = ? ORDER BY m.fecha DESC''', (id,)).fetchall()
    conn.close()
    return render_template('detalle_producto.html', p=producto, movimientos=historial)


@inventario_bp.route('/comprobante/<int:mov_id>')
def comprobante(mov_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    # Hacemos JOIN para traer los detalles del producto y del usuario responsable
    mov = conn.execute('''
        SELECT m.id, m.fecha, m.tipo, m.cantidad,
               p.sku, p.nombre as repuesto,
               u.username as responsable
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.id = ?
    ''', (mov_id,)).fetchone()
    conn.close()

    if not mov:
        flash('Movimiento no encontrado', 'danger')
        return redirect(url_for('inventario.inventario'))

    return render_template('comprobante.html', m=mov)
@inventario_bp.route('/importar_csv', methods=['POST'])
def importar_csv():
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']:
        flash('No tienes permisos para realizar esta acción.', 'danger')
        return redirect(url_for('inventario.inventario'))

    if 'archivo_csv' not in request.files:
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(url_for('inventario.inventario'))

    file = request.files['archivo_csv']
    if file.filename == '':
        return redirect(url_for('inventario.inventario'))

    if file and file.filename.endswith('.csv'):
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            next(csv_input, None) # Saltar encabezados

            conn = get_db_connection()
            cursor = conn.cursor()
            productos_importados = 0
            
            for row in csv_input:
                if len(row) >= 5:
                    sku = str(row[0]).strip()
                    nombre = str(row[1]).strip()
                    descripcion = str(row[2]).strip() if len(row) > 2 else ""
                    cantidad = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
                    precio = float(row[4]) if len(row) > 4 and row[4].replace('.', '', 1).isdigit() else 0.0
                    categoria_id = int(row[5]) if len(row) > 5 and row[5].isdigit() else None
                    ubicacion = str(row[6]).strip() if len(row) > 6 else "Bodega Central"
                    stock_minimo = 5 # Valor por defecto masivo

                    try:
                        cursor.execute('''INSERT INTO productos (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion, activo)
                                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                                       (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion))
                        nuevo_id = cursor.lastrowid
                        
                        cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad)
                                          VALUES (?, ?, 'Importación Masiva (CSV)', ?)''',
                                       (nuevo_id, session['user_id'], cantidad))
                        productos_importados += 1
                    except Exception:
                        pass # Ignorar filas defectuosas o con SKU duplicado

            conn.commit()
            conn.close()
            
            if productos_importados > 0:
                flash(f'Éxito: Se importaron {productos_importados} productos.', 'success')
            else:
                flash('No se importó ningún producto (Revise el formato o SKUs duplicados).', 'warning')
                
        except Exception as e:
            flash(f'Error al procesar el archivo CSV: {str(e)}', 'danger')
    else:
        flash('Formato no válido. Suba un archivo .csv', 'danger')

    return redirect(url_for('inventario.inventario'))

# MODIFICACIONES AGOSTO 2026
@inventario_bp.route('/api/productos/filtrar', methods=['GET'])
def api_filtrar_productos():
    conn = get_db_connection()
    cat_id = request.args.get('categoria_id', '')
    busqueda = request.args.get('q', '')

    query = '''SELECT p.*, c.nombre as categoria_nombre FROM productos p 
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.activo = 1'''
    params = []

    if cat_id:
        query += ' AND p.categoria_id = ?'
        params.append(cat_id)
    
    if busqueda:
        # Busca por SKU, Nombre (donde podría estar la marca) o Descripción
        query += ' AND (p.sku LIKE ? OR p.nombre LIKE ? OR p.descripcion LIKE ?)'
        params.extend([f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'])

    productos = conn.execute(query, params).fetchall()
    
    prod_list = []
    for p in productos:
        prod_list.append({
            'id': p['id'],
            'sku': p['sku'],
            'nombre': p['nombre'],
            'cantidad': p['cantidad'],
            'stock_reservado': p['stock_reservado'],
            'precio': p['precio'],
            'foto': p['foto'],
            'ficha_pdf': p['ficha_pdf'],
            'categoria_nombre': p['categoria_nombre']
        })
    
    conn.close()
    return jsonify({'total': len(prod_list), 'productos': prod_list})

# --- NUEVO CÓDIGO PARA HU-23: CAMPANA DE NOTIFICACIONES ---
@inventario_bp.route('/api/notificaciones', methods=['GET'])
def api_notificaciones():
    # Solo los administradores reciben estas alertas
    if 'user_id' not in session or session.get('rol') != 'Administrador':
        return current_app.response_class(response='{"alertas": 0}', status=200, mimetype='application/json')
    
    conn = get_db_connection()
    # Contamos cuántos productos están en stock crítico/agotado
    criticos = conn.execute('''SELECT COUNT(*) as total 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1''').fetchone()
    conn.close()
    
    # Retornamos el número en formato JSON
    return jsonify({'alertas': criticos['total']})

# ---- CODIGO PARA LA IMPRESIÓN DE LA TRZA  DE CADA ELEMENTO 

@inventario_bp.route('/exportar_trazabilidad/<int:id>')
def exportar_trazabilidad_csv(id):
    if 'user_id' not in session: 
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    producto = conn.execute('SELECT sku, nombre FROM productos WHERE id = ?', (id,)).fetchone()
    
    if not producto:
        conn.close()
        return redirect(url_for('inventario.inventario'))
        
    historial = conn.execute('''SELECT m.fecha, u.username, m.tipo, m.cantidad 
                                FROM movimientos m 
                                JOIN usuarios u ON m.usuario_id = u.id 
                                WHERE m.producto_id = ? ORDER BY m.fecha DESC''', (id,)).fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    # Título y metadatos en el CSV
    cw.writerow(['Reporte de Trazabilidad'])
    cw.writerow(['Repuesto:', producto['nombre']])
    cw.writerow(['SKU:', producto['sku']])
    cw.writerow([]) # Fila vacía para separar
    
    # Encabezados de la tabla
    cw.writerow(['Fecha', 'Operario', 'Movimiento', 'Cantidad'])
    
    for h in historial:
        cw.writerow([h['fecha'], h['username'], h['tipo'], h['cantidad']])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Trazabilidad_{producto['sku']}.csv"})