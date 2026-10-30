from decimal import Decimal, InvalidOperation

MAX_STOCK = 1_000_000_000
MAX_PRICE = Decimal('999999999.99')

def entero(valor, nombre, minimo=0, maximo=MAX_STOCK):
    try:
        texto = str(valor).strip()
        if not texto or not texto.isascii() or not texto.isdecimal():
            raise ValueError()
        numero = int(texto)
        if not minimo <= numero <= maximo:
            raise ValueError()
        return numero
    except (ValueError, TypeError):
        raise ValueError(f'{nombre}: introduce un número entero entre {minimo} y {maximo}.')

def importe(valor, nombre='Precio'):
    try:
        numero = Decimal(str(valor).strip())
        if not numero.is_finite() or not 0 <= numero <= MAX_PRICE or numero.as_tuple().exponent < -2:
            raise ValueError()
        return numero
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{nombre}: importe inválido. Usa un número entre 0 y {MAX_PRICE}, con dos decimales como máximo.')
