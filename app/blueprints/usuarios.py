from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from app.database import get_db_connection

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        username = str(request.form['username']).strip()
        password = request.form['password']
        rol = str(request.form['rol'])
        email = str(request.form.get('email', '')).strip() # Capturamos el nuevo campo

        if not username or len(username) > 80 or len(password) < 12 or len(password) > 256 or rol not in ('Administrador', 'Bodeguero', 'Vendedor') or len(email) > 254 or (email and ('@' not in email or ' ' in email)):
            flash('Revisa el nombre, rol y correo. La contraseña debe tener 12–256 caracteres.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('usuarios.usuarios'))
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO usuarios (username, password, rol, email, activo) VALUES (%s, %s, %s, %s, 1)', 
                         (username, hashed_password, rol, email))
            conn.commit()
            flash('Usuario creado exitosamente.', 'success')
        except Exception as e: 
            flash('Error: El nombre de usuario ya existe o los datos son inválidos.', 'danger')
            
    cursor.execute('SELECT id, username, rol, email, activo FROM usuarios')
    u = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('usuarios.html', usuarios=u, username=session.get('username'))

@usuarios_bp.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'POST':
        nueva_clave = request.form.get('password')
        nuevo_rol = request.form.get('rol')
        nuevo_email = str(request.form.get('email', '')).strip() # Capturamos el correo editado
        
        if nuevo_rol not in ('Administrador', 'Bodeguero', 'Vendedor') or len(nuevo_email) > 254 or (nuevo_email and ('@' not in nuevo_email or ' ' in nuevo_email)) or (nueva_clave and not 12 <= len(nueva_clave) <= 256):
            flash('Rol, correo o contraseña inválidos (mínimo 12 caracteres).', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('usuarios.usuarios'))
        if nueva_clave:
            hashed_password = generate_password_hash(nueva_clave)
            cursor.execute('UPDATE usuarios SET password = %s, rol = %s, email = %s WHERE id = %s', 
                         (hashed_password, nuevo_rol, nuevo_email, id))
        else:
            cursor.execute('UPDATE usuarios SET rol = %s, email = %s WHERE id = %s', 
                         (nuevo_rol, nuevo_email, id))
        
        conn.commit()
        flash('Usuario actualizado correctamente.', 'success')
        cursor.close()
        conn.close()
        return redirect(url_for('usuarios.usuarios'))
        
    cursor.execute('SELECT id, username, rol, email FROM usuarios WHERE id = %s', (id,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('editar_usuario.html', u=usuario)

@usuarios_bp.route('/eliminar_usuario/<int:id>', methods=['POST'])
def eliminar_usuario(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
        
    if id == session['user_id']:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('usuarios.usuarios'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuarios WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('usuarios.usuarios'))

@usuarios_bp.route('/toggle_estado/<int:id>', methods=['POST'])
def toggle_estado(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
        
    if id == session['user_id']:
        flash('No puedes deshabilitar tu propia cuenta.', 'danger')
        return redirect(url_for('usuarios.usuarios'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT activo FROM usuarios WHERE id = %s", (id,))
        usuario = cursor.fetchone()
        
        if usuario:
            nuevo_estado = 0 if usuario['activo'] else 1
            cursor.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (nuevo_estado, id))
            conn.commit()
            
            accion = "habilitado" if nuevo_estado else "deshabilitado"
            flash(f'Usuario {accion} correctamente.', 'success')
        else:
            flash('Usuario no encontrado.', 'danger')
            
    except Exception as e:
        conn.rollback()
        flash(f'Error al cambiar el estado: {e}', 'danger')
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('usuarios.usuarios'))