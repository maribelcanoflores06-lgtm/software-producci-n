from django.db import connection, transaction

from apps.maestros.models import CorrelativoNota, CorrelativoOp


def _bloquear(consulta):
    # SQLite no implementa SELECT FOR UPDATE. La transacción ya serializa
    # la escritura. En PostgreSQL el mismo código toma el bloqueo de fila.
    if connection.features.has_select_for_update:
        return consulta.select_for_update()
    return consulta


def next_nota(anio, almacen):
    with transaction.atomic():
        CorrelativoNota.objects.get_or_create(anio=anio, almacen=almacen, defaults={'ultimo': 0})
        fila = _bloquear(CorrelativoNota.objects).get(anio=anio, almacen=almacen)
        fila.ultimo += 1
        fila.save(update_fields=['ultimo'])
        return f'{almacen.codigo}-{anio.anio}-{fila.ultimo:06d}'


def next_op(anio):
    with transaction.atomic():
        CorrelativoOp.objects.get_or_create(anio=anio, defaults={'ultimo': 0})
        fila = _bloquear(CorrelativoOp.objects).get(anio=anio)
        fila.ultimo += 1
        fila.save(update_fields=['ultimo'])
        return f'OP-{anio.anio}-{fila.ultimo:04d}'
