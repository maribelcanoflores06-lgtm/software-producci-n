from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CUATRO = Decimal('0.0001')
CENTAVO = Decimal('0.01')


def q4(valor):
    return Decimal(valor).quantize(CUATRO, rounding=ROUND_HALF_UP)


def normalizar_entrada(texto):
    """Acepta punto decimal y coma de miles (1,250.50).

    Una coma suelta sigue valiendo como decimal (2,5) para lo ya escrito.
    Si la coma queda después del punto (1.250,50), también se lee como decimal.
    """
    texto = str(texto).strip().replace(' ', '').replace('\u00a0', '')
    if texto == '':
        return texto
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            return texto.replace('.', '').replace(',', '.')
        return texto.replace(',', '')
    if ',' not in texto:
        return texto
    partes = texto.split(',')
    miles = (
        len(partes) > 1
        and partes[0].lstrip('-').isdigit()
        and all(parte.isdigit() and len(parte) == 3 for parte in partes[1:])
    )
    if miles:
        return ''.join(partes)
    return texto.replace(',', '.')


def _numero(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, str):
        limpio = normalizar_entrada(valor)
        if limpio == '':
            return None
        return Decimal(limpio)
    return Decimal(valor)


def _con_miles(entero):
    signo = ''
    if entero.startswith('-'):
        signo = '-'
        entero = entero[1:]
    grupos = []
    while entero:
        grupos.append(entero[-3:])
        entero = entero[:-3]
    return signo + ','.join(reversed(grupos))


def formato_cantidad(valor):
    """Cantidad: hasta 4 decimales, sin ceros de más. 50, 2.5, 1,250.5."""
    try:
        numero = _numero(valor)
    except (InvalidOperation, ValueError, TypeError):
        return '' if valor in (None, '') else str(valor)
    if numero is None:
        return ''
    numero = q4(numero)
    texto = f'{numero:.4f}'.rstrip('0').rstrip('.')
    if '.' in texto:
        entero, frac = texto.split('.')
        return f'{_con_miles(entero)}.{frac}'
    return _con_miles(texto)


def formato_costo(valor):
    """Costo unitario o promedio: siempre 4 decimales. 3.0000, 1,250.5000."""
    try:
        numero = _numero(valor)
    except (InvalidOperation, ValueError, TypeError):
        return '' if valor in (None, '') else str(valor)
    if numero is None:
        return ''
    entero, frac = f'{q4(numero):.4f}'.split('.')
    return f'{_con_miles(entero)}.{frac}'


def formato_soles(valor):
    """Monto en soles: 2 decimales. 1,250.00."""
    try:
        numero = _numero(valor)
    except (InvalidOperation, ValueError, TypeError):
        return '' if valor in (None, '') else str(valor)
    if numero is None:
        return ''
    numero = numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    entero, frac = f'{numero:.2f}'.split('.')
    return f'{_con_miles(entero)}.{frac}'
