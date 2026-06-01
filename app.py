# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.utils import secure_filename
import sqlite3
import os
import csv
import io

app = Flask(__name__, template_folder='plantillas')
app.secret_key = 'clave_secreta_equi_parts'
app.config['UPLOAD_FOLDER'] = 'static/archivos'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('inventario.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    # Truco: Actualiza la base de datos automáticamente sin tener que borrarla
    try:
        conn.execute('ALTER TABLE productos ADD COLUMN activo INTEGER DEFAULT 1')
        conn.commit()
    except sqlite3.OperationalError:
        pass # Si la columna ya existe, simplemente ignora el error y continúa
    return conn

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', 
                            (request.form['username'], request.form['password'])).fetchone()
        conn.close()
        if user:
            session.update({'user_id': user['id'], 'username': user['username'], 'rol': user['rol']})
            return redirect(url_for('inventario'))
        flash('Credenciales inválidas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/inventario', methods=['GET', 'POST'])
def inventario():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    
    if request.method == 'POST' and session.get('rol') in ['Administrador', 'Bodeguero']:
        foto = request.files.get('foto')
        pdf = request.files.get('pdf')
        foto_path = secure_filename(foto.filename) if foto and foto.filename else ""
        pdf_path = secure_filename(pdf.filename) if pdf and pdf.filename else ""
        
        if foto_path: foto.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_path))
        if pdf_path: pdf.save(os.path.join(app.config['UPLOAD_FOLDER'], pdf_path))

        data = request.form
        sku = str(data.get('sku', ''))
        nombre = str(data.get('nombre', ''))
        descripcion = str(data.get('descripcion', ''))
        cantidad = int(data.get('cantidad', 0))
        precio = float(data.get('precio', 0.0))
        ubicacion = str(data.get('ubicacion', ''))
        cat_id_raw = data.get('categoria_id')
        categoria_id = int(cat_id_raw) if cat_id_raw else None

        try:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO productos (sku, nombre, descripcion, cantidad, precio, categoria_id, ubicacion, foto, ficha_pdf, activo) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                           (sku, nombre, descripcion, cantidad, precio, categoria_id, ubicacion, foto_path, pdf_path))
            nuevo_id = cursor.lastrowid
            
            cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                              VALUES (?, ?, 'Creación de Producto', ?)''', 
                           (nuevo_id, session['user_id'], cantidad))
            conn.commit()
            flash('Producto creado exitosamente.', 'success')
        except sqlite3.IntegrityError:
            flash('Error: El SKU ya existe.', 'danger')

    busqueda = request.args.get('q', '')
    # Solo mostramos los productos que están activos (activo = 1)
    query = '''SELECT p.*, c.nombre as cat_nombre FROM productos p 
               LEFT JOIN categorias c ON p.categoria_id = c.id
               WHERE p.activo = 1 AND (p.sku LIKE ? OR p.nombre LIKE ?)'''
    productos = conn.execute(query, ('%'+busqueda+'%', '%'+busqueda+'%')).fetchall()
    categorias = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    
    return render_template('inventario.html', productos=productos, categorias=categorias, 
                           username=session['username'], rol=session['rol'], busqueda=busqueda)

@app.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: return redirect(url_for('inventario'))
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.form
        cat_raw = data.get('categoria_id')
        categoria_id = int(cat_raw) if cat_raw else None
        conn.execute('''UPDATE productos SET nombre = ?, descripcion = ?, precio = ?, ubicacion = ?, categoria_id = ? 
                        WHERE id = ?''', (str(data.get('nombre')), str(data.get('descripcion')), float(data.get('precio')), str(data.get('ubicacion')), categoria_id, id))
        conn.commit()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('inventario'))
    p = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    c = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('editar_producto.html', p=p, categorias=c)

# --- CORRECCIÓN AQUÍ: ELIMINACIÓN SEGURA (BORRADO LÓGICO) ---
@app.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: return redirect(url_for('inventario'))
    conn = get_db_connection()
    try:
        # En vez de borrar (DELETE), lo ocultamos (UPDATE activo = 0)
        conn.execute('UPDATE productos SET activo = 0 WHERE id = ?', (id,))
        
        # Guardamos en auditoría que este usuario eliminó el producto
        conn.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                        VALUES (?, ?, 'Eliminación de Producto', 0)''', 
                     (id, session['user_id']))
        conn.commit()
        flash('Producto eliminado (Registro guardado en Auditoría).', 'success')
    except Exception as e: 
        flash(f'Error: {str(e)}', 'danger')
    conn.close()
    return redirect(url_for('inventario'))

