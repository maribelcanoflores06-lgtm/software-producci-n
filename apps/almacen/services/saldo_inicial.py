from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.almacen.models import Kardex, Movimiento, MovimientoDetalle, StockActual
from apps.almacen.services.numeracion import next_nota
from apps.core.numeros import q4
from apps.maestros.models import SaldoInicial


def registrar_saldo_inicial(*, anio, almacen, articulo, cantidad, costo_unitario, usuario, fecha=None):
    cantidad = q4(cantidad)
    costo_unitario = q4(costo_unitario)
    if anio.cerrado:
        raise ValidationError('El año está cerrado y no admite movimientos.')
    if not almacen.activo:
        raise ValidationError('El almacén está inactivo.')
    if not articulo.activo:
        raise ValidationError('El artículo está inactivo.')
    if cantidad <= 0:
        raise ValidationError('La cantidad debe ser mayor que cero.')
    if costo_unitario < 0:
        raise ValidationError('El costo unitario no puede ser negativo.')
    valor = q4(cantidad * costo_unitario)
    fecha = fecha or date(anio.anio, 1, 1)
    if fecha.year != anio.anio:
        raise ValidationError('La fecha del saldo debe pertenecer al año seleccionado.')

    with transaction.atomic():
        if SaldoInicial.objects.filter(anio=anio, almacen=almacen, articulo=articulo).exists():
            raise ValidationError('Ya existe un saldo inicial de este artículo en el almacén y año.')
        numero = next_nota(anio, almacen)
        movimiento = Movimiento.objects.create(
            numero_nota=numero,
            anio=anio,
            tipo=Movimiento.SALDO_INICIAL,
            fecha=fecha,
            fecha_hora=timezone.now(),
            almacen=almacen,
            almacen_destino=almacen,
            observacion='Saldo inicial',
            created_by=usuario,
        )
        detalle = MovimientoDetalle.objects.create(
            movimiento=movimiento,
            articulo=articulo,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            costo_total=valor,
        )
        Kardex.objects.create(
            anio=anio,
            articulo=articulo,
            almacen=almacen,
            movimiento_detalle=detalle,
            fecha=fecha,
            fecha_hora=timezone.now(),
            tipo_mov=Movimiento.SALDO_INICIAL,
            numero_nota=numero,
            cantidad_entrada=cantidad,
            cantidad_salida=0,
            saldo_cantidad=cantidad,
            costo_unit_mov=costo_unitario,
            costo_unit_promedio=costo_unitario,
            valor_entrada=valor,
            valor_salida=0,
            saldo_valor=valor,
            es_revalorizacion=False,
        )
        StockActual.objects.create(
            articulo=articulo,
            almacen=almacen,
            anio=anio,
            cantidad=cantidad,
            costo_promedio=costo_unitario,
            valor=valor,
            ultima_nota=numero,
        )
        saldo = SaldoInicial(
            anio=anio,
            almacen=almacen,
            articulo=articulo,
            cantidad=cantidad,
            costo_promedio=costo_unitario,
            valor=valor,
        )
        saldo.full_clean()
        saldo.save()
        return saldo, movimiento
