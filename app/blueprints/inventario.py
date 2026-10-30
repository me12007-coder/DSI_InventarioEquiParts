from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify, Response
from werkzeug.utils import secure_filename
from threading import Thread
from datetime import datetime
import os
import csv
import io
from uuid import uuid4
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import RequestEntityTooLarge

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
        foto_path = ""
        pdf_path = secure_filename(pdf.filename) if pdf and pdf.filename else ""
        
        # Guardar archivos
        if pdf_path: 
            pdf.save(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_path))

        data = request.form
        sku = str(data.get('sku', '')).strip().upper()
        
        # NUEVA VALIDACIÓN: Evitar que el SKU tenga espacios
        if ' ' in sku:
            flash('Error: El código SKU no puede contener espacios en blanco (use guiones).', 'danger')
            return redirect(url_for('inventario.inventario'))
            
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
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)''',
                           (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion, foto_path, pdf_path))
            nuevo_id = cursor.lastrowid
            guardar_fotos_galeria(cursor, nuevo_id, [foto] + request.files.getlist('fotos'))
            
            cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                              VALUES (%s, %s, 'Creación de Producto', %s)''', 
                           (nuevo_id, session['user_id'], cantidad))
            conn.commit()
            flash('Producto creado exitosamente.', 'success')
        except Exception as e:
            flash('Error al crear el producto (Verifique que el SKU no exista).', 'danger')
        finally:
            cursor.close()

    busqueda = request.args.get('q', '')
    mostrar_inactivos = session.get('rol') == 'Administrador' and request.args.get('estado') == 'inactivos'
    query = '''SELECT p.*, c.nombre as categoria_nombre FROM productos p 
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.activo = %s AND (p.sku LIKE %s OR p.nombre LIKE %s)'''
    cursor = conn.cursor()
    cursor.execute(query, (0 if mostrar_inactivos else 1, '%'+busqueda+'%', '%'+busqueda+'%'))
    productos = cursor.fetchall()
    
    cursor.execute('SELECT * FROM categorias')
    categorias = cursor.fetchall()
    
    # --- CÁLCULO DE ESTADÍSTICAS PARA LA CÁPSULA DINÁMICA ---
    alertas_stock = []
    stats = {
        'total': len(productos),
        'agotados': 0,
        'bajo_minimo': 0,
        'reservas': 0
    }
    
    for p in productos:
        stock_real = p['cantidad'] - p['stock_reservado']
        stats['reservas'] += p['stock_reservado']
        
        if stock_real <= 0:
            stats['agotados'] += 1
            alertas_stock.append({'nombre': p['nombre'], 'stock': stock_real, 'minimo': p['stock_minimo']})
        elif stock_real <= p['stock_minimo']:
            stats['bajo_minimo'] += 1
            alertas_stock.append({'nombre': p['nombre'], 'stock': stock_real, 'minimo': p['stock_minimo']})
            
    stats['criticos'] = stats['agotados'] + stats['bajo_minimo']
            
    cursor.close()
    conn.close()
    
    # Renderizamos pasando el nuevo diccionario stats
    return render_template('inventario.html', productos=productos, categorias=categorias, 
                           username=session.get('username'), rol=session.get('rol'), 
                           busqueda=busqueda, alertas_stock=alertas_stock, stats=stats, mostrar_inactivos=mostrar_inactivos)


