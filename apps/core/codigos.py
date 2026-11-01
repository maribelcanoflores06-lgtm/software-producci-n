import re

from django.core.exceptions import ValidationError

PATRON_CODIGO = re.compile(r'^[A-Z0-9][A-Z0-9_./-]{0,39}$')
PATRON_ALMACEN = re.compile(r'^[A-Z][A-Z0-9]{1,19}$')

MENSAJE_CODIGO = 'Use letras y números, sin espacios.'
MENSAJE_ALMACEN = 'El código de almacén usa letras y números (ejemplo ALM01), sin espacios ni símbolos.'


def normalizar_codigo(valor, patron=PATRON_CODIGO, mensaje=MENSAJE_CODIGO):
    valor = (valor or '').strip().upper()
    if not valor or patron.fullmatch(valor) is None:
        raise ValidationError(mensaje)
    return valor
