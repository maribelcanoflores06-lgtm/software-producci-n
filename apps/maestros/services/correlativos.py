"""Correlativos en cero: una fila por año y almacén, y una de OP por año.

Se crean al dar de alta el año o el almacén. No se reinicia `ultimo` si la fila ya existe.
"""

from apps.maestros.models import Almacen, Anio, CorrelativoNota, CorrelativoOp


def asegurar_correlativos_anio(anio):
    CorrelativoOp.objects.get_or_create(anio=anio, defaults={'ultimo': 0})
    for almacen in Almacen.objects.all().only('id'):
        CorrelativoNota.objects.get_or_create(
            anio=anio,
            almacen=almacen,
            defaults={'ultimo': 0},
        )


def asegurar_correlativos_almacen(almacen):
    for anio in Anio.objects.all().only('id'):
        CorrelativoNota.objects.get_or_create(
            anio=anio,
            almacen=almacen,
            defaults={'ultimo': 0},
        )
