"""Kardex por promedio ponderado.

Ingreso: el usuario informa el costo en soles y el promedio se recalcula.
Salida y salida de transferencia: salen al promedio vigente, sin cambiarlo.
La entrada de una transferencia recalcula el promedio del destino como un ingreso.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.almacen.models import Kardex, Movimiento, MovimientoDetalle, StockActual
from apps.almacen.services.numeracion import next_nota
from apps.core.numeros import q4


def crear_ingreso(
    *,
    anio,
    fecha,
    subtipo,
    almacen_destino,
    proveedor,
    lineas,
    usuario,
    tipo_comprobante='',
    serie_doc='',
    numero_doc='',
    fecha_doc=None,
    observacion='',
    cliente=None,
):
    _validar_periodo(anio, fecha)
    _validar_almacen_normal(almacen_destino)
    if proveedor is None:
        raise ValidationError('El ingreso exige un proveedor.')
    if not proveedor.activo:
        raise ValidationError('El proveedor está inactivo.')
    if subtipo not in {codigo for codigo, _nombre in Movimiento.SUBTIPOS}:
        raise ValidationError('Seleccione el subtipo de ingreso.')
    _validar_cliente(cliente)
    limpias = _normalizar_lineas(lineas, con_costo=True)

    with transaction.atomic():
        _bloquear_anio(anio)
        numero = next_nota(anio, almacen_destino)
        ahora = timezone.now()
        movimiento = Movimiento.objects.create(
            numero_nota=numero,
            anio=anio,
            tipo=Movimiento.INGRESO,
            subtipo=subtipo,
            fecha=fecha,
            fecha_hora=ahora,
            almacen=almacen_destino,
            almacen_destino=almacen_destino,
            proveedor=proveedor,
            cliente=cliente,
            tipo_comprobante=(tipo_comprobante or '').strip(),
            serie_doc=(serie_doc or '').strip(),
            numero_doc=(numero_doc or '').strip(),
            fecha_doc=fecha_doc,
            observacion=(observacion or '').strip(),
            created_by=usuario,
        )
        for linea in limpias:
            detalle = _crear_detalle(movimiento, linea, linea['costo_unitario'])
            _aplicar_entrada(
                anio=anio,
                almacen=almacen_destino,
                articulo=linea['articulo'],
                detalle=detalle,
                fecha=fecha,
                fecha_hora=ahora,
                tipo_mov=Movimiento.INGRESO,
                numero_nota=numero,
                cantidad=linea['cantidad'],
                costo_unitario=linea['costo_unitario'],
            )
        return movimiento


def crear_salida(
    *,
    anio,
    fecha,
    almacen_origen,
    lineas,
    usuario,
    cliente=None,
    tipo_comprobante='',
    serie_doc='',
    numero_doc='',
    fecha_doc=None,
    observacion='',
):
    _validar_periodo(anio, fecha)
    _validar_almacen_normal(almacen_origen)
    _validar_cliente(cliente)
    limpias = _normalizar_lineas(lineas, con_costo=False)

    with transaction.atomic():
        _bloquear_anio(anio)
        numero = next_nota(anio, almacen_origen)
        ahora = timezone.now()
        movimiento = Movimiento.objects.create(
            numero_nota=numero,
            anio=anio,
            tipo=Movimiento.SALIDA,
            fecha=fecha,
            fecha_hora=ahora,
            almacen=almacen_origen,
            almacen_origen=almacen_origen,
            cliente=cliente,
            tipo_comprobante=(tipo_comprobante or '').strip(),
            serie_doc=(serie_doc or '').strip(),
            numero_doc=(numero_doc or '').strip(),
            fecha_doc=fecha_doc,
            observacion=(observacion or '').strip(),
            created_by=usuario,
        )
        for linea in limpias:
            costo, valor_salida, stock, nuevo_cant, nuevo_valor = _preparar_salida(
                anio, almacen_origen, linea['articulo'], linea['cantidad'],
            )
            detalle = _crear_detalle(movimiento, linea, costo)
            _escribir_salida(
                stock=stock,
                detalle=detalle,
                anio=anio,
                almacen=almacen_origen,
                articulo=linea['articulo'],
                fecha=fecha,
                fecha_hora=ahora,
                tipo_mov=Movimiento.SALIDA,
                numero_nota=numero,
                cantidad=linea['cantidad'],
                costo=costo,
                valor_salida=valor_salida,
                nuevo_cant=nuevo_cant,
                nuevo_valor=nuevo_valor,
            )
        return movimiento


def crear_transferencia(
    *,
    anio,
    fecha,
    almacen_origen,
    almacen_destino,
    lineas,
    usuario,
    observacion='',
    tipo_comprobante='',
    serie_doc='',
    numero_doc='',
    fecha_doc=None,
):
    _validar_periodo(anio, fecha)
    _validar_almacen_normal(almacen_origen)
    _validar_almacen_normal(almacen_destino)
    if almacen_origen.pk == almacen_destino.pk:
        raise ValidationError('El almacén de origen y el de destino deben ser distintos.')
    limpias = _normalizar_lineas(lineas, con_costo=False)

    with transaction.atomic():
        _bloquear_anio(anio)
        numero = next_nota(anio, almacen_origen)
        ahora = timezone.now()
        movimiento = Movimiento.objects.create(
            numero_nota=numero,
            anio=anio,
            tipo=Movimiento.TRANSFERENCIA,
            fecha=fecha,
            fecha_hora=ahora,
            almacen=almacen_origen,
            almacen_origen=almacen_origen,
            almacen_destino=almacen_destino,
            tipo_comprobante=(tipo_comprobante or '').strip(),
            serie_doc=(serie_doc or '').strip(),
            numero_doc=(numero_doc or '').strip(),
            fecha_doc=fecha_doc,
            observacion=(observacion or '').strip(),
            created_by=usuario,
        )
        for linea in limpias:
            costo, valor_salida, stock, nuevo_cant, nuevo_valor = _preparar_salida(
                anio, almacen_origen, linea['articulo'], linea['cantidad'],
            )
            detalle = _crear_detalle(movimiento, linea, costo)
            _escribir_salida(
                stock=stock,
                detalle=detalle,
                anio=anio,
                almacen=almacen_origen,
                articulo=linea['articulo'],
                fecha=fecha,
                fecha_hora=ahora,
                tipo_mov=Movimiento.TRANSFERENCIA,
                numero_nota=numero,
                cantidad=linea['cantidad'],
                costo=costo,
                valor_salida=valor_salida,
                nuevo_cant=nuevo_cant,
                nuevo_valor=nuevo_valor,
            )
            _aplicar_entrada(
                anio=anio,
                almacen=almacen_destino,
                articulo=linea['articulo'],
                detalle=detalle,
                fecha=fecha,
                fecha_hora=ahora,
                tipo_mov=Movimiento.TRANSFERENCIA,
                numero_nota=numero,
                cantidad=linea['cantidad'],
                costo_unitario=costo,
            )
        return movimiento


apply_ingreso = crear_ingreso
apply_salida = crear_salida
apply_transferencia = crear_transferencia


def _validar_periodo(anio, fecha):
    if anio.cerrado:
        raise ValidationError('El año está cerrado y no admite movimientos.')
    if fecha is None or fecha.year != anio.anio:
        raise ValidationError('La fecha del movimiento debe pertenecer al año seleccionado.')


def _bloquear_anio(anio):
    from apps.maestros.models import Anio

    consulta = Anio.objects.filter(pk=anio.pk)
    if connection.features.has_select_for_update:
        consulta = consulta.select_for_update()
    fresco = consulta.get()
    if fresco.cerrado:
        raise ValidationError('El año está cerrado y no admite movimientos.')
    return fresco


def _validar_almacen_normal(almacen):
    if almacen is None:
        raise ValidationError('Seleccione un almacén.')
    if not almacen.activo:
        raise ValidationError(f'El almacén {almacen.codigo} está inactivo.')
    if almacen.es_proceso:
        raise ValidationError(
            f'El almacén {almacen.codigo} es de proceso. '
            'Solo se usa en salida o entrada de producción.'
        )


def _validar_cliente(cliente):
    if cliente is not None and not cliente.activo:
        raise ValidationError('El cliente está inactivo.')


def _normalizar_lineas(lineas, con_costo):
    if not lineas:
        raise ValidationError('Agregue al menos una línea.')
    limpias = []
    for linea in lineas:
        articulo = linea.get('articulo')
        if articulo is None:
            raise ValidationError('Seleccione un artículo.')
        if not articulo.activo:
            raise ValidationError(f'El artículo {articulo.codigo} está inactivo.')
        cantidad = q4(linea.get('cantidad') or 0)
        if cantidad <= 0:
            raise ValidationError('La cantidad debe ser mayor que cero.')
        item = {
            'articulo': articulo,
            'cantidad': cantidad,
            'lote_ref': (linea.get('lote_ref') or '')[:40],
            'ubicacion_ref': (linea.get('ubicacion_ref') or '')[:40],
            'observacion': (linea.get('observacion') or '')[:200],
        }
        if con_costo:
            costo = q4(linea.get('costo_unitario') or 0)
            if costo <= 0:
                raise ValidationError('El costo unitario del ingreso debe ser mayor que cero.')
            item['costo_unitario'] = costo
        limpias.append(item)
    return limpias


def _crear_detalle(movimiento, linea, costo):
    costo = q4(costo)
    cantidad = linea['cantidad']
    return MovimientoDetalle.objects.create(
        movimiento=movimiento,
        articulo=linea['articulo'],
        cantidad=cantidad,
        costo_unitario=costo,
        costo_total=q4(cantidad * costo),
        lote_ref=linea.get('lote_ref') or '',
        ubicacion_ref=linea.get('ubicacion_ref') or '',
        observacion=linea.get('observacion') or '',
    )


def _fmt(valor):
    return f'{q4(valor):.4f}'


def _preparar_salida(anio, almacen, articulo, cantidad):
    stock = _bloquear_stock(anio, almacen, articulo)
    disponible = stock.cantidad if stock is not None else q4(0)
    if stock is None or cantidad > disponible:
        raise ValidationError(
            f'Stock insuficiente de {articulo.codigo} en {almacen.codigo}: '
            f'disponible {_fmt(disponible)}, pedido {_fmt(cantidad)}'
        )
    costo = q4(stock.costo_promedio)
    valor_salida = q4(cantidad * costo)
    nuevo_cant = q4(stock.cantidad - cantidad)
    nuevo_valor = q4(stock.valor - valor_salida)
    if nuevo_cant == 0 or nuevo_valor < 0:
        nuevo_valor = q4(0)
    return costo, valor_salida, stock, nuevo_cant, nuevo_valor


def _escribir_salida(
    *,
    stock,
    detalle,
    anio,
    almacen,
    articulo,
    fecha,
    fecha_hora,
    tipo_mov,
    numero_nota,
    cantidad,
    costo,
    valor_salida,
    nuevo_cant,
    nuevo_valor,
):
    Kardex.objects.create(
        anio=anio,
        articulo=articulo,
        almacen=almacen,
        movimiento_detalle=detalle,
        fecha=fecha,
        fecha_hora=fecha_hora,
        tipo_mov=tipo_mov,
        numero_nota=numero_nota,
        cantidad_entrada=0,
        cantidad_salida=cantidad,
        saldo_cantidad=nuevo_cant,
        costo_unit_mov=costo,
        costo_unit_promedio=costo,
        valor_entrada=0,
        valor_salida=valor_salida,
        saldo_valor=nuevo_valor,
        es_revalorizacion=False,
    )
    stock.cantidad = nuevo_cant
    stock.valor = nuevo_valor
    stock.costo_promedio = costo
    stock.ultima_nota = numero_nota
    stock.save(update_fields=['cantidad', 'valor', 'costo_promedio', 'ultima_nota'])


def _aplicar_entrada(
    *,
    anio,
    almacen,
    articulo,
    detalle,
    fecha,
    fecha_hora,
    tipo_mov,
    numero_nota,
    cantidad,
    costo_unitario,
):
    stock = _bloquear_o_crear(anio, almacen, articulo)
    costo_unitario = q4(costo_unitario)
    valor_entrada = q4(cantidad * costo_unitario)
    nuevo_cant = q4(stock.cantidad + cantidad)
    nuevo_valor = q4(stock.valor + valor_entrada)
    promedio = q4(nuevo_valor / nuevo_cant) if nuevo_cant else q4(0)
    Kardex.objects.create(
        anio=anio,
        articulo=articulo,
        almacen=almacen,
        movimiento_detalle=detalle,
        fecha=fecha,
        fecha_hora=fecha_hora,
        tipo_mov=tipo_mov,
        numero_nota=numero_nota,
        cantidad_entrada=cantidad,
        cantidad_salida=0,
        saldo_cantidad=nuevo_cant,
        costo_unit_mov=costo_unitario,
        costo_unit_promedio=promedio,
        valor_entrada=valor_entrada,
        valor_salida=0,
        saldo_valor=nuevo_valor,
        es_revalorizacion=False,
    )
    stock.cantidad = nuevo_cant
    stock.valor = nuevo_valor
    stock.costo_promedio = promedio
    stock.ultima_nota = numero_nota
    stock.save(update_fields=['cantidad', 'valor', 'costo_promedio', 'ultima_nota'])


def _consulta_stock(anio, almacen, articulo):
    consulta = StockActual.objects.filter(anio=anio, almacen=almacen, articulo=articulo)
    if connection.features.has_select_for_update:
        consulta = consulta.select_for_update()
    return consulta


def _bloquear_stock(anio, almacen, articulo):
    stock = _consulta_stock(anio, almacen, articulo).first()
    if stock is not None:
        return stock
    ultimo = (
        Kardex.objects.filter(anio=anio, almacen=almacen, articulo=articulo)
        .order_by('-fecha', '-id')
        .first()
    )
    if ultimo is None:
        return None
    _crear_cache(anio, almacen, articulo, ultimo)
    return _consulta_stock(anio, almacen, articulo).first()


def _bloquear_o_crear(anio, almacen, articulo):
    stock = _bloquear_stock(anio, almacen, articulo)
    if stock is not None:
        return stock
    _crear_cache(anio, almacen, articulo, None)
    return _consulta_stock(anio, almacen, articulo).get()


def _crear_cache(anio, almacen, articulo, ultimo):
    datos = {
        'cantidad': ultimo.saldo_cantidad if ultimo else q4(0),
        'costo_promedio': ultimo.costo_unit_promedio if ultimo else q4(0),
        'valor': ultimo.saldo_valor if ultimo else q4(0),
        'ultima_nota': ultimo.numero_nota if ultimo else '',
    }
    try:
        with transaction.atomic():
            StockActual.objects.create(anio=anio, almacen=almacen, articulo=articulo, **datos)
    except IntegrityError:
        return