@app.route('/categorias', methods=['GET', 'POST'])
def categorias():
    if 'user_id' not in session or session.get('rol') != 'Administrador': return redirect(url_for('inventario'))
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            conn.execute('INSERT INTO categorias (nombre) VALUES (?)', (str(request.form['nombre']),))
            conn.commit()
            flash('Categoría creada.', 'success')
        except: flash('La categoría ya existe.', 'danger')
    c = conn.execute('SELECT * FROM categorias').fetchall()
    conn.close()
    return render_template('categorias.html', categorias=c, username=session['username'])

@app.route('/eliminar_categoria/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': return redirect(url_for('inventario'))
    conn = get_db_connection()
    conn.execute('UPDATE productos SET categoria_id = NULL WHERE categoria_id = ?', (id,))
    conn.execute('DELETE FROM categorias WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('categorias'))

@app.route('/producto/<int:id>', methods=['GET', 'POST'])
def detalle_producto(id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()

    if request.method == 'POST':
        tipo = request.form['tipo']
        cantidad_mov = int(request.form['cantidad'])
        p = conn.execute('SELECT cantidad, stock_reservado FROM productos WHERE id = ?', (id,)).fetchone()
        stock_fisico = p['cantidad']
        stock_reservado = p['stock_reservado']
        stock_disponible = stock_fisico - stock_reservado
        cursor = conn.cursor()
        error = False

        if tipo == 'Cotizacion':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock.', 'danger')
                error = True
            else:
                cursor.execute('UPDATE productos SET stock_reservado = stock_reservado + ? WHERE id = ?', (cantidad_mov, id))
                flash('Cotización creada.', 'info')
        elif tipo == 'Venta_Cotizacion':
            if cantidad_mov > stock_reservado:
                flash('Error: Cantidad supera la reserva.', 'danger')
                error = True
            else:
                cursor.execute('UPDATE productos SET cantidad = cantidad - ?, stock_reservado = stock_reservado - ? WHERE id = ?', (cantidad_mov, cantidad_mov, id))
                flash('Venta concretada.', 'success')
        elif tipo == 'Salida':
            if cantidad_mov > stock_disponible:
                flash('Error: No hay suficiente stock.', 'danger')
                error = True
            else:
                cursor.execute('UPDATE productos SET cantidad = cantidad - ? WHERE id = ?', (cantidad_mov, id))
                flash('Venta directa registrada.', 'success')
        elif tipo == 'Entrada':
            cursor.execute('UPDATE productos SET cantidad = cantidad + ? WHERE id = ?', (cantidad_mov, id))
            flash('Ingreso registrado.', 'success')

        if not error:
            cursor.execute('INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) VALUES (?, ?, ?, ?)',
                           (id, session['user_id'], tipo, cantidad_mov))
            mov_id = cursor.lastrowid
            conn.commit()
            if tipo in ['Salida', 'Venta_Cotizacion', 'Cotizacion']:
                return redirect(url_for('comprobante', mov_id=mov_id))

    producto = conn.execute('SELECT * FROM productos WHERE id = ?', (id,)).fetchone()
    historial = conn.execute('''SELECT m.*, u.username FROM movimientos m 
                                JOIN usuarios u ON m.usuario_id = u.id 
                                WHERE m.producto_id = ? ORDER BY m.fecha DESC LIMIT 10''', (id,)).fetchall()
    conn.close()
    return render_template('detalle_producto.html', p=producto, historial=historial)

@app.route('/comprobante/<int:mov_id>')
def comprobante(mov_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    datos = conn.execute('''SELECT m.id, m.fecha, m.cantidad, m.tipo, p.sku, p.nombre, p.precio, u.username 
                            FROM movimientos m JOIN productos p ON m.producto_id = p.id
                            JOIN usuarios u ON m.usuario_id = u.id WHERE m.id = ?''', (mov_id,)).fetchone()
    conn.close()
    subtotal = round(datos['cantidad'] * datos['precio'], 2)
    iva = round(subtotal * 0.13, 2)
    total = round(subtotal + iva, 2)
    return render_template('comprobante.html', d=datos, subtotal=subtotal, iva=iva, total=total)

@app.route('/importar', methods=['POST'])
def importar_csv():
    if 'user_id' not in session or session.get('rol') not in ['Administrador', 'Bodeguero']: return redirect(url_for('inventario'))
    file = request.files.get('archivo_csv')
    if not file or file.filename == '': return redirect(url_for('inventario'))
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.reader(stream)
        next(csv_input)
        conn = get_db_connection()
        cursor = conn.cursor()
        importados = 0
        for row in csv_input:
            if len(row) >= 5:
                try: 
                    cantidad_inicial = int(row[3])
                    cursor.execute('''INSERT INTO productos (sku, nombre, descripcion, cantidad, precio, ubicacion, activo) 
                                      VALUES (?, ?, ?, ?, ?, ?, 1)''', (str(row[0]), str(row[1]), str(row[2]), cantidad_inicial, float(row[4]), 'Bodega'))
                    nuevo_id = cursor.lastrowid
                    cursor.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                                      VALUES (?, ?, 'Importación CSV', ?)''', 
                                   (nuevo_id, session['user_id'], cantidad_inicial))
                    importados += 1
                except: pass
        conn.commit()
        conn.close()
        flash(f'{importados} productos importados y auditados.', 'success')
    except Exception as e: flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('inventario'))

@app.route('/auditoria')
def auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        flash('No tienes permisos.', 'danger')
        return redirect(url_for('inventario'))
    conn = get_db_connection()
    # Ahora la consulta incluye productos aunque estén "borrados" lógicamente (activo = 0)
    query = '''SELECT m.id AS transaccion_id, m.fecha, m.tipo, m.cantidad, 
               u.username, u.rol, p.sku, p.nombre
               FROM movimientos m JOIN usuarios u ON m.usuario_id = u.id JOIN productos p ON m.producto_id = p.id
               ORDER BY m.fecha DESC'''
    logs = conn.execute(query).fetchall()
    conn.close()
    return render_template('auditoria.html', logs=logs, username=session['username'])

@app.route('/exportar_auditoria')
def exportar_auditoria():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario'))
    
    conn = get_db_connection()
    query = '''SELECT m.id, m.fecha, u.username, u.rol, m.tipo, p.sku, p.nombre, m.cantidad
               FROM movimientos m JOIN usuarios u ON m.usuario_id = u.id JOIN productos p ON m.producto_id = p.id
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

@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user_id' not in session or session.get('rol') != 'Administrador': return redirect(url_for('inventario'))
    conn = get_db_connection()
    if request.method == 'POST':
        try:
            conn.execute('INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)', 
                         (str(request.form['username']), str(request.form['password']), str(request.form['rol'])))
            conn.commit()
            flash('Usuario creado.', 'success')
        except: flash('El usuario ya existe.', 'danger')
    u = conn.execute('SELECT id, username, rol FROM usuarios').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=u, username=session['username'])

@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': return redirect(url_for('inventario'))
    conn = get_db_connection()
    if request.method == 'POST':
        nueva_clave = request.form.get('password')
        nuevo_rol = request.form.get('rol')
        if nueva_clave:
            conn.execute('UPDATE usuarios SET password = ?, rol = ? WHERE id = ?', (nueva_clave, nuevo_rol, id))
        else:
            conn.execute('UPDATE usuarios SET rol = ? WHERE id = ?', (nuevo_rol, id))
        conn.commit()
        flash('Usuario actualizado correctamente.', 'success')
        return redirect(url_for('usuarios'))
    usuario = conn.execute('SELECT id, username, rol FROM usuarios WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('editar_usuario.html', u=usuario)

@app.route('/eliminar_usuario/<int:id>', methods=['POST'])
def eliminar_usuario(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': return redirect(url_for('inventario'))
    if id == session['user_id']:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('usuarios'))
    conn = get_db_connection()
    conn.execute('DELETE FROM usuarios WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('usuarios'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