@inventario_bp.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.form
        cat_raw = data.get('categoria_id')
        categoria_id = int(cat_raw) if cat_raw else None
        stock_minimo = int(data.get('stock_minimo', 5))
        
        cursor.execute('SELECT foto, ficha_pdf, activo, cantidad FROM productos WHERE id = %s FOR UPDATE', (id,))
        prod_actual = cursor.fetchone()
        foto_path = prod_actual['foto'] if prod_actual['foto'] else ""
        pdf_path = prod_actual['ficha_pdf'] if prod_actual['ficha_pdf'] else ""
        
        foto = request.files.get('foto')
        pdf = request.files.get('pdf')
        
        if foto and foto.filename:
            # Las fotos nuevas se incorporan a la galería sin borrar fotos antiguas.
            pass

        if pdf and pdf.filename:
            if prod_actual['ficha_pdf']:
                vieja_ruta_pdf = os.path.join(current_app.config['UPLOAD_FOLDER'], prod_actual['ficha_pdf'])
                if os.path.exists(vieja_ruta_pdf):
                    os.remove(vieja_ruta_pdf)
            pdf_path = secure_filename(pdf.filename)
            pdf.save(os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_path))
        
        cursor.execute('''UPDATE productos SET nombre = %s, descripcion = %s, precio = %s, 
                          ubicacion = %s, categoria_id = %s, cantidad = %s, stock_minimo = %s,
                          foto = %s, ficha_pdf = %s
                          WHERE id = %s''', 
                     (str(data.get('nombre')), str(data.get('descripcion')), float(data.get('precio')), 
                      str(data.get('ubicacion')), categoria_id, (int(data.get('cantidad', 0)) if prod_actual['activo'] else prod_actual['cantidad']), stock_minimo, 
                      foto_path, pdf_path, id))
        try:
            guardar_fotos_galeria(cursor, id, [foto] + request.files.getlist('fotos'))
            conn.commit()
        except (ValueError, OSError) as error:
            conn.rollback()
            flash('No se guardó la ficha: ' + str(error), 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('inventario.editar_producto', id=id))
        flash('Ficha del producto actualizada correctamente.', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('inventario.inventario'))
    
    cursor.execute('SELECT * FROM productos WHERE id = %s', (id,))
    p = cursor.fetchone()
    cursor.execute('SELECT * FROM categorias')
    c = cursor.fetchall()
    cursor.close()
    conn.close()
    cursor_g = get_db_connection()
    try:
        with cursor_g.cursor() as cg:
            cg.execute('SELECT id, archivo, principal FROM producto_fotos WHERE producto_id=%s ORDER BY principal DESC, id', (id,))
            galeria = cg.fetchall()
    finally:
        cursor_g.close()
    return render_template('editar_producto.html', p=p, categorias=c, galeria=galeria)

