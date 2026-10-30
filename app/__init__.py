from flask import Flask, request, session, abort, flash, redirect, url_for
from flask_mail import Mail
import os
import secrets
import hmac
from datetime import timedelta, date

# Instanciamos Mail fuera para poder importarlo en otros archivos
mail = Mail()

def create_app():
    app = Flask(__name__, template_folder='plantillas')
    app.secret_key = os.environ.get('EQUIPARTS_SECRET_KEY')
    if not app.secret_key:
        raise RuntimeError('Configura EQUIPARTS_SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))")')
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('EQUIPARTS_HTTPS','0') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=10 * 1024 * 1024)
    
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/archivos')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # --- CONFIGURACIÓN DE CORREO (Ejemplo con Gmail) ---
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    # Reemplaza con el correo real de la empresa
    app.config['MAIL_USERNAME'] = os.getenv('EQUIPARTS_MAIL_USERNAME', '') 
    # Aquí va la "Contraseña de Aplicación" de Google, NO la contraseña normal
    app.config['MAIL_PASSWORD'] = os.getenv('EQUIPARTS_MAIL_PASSWORD', '') 
    
    @app.before_request
    def proteger_solicitudes():
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            esperado = session.get('_csrf_token')
            recibido = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
            if not esperado or not recibido or not hmac.compare_digest(esperado, recibido):
                abort(400, description='Token de seguridad ausente o inválido. Actualiza la página.')

    @app.context_processor
    def token_formulario():
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_urlsafe(32)
        return {'csrf_token': lambda: session['_csrf_token'], 'hoy': date.today().isoformat()}

    @app.after_request
    def cabeceras_seguridad(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        return response

    @app.errorhandler(ValueError)
    def error_validacion(error):
        if request.method == 'POST':
            flash(str(error), 'danger')
            return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url) else url_for('inventario.inventario'))
        return str(error), 400

    mail.init_app(app)

    # Importar y registrar blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.inventario import inventario_bp
    from .blueprints.usuarios import usuarios_bp
    from .blueprints.reportes import reportes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(reportes_bp)

    return app