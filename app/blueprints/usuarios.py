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
    if request.method == 'POST':
        username = str(request.form['username']).strip()
        password = request.form['password']
        rol = str(request.form['rol'])
        email = str(request.form.get('email', '')).strip() # Capturamos el nuevo campo

        try:
            hashed_password = generate_password_hash(password)
            conn.execute('INSERT INTO usuarios (username, password, rol, email) VALUES (?, ?, ?, ?)', 
                         (username, hashed_password, rol, email))
            conn.commit()
            flash('Usuario creado exitosamente.', 'success')
        except Exception as e: 
            flash('Error: El nombre de usuario ya existe o los datos son inválidos.', 'danger')
            
    u = conn.execute('SELECT id, username, rol, email FROM usuarios').fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=u, username=session.get('username'))

@usuarios_bp.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
def editar_usuario(id):
    if 'user_id' not in session or session.get('rol') != 'Administrador': 
        return redirect(url_for('inventario.inventario'))
    
    conn = get_db_connection()
    if request.method == 'POST':
        nueva_clave = request.form.get('password')
        nuevo_rol = request.form.get('rol')
        nuevo_email = str(request.form.get('email', '')).strip() # Capturamos el correo editado
        
        if nueva_clave:
            hashed_password = generate_password_hash(nueva_clave)
            conn.execute('UPDATE usuarios SET password = ?, rol = ?, email = ? WHERE id = ?', 
                         (hashed_password, nuevo_rol, nuevo_email, id))
        else:
            conn.execute('UPDATE usuarios SET rol = ?, email = ? WHERE id = ?', 
                         (nuevo_rol, nuevo_email, id))
        
        conn.commit()
        flash('Usuario actualizado correctamente.', 'success')
        return redirect(url_for('usuarios.usuarios'))
        
    usuario = conn.execute('SELECT id, username, rol, email FROM usuarios WHERE id = ?', (id,)).fetchone()
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
    conn.execute('DELETE FROM usuarios WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('usuarios.usuarios'))