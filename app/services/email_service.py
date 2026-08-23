from flask_mail import Message
from app import mail
from flask import current_app
from app.database import get_db_connection

def enviar_alerta_stock(nombre_producto, sku, stock_actual, correos_destino, producto_id, usuario_id):
    """
    Envía un correo de alerta a una lista de destinatarios y guarda el registro.
    """
    if not correos_destino:
        return

    asunto = f"⚠️ ALERTA DE STOCK CRÍTICO: {nombre_producto}"
    
    cuerpo_mensaje = f"""
    SISTEMA DE INVENTARIO EQUI-PARTS S&S
    ------------------------------------
    Alerta Automática de Reabastecimiento

    El siguiente repuesto ha alcanzado su nivel mínimo de stock:
    
    - Producto: {nombre_producto}
    - SKU: {sku}
    - Stock Físico Disponible: {stock_actual} unidades
    
    Por favor, gestione la compra o ingreso a bodega a la brevedad.
    """

    try:
        msg = Message(asunto,
                      sender=current_app.config['MAIL_USERNAME'],
                      recipients=correos_destino,
                      body=cuerpo_mensaje)
        mail.send(msg)
        print(f"Correo de alerta enviado a: {correos_destino}")
        
        # --- NUEVO: GUARDAR EL ENVÍO EN LA AUDITORÍA ---
        conn = get_db_connection()
        conn.execute('''INSERT INTO movimientos (producto_id, usuario_id, tipo, cantidad) 
                        VALUES (?, ?, 'Alerta de Stock (Correo)', ?)''', 
                     (producto_id, usuario_id, stock_actual))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error al enviar el correo de alerta: {e}")