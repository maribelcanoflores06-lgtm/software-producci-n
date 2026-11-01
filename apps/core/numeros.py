from decimal import Decimal, ROUND_HALF_UP

CUATRO = Decimal('0.0001')


def q4(valor):
    return Decimal(valor).quantize(CUATRO, rounding=ROUND_HALF_UP)
