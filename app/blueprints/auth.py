from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from app.database import get_db_connection

# Creamos el blueprint para la autenticación
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE username = ?', 
                            (request.form['username'],)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], request.form['password']):
            session.clear() # Limpiamos cualquier sesión previa por seguridad
            session.update({
                'user_id': user['id'], 
                'username': user['username'], 
                'rol': user['rol']
            })
            return redirect(url_for('inventario.inventario'))
            
        flash('Credenciales inválidas.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))