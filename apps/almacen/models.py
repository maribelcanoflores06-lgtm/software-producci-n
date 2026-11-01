from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.maestros.models import Decimal4


class Movimiento(models.Model):
    """Cabecera de nota. La fase 1 graba SALDO_INICIAL.
    La orden de producción se enlaza cuando exista esa pantalla.
    """

    INGRESO = 'INGRESO'
    SALIDA = 'SALIDA'
    TRANSFERENCIA = 'TRANSFERENCIA'
    SALIDA_PROD = 'SALIDA_PROD'
    ENTRADA_PROD = 'ENTRADA_PROD'
    SALDO_INICIAL = 'SALDO_INICIAL'
    TIPOS = [
        (INGRESO, 'Ingreso'),
        (SALIDA, 'Salida'),
        (TRANSFERENCIA, 'Transferencia'),
        (SALIDA_PROD, 'Salida a producción'),
        (ENTRADA_PROD, 'Entrada de producción'),
        (SALDO_INICIAL, 'Saldo inicial'),
    ]
    SUBTIPOS = [
        ('COMPRA_NAC', 'Compra nacional'),
        ('IMPORTACION', 'Importación'),
        ('MUESTRAS', 'Muestras'),
        ('OTROS', 'Otros'),
    ]

    numero_nota = models.CharField('Nota', max_length=40, unique=True)
    anio = models.ForeignKey('maestros.Anio', on_delete=models.PROTECT, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    subtipo = models.CharField(max_length=20, choices=SUBTIPOS, null=True, blank=True)
    fecha = models.DateField()
    fecha_hora = models.DateTimeField(default=timezone.now)
    almacen = models.ForeignKey(
        'maestros.Almacen',
        on_delete=models.PROTECT,
        related_name='movimientos_correlativo',
    )
    almacen_origen = models.ForeignKey(
        'maestros.Almacen',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='movimientos_origen',
    )
    almacen_destino = models.ForeignKey(
        'maestros.Almacen',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='movimientos_destino',
    )
    proveedor = models.ForeignKey(
        'maestros.Proveedor',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    cliente = models.ForeignKey(
        'maestros.Cliente',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='movimientos',
    )
    tipo_comprobante = models.CharField(max_length=20, blank=True)
    serie_doc = models.CharField(max_length=20, blank=True)
    numero_doc = models.CharField(max_length=30, blank=True)
    fecha_doc = models.DateField(null=True, blank=True)
    observacion = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='movimientos_creados',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimiento'
        ordering = ['fecha', 'id']
        indexes = [
            models.Index(fields=['anio', 'fecha'], name='movimiento_anio_fecha'),
            models.Index(fields=['tipo'], name='movimiento_tipo'),
            models.Index(fields=['almacen'], name='movimiento_almacen'),
        ]

    def __str__(self):
        return self.numero_nota


class MovimientoDetalle(models.Model):
    movimiento = models.ForeignKey(Movimiento, on_delete=models.CASCADE, related_name='detalles')
    articulo = models.ForeignKey('maestros.Articulo', on_delete=models.PROTECT, related_name='movimiento_detalles')
    cantidad = Decimal4()
    costo_unitario = Decimal4()
    costo_total = Decimal4()
    lote_ref = models.CharField(max_length=40, blank=True)
    ubicacion_ref = models.CharField(max_length=40, blank=True)
    kilo_ref = Decimal4(null=True, blank=True)
    und_ref = Decimal4(null=True, blank=True)
    metro_ref = Decimal4(null=True, blank=True)
    observacion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'movimiento_detalle'

    def __str__(self):
        return f'{self.movimiento.numero_nota} · {self.articulo.codigo}'


class Kardex(models.Model):
    anio = models.ForeignKey('maestros.Anio', on_delete=models.PROTECT, related_name='kardex')
    articulo = models.ForeignKey('maestros.Articulo', on_delete=models.PROTECT, related_name='kardex')
    almacen = models.ForeignKey('maestros.Almacen', on_delete=models.PROTECT, related_name='kardex')
    movimiento_detalle = models.ForeignKey(
        MovimientoDetalle,
        on_delete=models.PROTECT,
        related_name='kardex',
    )
    fecha = models.DateField()
    fecha_hora = models.DateTimeField(default=timezone.now)
    tipo_mov = models.CharField(max_length=20)
    numero_nota = models.CharField(max_length=40)
    cantidad_entrada = Decimal4(default=0)
    cantidad_salida = Decimal4(default=0)
    saldo_cantidad = Decimal4()
    costo_unit_mov = Decimal4()
    costo_unit_promedio = Decimal4()
    valor_entrada = Decimal4(default=0)
    valor_salida = Decimal4(default=0)
    saldo_valor = Decimal4()
    es_revalorizacion = models.BooleanField(default=False)

    class Meta:
        db_table = 'kardex'
        ordering = ['fecha', 'id']
        indexes = [
            models.Index(
                fields=['articulo', 'almacen', 'anio', 'fecha', 'id'],
                name='kardex_stock_idx',
            ),
        ]

    def __str__(self):
        return f'{self.numero_nota} · {self.articulo.codigo}'


class StockActual(models.Model):
    articulo = models.ForeignKey('maestros.Articulo', on_delete=models.PROTECT, related_name='stocks')
    almacen = models.ForeignKey('maestros.Almacen', on_delete=models.PROTECT, related_name='stocks')
    anio = models.ForeignKey('maestros.Anio', on_delete=models.PROTECT, related_name='stocks')
    cantidad = Decimal4()
    costo_promedio = Decimal4()
    valor = Decimal4()
    ultima_nota = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = 'stock_actual'
        constraints = [
            models.UniqueConstraint(
                fields=['articulo', 'almacen', 'anio'],
                name='stock_actual_unico',
            ),
        ]

    def __str__(self):
        return f'{self.anio.anio} {self.almacen.codigo} {self.articulo.codigo}'