@inventario_bp.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE productos SET activo = 0 WHERE id = %s', (id,))
        cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                        VALUES (%s, %s, 'Desactivación de Producto', 0)''', 
                     (id, session['user_id']))
        conn.commit()
        flash('Producto desactivado. Ya no admite movimientos.', 'success')
    except Exception as e: 
        flash(f'Error: {str(e)}', 'danger')
        
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/reactivar_producto/<int:id>', methods=['POST'])
def reactivar_producto(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador':
        return redirect(url_for('inventario.inventario'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE productos SET activo=1 WHERE id=%s AND activo=0', (id,))
            if cursor.rowcount:
                cursor.execute('INSERT INTO movimientos (producto_id,usuario_id,tipo,cantidad) VALUES (%s,%s,%s,0)',
                               (id,session['user_id'],'Reactivación de Producto'))
        conn.commit()
        flash('Producto reactivado.', 'success')
    except Exception:
        conn.rollback()
        flash('No se pudo reactivar el repuesto.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventario.inventario', estado='inactivos'))


def guardar_fotos_galeria(cursor, producto_id, files):
    """Valida contenido real, guarda imágenes normalizadas y registra la galería."""
    from pathlib import Path
    carpeta = Path(current_app.config['UPLOAD_FOLDER'])
    carpeta.mkdir(parents=True, exist_ok=True)
    cursor.execute('SELECT COUNT(*) AS n FROM producto_fotos WHERE producto_id=%s', (producto_id,))
    presentes = cursor.fetchone()['n']
    nuevas = [f for f in files if f and f.filename]
    if len(nuevas) + presentes > 12:
        raise ValueError('Máximo 12 fotos por producto.')
    for f in nuevas:
        if len(f.read(8 * 1024 * 1024 + 1)) > 8 * 1024 * 1024:
            raise ValueError('Cada foto debe pesar menos de 8 MB.')
        f.stream.seek(0)
        try:
            with Image.open(f.stream) as im:
                im.verify()
            f.stream.seek(0)
            with Image.open(f.stream) as im:
                if im.format not in ('JPEG','PNG','WEBP') or im.width * im.height > 24_000_000:
                    raise ValueError('Solo JPEG, PNG o WEBP de hasta 24 megapíxeles.')
                im.thumbnail((1800,1800))
                im = im.convert('RGB')
                nombre = 'repuesto_' + uuid4().hex + '.jpg'
                im.save(carpeta / nombre, format='JPEG', quality=85)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError('Imagen inválida.') from exc
        cursor.execute('INSERT INTO producto_fotos (producto_id,archivo,principal) VALUES (%s,%s,%s)',
                       (producto_id,nombre,0 if presentes else 1))
        if not presentes:
            cursor.execute('UPDATE productos SET foto=%s WHERE id=%s', (nombre,producto_id))
        presentes += 1


@inventario_bp.route('/producto/<int:id>/foto_principal/<int:foto_id>', methods=['POST'])
def foto_principal(id,foto_id):
    if session.get('rol') not in ('Administrador','Bodeguero') or 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT archivo FROM producto_fotos WHERE id=%s AND producto_id=%s', (foto_id,id))
            foto = cursor.fetchone()
            if not foto:
                flash('Foto no encontrada.', 'danger')
                return redirect(url_for('inventario.editar_producto',id=id))
            cursor.execute('UPDATE producto_fotos SET principal=0 WHERE producto_id=%s', (id,))
            cursor.execute('UPDATE producto_fotos SET principal=1 WHERE id=%s', (foto_id,))
            cursor.execute('UPDATE productos SET foto=%s WHERE id=%s', (foto['archivo'],id))
        conn.commit()
    except Exception:
        conn.rollback()
        flash('No se pudo cambiar la foto principal.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('inventario.editar_producto',id=id))


@inventario_bp.route('/categorias', methods=['GET', 'POST'])
def categorias():
    if 'user_id' not in session or session.get('rol') == 'Vendedor': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        try:
            cursor.execute('INSERT INTO categorias (nombre) VALUES (%s)', (str(request.form['nombre']),))
            conn.commit()
            flash('Categoría creada.', 'success')
        except: 
            flash('La categoría ya existe.', 'danger')
            
    cursor.execute('SELECT * FROM categorias')
    c = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('categorias.html', categorias=c)

@inventario_bp.route('/editar_categoria/<int:id>', methods=['POST'])
def editar_categoria(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    nuevo_nombre = request.form.get('nombre', '').strip()
    if not nuevo_nombre:
        flash('El nombre de la categoría no puede estar vacío.', 'danger')
        return redirect(url_for('inventario.categorias'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE categorias SET nombre = %s WHERE id = %s', (nuevo_nombre, id))
        conn.commit()
        flash('Categoría actualizada correctamente.', 'success')
    except Exception as e:
        flash('Error al actualizar la categoría. Es posible que el nombre ya exista.', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('inventario.categorias'))

@inventario_bp.route('/eliminar_categoria/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Verificar si hay productos que dependen de esta categoría
    cursor.execute('SELECT COUNT(*) as total FROM productos WHERE categoria_id = %s', (id,))
    resultado = cursor.fetchone()
    
    if resultado['total'] > 0:
        flash(f"No se puede eliminar: Hay {resultado['total']} repuesto(s) asignados a esta categoría.", 'danger')
    else:
        cursor.execute('DELETE FROM categorias WHERE id = %s', (id,))
        conn.commit()
        flash('Categoría eliminada correctamente.', 'success')
        
    cursor.close()
    conn.close()
    return redirect(url_for('inventario.categorias'))

@inventario_bp.route('/producto/<int:id>', methods=['GET', 'POST'])
def detalle_producto(id):
    if 'user_id' not in session: 
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        tipo = request.form.get('tipo_movimiento', request.form.get('tipo'))
        cantidad_mov = int(request.form['cantidad'])
        cursor.execute('SELECT nombre, sku, cantidad, stock_reservado, stock_minimo, activo FROM productos WHERE id = %s FOR UPDATE', (id,))
        p = cursor.fetchone()
        if not p or not p['activo']:
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Producto inactivo o inexistente: movimiento bloqueado.', 'danger')
            return redirect(url_for('inventario.inventario'))
        if cantidad_mov < 0 or (cantidad_mov == 0 and tipo != 'Ajuste'):
            conn.rollback()
            cursor.close()
            conn.close()
            flash('Cantidad inválida.', 'danger')
            return redirect(url_for('inventario.detalle_producto', id=id))
        
        stock_fisico = p['cantidad']
        stock_reservado = p['stock_reservado']
        stock_disponible = stock_fisico - stock_reservado
        error = False

        if tipo == 'Cotizacion':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock disponible para reservar.', 'danger')
                error = True
            else:
                cursor.execute('UPDATE productos SET stock_reservado = stock_reservado + %s WHERE id = %s', (cantidad_mov, id))
                flash('Cotización (Reserva) creada correctamente.', 'info')
                
        elif tipo == 'Venta_Cotizacion':
            if cantidad_mov > stock_reservado:
                flash('Error: La cantidad de venta supera a la cantidad que estaba reservada.', 'danger')
                error = True
            else:
                nueva_cantidad = stock_fisico - cantidad_mov
                cursor.execute('UPDATE productos SET cantidad = %s, stock_reservado = stock_reservado - %s WHERE id = %s', (nueva_cantidad, cantidad_mov, id))
                flash('Venta concretada desde la reserva.', 'success')
                
        elif tipo == 'Salida':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock para la venta directa.', 'danger')
                error = True
            else:
                nueva_cantidad = stock_fisico - cantidad_mov
                cursor.execute('UPDATE productos SET cantidad = %s WHERE id = %s', (nueva_cantidad, id))
                flash('Venta directa (Salida) registrada.', 'success')
                
        elif tipo == 'Entrada':
            cursor.execute('UPDATE productos SET cantidad = cantidad + %s WHERE id = %s', (cantidad_mov, id))
            flash('Ingreso de mercadería registrado exitosamente.', 'success')
            
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
                    diferencia = cantidad_mov - stock_fisico 
                    cursor.execute('UPDATE productos SET cantidad = %s WHERE id = %s', (cantidad_mov, id))
                    flash('Ajuste de inventario registrado correctamente.', 'success')
                    tipo = f"Ajuste manual: {justificacion}"
                    cantidad_mov = diferencia

        elif tipo == 'Mermar':
            if session.get('rol') != 'Administrador':
                flash('Acceso denegado.', 'danger')
                error = True
            else:
                justificacion = request.form.get('justificacion', '').strip()
                if not justificacion:
                    flash('Error: Justificación obligatoria.', 'danger')
                    error = True
                elif cantidad_mov > stock_disponible:
                    flash('Error: No hay suficiente stock disponible para mermar.', 'danger')
                    error = True
                else:
                    nueva_cantidad = stock_fisico - cantidad_mov
                    cursor.execute('UPDATE productos SET cantidad = %s WHERE id = %s', (nueva_cantidad, id))
                    flash('Repuesto trasladado a Mermas correctamente.', 'success')
                    tipo = f"Traslado a Mermas: {justificacion}"

        elif tipo == 'Baja':
            if session.get('rol') != 'Administrador':
                flash('Acceso denegado.', 'danger')
                error = True
            else:
                justificacion = request.form.get('justificacion', '').strip()
                cursor.execute('''
                    SELECT 
                        SUM(CASE WHEN tipo LIKE 'Traslado a Mermas%%' OR tipo LIKE 'Devolución (Dañado%%' THEN cantidad ELSE 0 END) - 
                        SUM(CASE WHEN tipo LIKE 'Destrucción de Merma%%' THEN cantidad ELSE 0 END) as mermas_actuales
                    FROM movimientos 
                    WHERE producto_id = %s
                ''', (id,))
                mermas_db = cursor.fetchone()
                mermas_disponibles = mermas_db['mermas_actuales'] if mermas_db['mermas_actuales'] else 0

                if not justificacion:
                    flash('Error: Justificación obligatoria.', 'danger')
                    error = True
                elif cantidad_mov > mermas_disponibles:
                    flash(f'Error: Solo tienes {int(mermas_disponibles)} piezas en Mermas. No puedes destruir {cantidad_mov}.', 'danger')
                    error = True
                else:
                    flash('Repuesto destruido definitivamente.', 'success')
                    tipo = f"Destrucción de Merma: {justificacion}"

        elif tipo == 'Devolucion':
            if session.get('rol') != 'Administrador':
                flash('Acceso denegado: Solo los administradores pueden registrar devoluciones.', 'danger')
                error = True
            else:
                motivo = request.form.get('motivo_devolucion', '').strip()
                referencia = request.form.get('referencia_venta', '').strip()
                estado_pieza = request.form.get('estado_devolucion', 'Bueno')
                
                if not motivo or not referencia:
                    flash('Error: El motivo y la referencia son obligatorios para una devolución.', 'danger')
                    error = True
                else:
                    if estado_pieza == 'Bueno':
                        cursor.execute('UPDATE productos SET cantidad = cantidad + %s WHERE id = %s', (cantidad_mov, id))
                        flash('Devolución registrada, el stock ha reingresado a la bodega.', 'success')
                        tipo = f"Devolución (Reingreso): {motivo} (Ref: {referencia})"
                    else:
                        flash('Devolución por producto dañado. La pieza se ha enviado a Mermas.', 'warning')
                        tipo = f"Devolución (Dañado/Merma): {motivo} (Ref: {referencia})"

        if not error:
            tipo_seguro = tipo[:50] 
            cursor.execute('INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) VALUES (%s, %s, %s, %s)',
                           (id, session['user_id'], tipo_seguro, cantidad_mov))
            mov_id = cursor.lastrowid
            
            if tipo in ['Salida', 'Venta_Cotizacion', 'Cotizacion', 'Mermar'] or tipo.startswith('Ajuste'):
                cursor.execute('SELECT sku, nombre, cantidad, stock_reservado, stock_minimo FROM productos WHERE id = %s', (id,))
                p_actualizado = cursor.fetchone()
                stock_real = p_actualizado['cantidad'] - p_actualizado['stock_reservado']
                
                if stock_real <= p_actualizado['stock_minimo']:
                    cursor.execute("SELECT email FROM usuarios WHERE rol = 'Administrador' AND email IS NOT NULL")
                    admins = cursor.fetchall()
                    correos_admin = [admin['email'] for admin in admins if admin['email']]
                    
                    if correos_admin:
                        app_actual = current_app._get_current_object()
                        def enviar_async(app, nombre, sku, stock, correos, p_id, u_id):
                            with app.app_context():
                                enviar_alerta_stock(nombre, sku, stock, correos, p_id, u_id)
        
                        hilo = Thread(target=enviar_async, args=(app_actual, p_actualizado['nombre'], p_actualizado['sku'], stock_real, correos_admin, id, session['user_id']))
                        hilo.start()

            conn.commit()
            if tipo in ['Salida', 'Venta_Cotizacion', 'Cotizacion', 'Mermar', 'Baja'] or tipo.startswith('Devolución'):
                cursor.close()
                conn.close()
                return redirect(url_for('inventario.comprobante', mov_id=mov_id))

    cursor.execute('SELECT p.*, c.nombre as categoria_nombre FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id WHERE p.id = %s', (id,))
    producto = cursor.fetchone()
    if not producto or (not producto['activo'] and session.get('rol') == 'Vendedor'):
        cursor.close()
        conn.close()
        flash('Producto no disponible.', 'warning')
        return redirect(url_for('inventario.inventario'))
    cursor.execute('''SELECT m.*, u.username FROM movimientos m 
                                JOIN usuarios u ON m.usuario_id = u.id 
                                WHERE m.producto_id = %s ORDER BY m.fecha DESC''', (id,))
    historial = cursor.fetchall()
    
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN tipo LIKE 'Traslado a Mermas%%' OR tipo LIKE 'Devolución (Dañado%%' THEN cantidad ELSE 0 END) - 
            SUM(CASE WHEN tipo LIKE 'Destrucción de Merma%%' THEN cantidad ELSE 0 END) as mermas_actuales
        FROM movimientos
        WHERE producto_id = %s 
    ''', (id,))
    mermas_ui = cursor.fetchone()
    total_dañados = mermas_ui['mermas_actuales'] if mermas_ui['mermas_actuales'] else 0

    cursor.execute('''
        SELECT DATE(fecha) as dia, 
               SUM(CASE WHEN tipo IN ('Salida', 'Venta_Cotizacion') THEN cantidad ELSE 0 END) as total_ventas,
               SUM(CASE WHEN tipo LIKE 'Traslado a Mermas%%' OR tipo LIKE 'Devolución (Dañado%%' THEN cantidad ELSE 0 END) as total_mermas
        FROM movimientos 
        WHERE producto_id = %s 
          AND fecha >= DATE_SUB(NOW(), INTERVAL 30 DAY)
          AND (tipo IN ('Salida', 'Venta_Cotizacion') 
               OR tipo LIKE 'Traslado a Mermas%%' 
               OR tipo LIKE 'Devolución (Dañado%%')
        GROUP BY DATE(fecha) 
        ORDER BY dia ASC LIMIT 30
    ''', (id,))
    tendencia = cursor.fetchall()
    
    fechas_chart = [row['dia'].strftime('%d %b') for row in tendencia]
    ventas_chart = [row['total_ventas'] for row in tendencia]
    mermas_chart = [row['total_mermas'] for row in tendencia]
    
    cursor.execute('SELECT id,archivo,principal FROM producto_fotos WHERE producto_id=%s ORDER BY principal DESC,id', (id,))
    galeria = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('detalle_producto.html', 
                           p=producto, galeria=galeria,
                           movimientos=historial,
                           total_dañados=int(total_dañados),
                           fechas_chart=fechas_chart,
                           ventas_chart=ventas_chart,
                           mermas_chart=mermas_chart)

