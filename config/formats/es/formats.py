"""Separadores numéricos de la interfaz.

El idioma sigue en español, pero el decimal es punto y los miles van con coma
(1,250.00). Así Django no pinta la coma decimal del locale es.
"""

DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3
