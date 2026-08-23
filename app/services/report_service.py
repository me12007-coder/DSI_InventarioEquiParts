import io
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generar_excel_movimientos(logs):
    """Genera un archivo Excel en memoria listo para descargar."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Movimientos"
    
    # Encabezados
    headers = ['ID Transacción', 'Fecha', 'Usuario', 'Rol', 'Operación', 'SKU', 'Repuesto', 'Cantidad']
    ws.append(headers)
    
    for log in logs:
        ws.append([log['transaccion_id'], log['fecha'], log['username'], log['rol'], log['tipo'], log['sku'], log['nombre'], log['cantidad']])
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def generar_pdf_movimientos(logs):
    """Genera un archivo PDF ejecutivo en memoria usando ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=20, textColor=colors.HexColor('#1a252f'))
    
    story.append(Paragraph("Equi Parts - Reporte de Auditoría e Inventario", title_style))
    story.append(Spacer(1, 12))
    
    # Construcción de la tabla
    tabla_datos = [['ID', 'Fecha', 'Usuario', 'Operación', 'SKU', 'Cant']]
    for log in logs:
        # Simplificado para que quepa en formato carta horizontal/vertical ajustado
        tabla_datos.append([
            str(log['transaccion_id']),
            str(log['fecha'])[:10], # Solo la fecha sin hora para ahorrar espacio
            str(log['username']),
            str(log['tipo']),
            str(log['sku']),
            str(log['cantidad'])
        ])
        
    t = Table(tabla_datos, colWidths=[30, 70, 70, 150, 80, 40])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