@inventario_bp.route('/comprobante/<int:mov_id>')
def comprobante(mov_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.id, m.fecha, m.tipo, m.cantidad,
               p.sku, p.nombre as repuesto,
               u.username as responsable
        FROM movimientos m
        JOIN productos p ON m.producto_id = p.id
        JOIN usuarios u ON m.usuario_id = u.id
        WHERE m.id = %s
    ''', (mov_id,))
    mov = cursor.fetchone()
    cursor.close()
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
            next(csv_input, None)

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
                    
                    stock_minimo = int(row[7]) if len(row) > 7 and row[7].isdigit() else 5

                    try:
                        cursor.execute('''INSERT INTO productos (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion, activo)
                                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)''',
                                       (sku, nombre, descripcion, cantidad, stock_minimo, precio, categoria_id, ubicacion))
                        nuevo_id = cursor.lastrowid
                        
                        cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad)
                                          VALUES (%s, %s, 'Importación Masiva (CSV)', %s)''',
                                       (nuevo_id, session['user_id'], cantidad))
                        productos_importados += 1
                    except Exception:
                        pass

            conn.commit()
            cursor.close()
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

@inventario_bp.route('/descargar_plantilla_csv')
def descargar_plantilla_csv():
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']:
        return redirect(url_for('inventario.inventario'))
    
    csv_content = "sku,nombre,descripcion,cantidad,precio,categoria_id,ubicacion,stock_minimo\n"
    csv_content += "EX-001,Ejemplo de Repuesto,Descripción breve,10,150.50,1,Estante A-1,3\n"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=plantilla_importacion.csv"}
    )

