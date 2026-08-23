from flask import Flask
from flask_mail import Mail
import os

# Instanciamos Mail fuera para poder importarlo en otros archivos
mail = Mail()

def create_app():
    app = Flask(__name__, template_folder='plantillas')
    app.secret_key = 'clave_secreta_equi_parts'
    
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/archivos')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # --- CONFIGURACIÓN DE CORREO (Ejemplo con Gmail) ---
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    # Reemplaza con el correo real de la empresa
    app.config['MAIL_USERNAME'] = 'me12007@ues.edu.sv' 
    # Aquí va la "Contraseña de Aplicación" de Google, NO la contraseña normal
    app.config['MAIL_PASSWORD'] = 'twefggqvlpkaaarg' 
    
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