@inventario_bp.route('/api/productos/filtrar', methods=['GET'])
def api_filtrar_productos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cat_id = request.args.get('categoria_id', '')
    busqueda = request.args.get('q', '')
    mostrar_inactivos = session.get('rol') == 'Administrador' and request.args.get('estado') == 'inactivos'

    query = '''SELECT p.*, c.nombre as categoria_nombre FROM productos p 
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.activo = %s'''
    params = [0 if mostrar_inactivos else 1]

    if cat_id:
        query += ' AND p.categoria_id = %s'
        params.append(cat_id)
    
    if busqueda:
        query += ' AND (p.sku LIKE %s OR p.nombre LIKE %s OR p.descripcion LIKE %s)'
        params.extend([f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'])

    cursor.execute(query, params)
    productos = cursor.fetchall()
    
    prod_list = []
    for p in productos:
        prod_list.append({
            'id': p['id'],
            'activo': p['activo'],
            'sku': p['sku'],
            'nombre': p['nombre'],
            'cantidad': p['cantidad'],
            'stock_reservado': p['stock_reservado'],
            'precio': p['precio'],
            'foto': p['foto'],
            'ficha_pdf': p['ficha_pdf'],
            'categoria_nombre': p['categoria_nombre'],
            'stock_minimo': p['stock_minimo']
        })
    
    cursor.close()
    conn.close()
    return jsonify({'total': len(prod_list), 'productos': prod_list})

@inventario_bp.route('/api/notificaciones', methods=['GET'])
def api_notificaciones():
    if 'user_id' not in session or session.get('rol') != 'Administrador':
        return current_app.response_class(response='{"alertas": 0}', status=200, mimetype='application/json')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT COUNT(*) as total 
                               FROM productos 
                               WHERE (cantidad - stock_reservado) <= stock_minimo AND activo = 1''')
    criticos = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return jsonify({'alertas': criticos['total']})

@inventario_bp.route('/exportar_trazabilidad/<int:id>')
def exportar_trazabilidad_csv(id):
    if 'user_id' not in session: 
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT sku, nombre FROM productos WHERE id = %s', (id,))
    producto = cursor.fetchone()
    
    if not producto:
        cursor.close()
        conn.close()
        return redirect(url_for('inventario.inventario'))
        
    cursor.execute('''SELECT m.fecha, u.username, m.tipo, m.cantidad 
                                FROM movimientos m 
                                JOIN usuarios u ON m.usuario_id = u.id 
                                WHERE m.producto_id = %s ORDER BY m.fecha DESC''', (id,))
    historial = cursor.fetchall()
    cursor.close()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Reporte de Trazabilidad'])
    cw.writerow(['Repuesto:', producto['nombre']])
    cw.writerow(['SKU:', producto['sku']])
    cw.writerow([])
    cw.writerow(['Fecha', 'Operario', 'Movimiento', 'Cantidad'])
    
    for h in historial:
        cw.writerow([h['fecha'], h['username'], h['tipo'], h['cantidad']])
    
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=Trazabilidad_{producto['sku']}.csv"})

@inventario_bp.route('/api/validar_sku', methods=['GET'])
def validar_sku():
    sku = request.args.get('sku', '').strip()
    if not sku:
        return jsonify({'existe': False})
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total FROM productos WHERE sku = %s', (sku,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return jsonify({'existe': resultado['total'] > 0})


@inventario_bp.route('/producto/<int:id>/purgar', methods=['POST'])
def purgar_historial(id):
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
        
    cursor.execute('SELECT sku, nombre FROM productos WHERE id = %s', (id,))
    producto = cursor.fetchone()
    
    cursor.execute('''SELECT m.fecha, u.username, m.tipo, m.cantidad 
                      FROM movimientos m 
                      JOIN usuarios u ON m.usuario_id = u.id 
                      WHERE m.producto_id = %s ORDER BY m.fecha DESC''', (id,))
    historial = cursor.fetchall()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Respaldo Oficial - Purga de Historial de Trazabilidad'])
    cw.writerow(['Repuesto:', producto['nombre'], 'SKU:', producto['sku']])
    cw.writerow(['Ejecutado por:', session.get('username'), 'Fecha de Purga:', datetime.now().strftime('%Y-%m-%d %H:%M')])
    cw.writerow([])
    cw.writerow(['Fecha', 'Operario', 'Movimiento', 'Cantidad'])
    
    for h in historial:
        cw.writerow([h['fecha'], h['username'], h['tipo'], h['cantidad']])
        
    output = si.getvalue()
    
    cursor.execute('DELETE FROM movimientos WHERE producto_id = %s', (id,))
    cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                      VALUES (%s, %s, 'Purga de Historial (Respaldo CSV Descargado)', 0)''', 
                   (id, session['user_id']))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return Response(
        output, 
        mimetype="text/csv", 
        headers={"Content-Disposition": f"attachment;filename=Respaldo_Purga_{producto['sku']}.csv"}
    )