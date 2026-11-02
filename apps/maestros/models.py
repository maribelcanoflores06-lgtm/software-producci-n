from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.codigos import (
    MENSAJE_ALMACEN,
    MENSAJE_CODIGO,
    PATRON_ALMACEN,
    PATRON_CODIGO,
    normalizar_codigo,
)
from apps.core.numeros import q4


class Decimal4(models.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 14)
        kwargs.setdefault('decimal_places', 4)
        super().__init__(*args, **kwargs)


class Anio(models.Model):
    anio = models.PositiveIntegerField('Año', unique=True)
    activo = models.BooleanField('Año de trabajo', default=False)
    cerrado = models.BooleanField('Cerrado', default=False)
    fecha_cierre = models.DateTimeField('Fecha de cierre', null=True, blank=True)
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Cerrado por',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='anios_cerrados',
    )

    class Meta:
        db_table = 'anio'
        ordering = ['-anio']
        verbose_name = 'año'
        verbose_name_plural = 'años'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.activo:
            type(self).objects.exclude(pk=self.pk).update(activo=False)

    def __str__(self):
        return str(self.anio)


class TipoMaterial(models.Model):
    codigo = models.CharField('Código', max_length=10, unique=True)
    nombre = models.CharField('Nombre', max_length=80)

    class Meta:
        db_table = 'tipo_material'
        ordering = ['codigo']
        verbose_name = 'tipo de material'
        verbose_name_plural = 'tipos de material'

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class Articulo(models.Model):
    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe un artículo con este código.'},
    )
    descripcion = models.CharField('Descripción', max_length=200)
    tipo_material = models.ForeignKey(
        TipoMaterial,
        verbose_name='Tipo',
        on_delete=models.PROTECT,
        related_name='articulos',
    )
    unidad_medida = models.CharField('Unidad de medida', max_length=20)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'articulo'
        ordering = ['codigo']
        verbose_name = 'artículo'
        verbose_name_plural = 'artículos'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.descripcion = (self.descripcion or '').strip()
        self.unidad_medida = (self.unidad_medida or '').strip()
        if not self.descripcion:
            raise ValidationError({'descripcion': 'La descripción es obligatoria.'})
        if not self.unidad_medida:
            raise ValidationError({'unidad_medida': 'La unidad de medida es obligatoria.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.descripcion}'


class Tercero(models.Model):
    codigo = models.CharField('Código', max_length=40, unique=True)
    ruc_documento = models.CharField('RUC / documento', max_length=20, blank=True)
    razon_social = models.CharField('Razón social', max_length=200)
    direccion = models.CharField('Dirección', max_length=250, blank=True)
    telefono = models.CharField('Teléfono', max_length=40, blank=True)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        abstract = True
        ordering = ['codigo']

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.razon_social = (self.razon_social or '').strip()
        self.ruc_documento = (self.ruc_documento or '').strip()
        self.direccion = (self.direccion or '').strip()
        self.telefono = (self.telefono or '').strip()
        if not self.razon_social:
            raise ValidationError({'razon_social': 'La razón social es obligatoria.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.razon_social}'


class Cliente(Tercero):
    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe un cliente con este código.'},
    )

    class Meta:
        db_table = 'cliente'
        ordering = ['codigo']
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'


class Proveedor(Tercero):
    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe un proveedor con este código.'},
    )

    class Meta:
        db_table = 'proveedor'
        ordering = ['codigo']
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'


class Trabajador(models.Model):
    DNI = 'DNI'
    PASAPORTE = 'PASAPORTE'
    OTROS = 'OTROS'
    TIPOS_DOCUMENTO = [
        (DNI, 'DNI'),
        (PASAPORTE, 'Pasaporte'),
        (OTROS, 'Otros'),
    ]

    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe un trabajador con este código.'},
    )
    nombres = models.CharField('Nombres', max_length=150)
    tipo_documento = models.CharField(
        'Tipo de documento',
        max_length=20,
        choices=TIPOS_DOCUMENTO,
        default=DNI,
    )
    numero_documento = models.CharField('Número de documento', max_length=30)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'trabajador'
        ordering = ['codigo']
        verbose_name = 'trabajador'
        verbose_name_plural = 'trabajadores'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.nombres = (self.nombres or '').strip()
        self.numero_documento = (self.numero_documento or '').strip()
        if not self.nombres:
            raise ValidationError({'nombres': 'Los nombres son obligatorios.'})
        if not self.numero_documento:
            raise ValidationError({'numero_documento': 'El número de documento es obligatorio.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.nombres}'


class Almacen(models.Model):
    codigo = models.CharField(
        'Código',
        max_length=20,
        unique=True,
        error_messages={'unique': 'Ya existe un almacén con este código.'},
    )
    nombre = models.CharField('Nombre', max_length=120)
    es_proceso = models.BooleanField('Es proceso', default=False)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'almacen'
        ordering = ['codigo']
        verbose_name = 'almacén'
        verbose_name_plural = 'almacenes'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_ALMACEN, MENSAJE_ALMACEN)
        self.nombre = (self.nombre or '').strip()
        if not self.nombre:
            raise ValidationError({'nombre': 'El nombre es obligatorio.'})
        if self.pk and not self.activo and _almacen_con_stock(self.pk):
            raise ValidationError('No se puede desactivar un almacén con stock mayor a cero.')

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        marca = ' · proceso' if self.es_proceso else ''
        return f'{self.codigo} · {self.nombre}{marca}'


def _almacen_con_stock(almacen_id):
    from django.db.models import Q

    from apps.almacen.models import StockActual

    return StockActual.objects.filter(almacen_id=almacen_id).filter(
        Q(cantidad__gt=0) | Q(valor__gt=0)
    ).exists()


class Proceso(models.Model):
    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe un proceso con este código.'},
    )
    nombre = models.CharField('Nombre', max_length=120)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'proceso'
        ordering = ['codigo']
        verbose_name = 'proceso'
        verbose_name_plural = 'procesos'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.nombre = (self.nombre or '').strip()
        if not self.nombre:
            raise ValidationError({'nombre': 'El nombre es obligatorio.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class Ruta(models.Model):
    """La ruta no se asocia al producto terminado. Se elige al crear la orden."""

    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe una ruta con este código.'},
    )
    nombre = models.CharField('Nombre', max_length=120)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'ruta'
        ordering = ['codigo']
        verbose_name = 'ruta'
        verbose_name_plural = 'rutas'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.nombre = (self.nombre or '').strip()
        if not self.nombre:
            raise ValidationError({'nombre': 'El nombre es obligatorio.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class RutaProceso(models.Model):
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name='pasos')
    proceso = models.ForeignKey(Proceso, on_delete=models.PROTECT, related_name='rutas')
    secuencia = models.PositiveIntegerField('Secuencia')

    class Meta:
        db_table = 'ruta_proceso'
        ordering = ['secuencia', 'id']
        constraints = [
            models.UniqueConstraint(fields=['ruta', 'secuencia'], name='ruta_secuencia_unica'),
        ]

    def __str__(self):
        return f'{self.ruta.codigo} · {self.secuencia} {self.proceso.codigo}'


class Receta(models.Model):
    articulo_pt = models.OneToOneField(
        Articulo,
        verbose_name='Producto terminado',
        on_delete=models.PROTECT,
        related_name='receta',
    )
    lote_base = Decimal4('Lote base')
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'receta'
        verbose_name = 'receta'
        verbose_name_plural = 'recetas'
        constraints = [
            models.CheckConstraint(condition=models.Q(lote_base__gt=0), name='receta_lote_positivo'),
        ]

    def clean(self):
        super().clean()
        if self.lote_base is not None and self.lote_base <= 0:
            raise ValidationError({'lote_base': 'El lote base debe ser mayor que cero.'})
        if self.articulo_pt_id and self.articulo_pt.tipo_material.codigo != 'PT':
            raise ValidationError({'articulo_pt': 'La receta es solo para un producto terminado.'})

    def __str__(self):
        return f'{self.articulo_pt.codigo} · lote {self.lote_base}'


class RecetaDetalle(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='detalles')
    articulo_insumo = models.ForeignKey(
        Articulo,
        verbose_name='Insumo',
        on_delete=models.PROTECT,
        related_name='usos_en_receta',
    )
    cantidad_por_lote = Decimal4('Cantidad por lote')

    class Meta:
        db_table = 'receta_detalle'
        ordering = ['articulo_insumo__codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['receta', 'articulo_insumo'],
                name='receta_insumo_unico',
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_por_lote__gt=0),
                name='receta_detalle_cantidad_positiva',
            ),
        ]

    def clean(self):
        super().clean()
        if self.cantidad_por_lote is not None and self.cantidad_por_lote <= 0:
            raise ValidationError({'cantidad_por_lote': 'La cantidad debe ser mayor que cero.'})
        if self.receta_id and self.articulo_insumo_id == self.receta.articulo_pt_id:
            raise ValidationError('El insumo no puede ser el mismo producto terminado de la receta.')

    def __str__(self):
        return f'{self.articulo_insumo.codigo} · {self.cantidad_por_lote}'


class Maquina(models.Model):
    """Equipo del taller. Los procesos que puede realizar son los del maestro Proceso."""

    codigo = models.CharField(
        'Código',
        max_length=40,
        unique=True,
        error_messages={'unique': 'Ya existe una máquina con este código.'},
    )
    nombre = models.CharField('Nombre', max_length=120)
    descripcion = models.CharField('Descripción', max_length=250, blank=True)
    activo = models.BooleanField('Activo', default=True)
    procesos = models.ManyToManyField(
        Proceso,
        through='MaquinaProceso',
        related_name='maquinas',
        verbose_name='Procesos',
    )

    class Meta:
        db_table = 'maquina'
        ordering = ['codigo']
        verbose_name = 'máquina'
        verbose_name_plural = 'máquinas'

    def clean(self):
        super().clean()
        self.codigo = normalizar_codigo(self.codigo, PATRON_CODIGO, MENSAJE_CODIGO)
        self.nombre = (self.nombre or '').strip()
        self.descripcion = (self.descripcion or '').strip()
        if not self.nombre:
            raise ValidationError({'nombre': 'El nombre es obligatorio.'})

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.codigo} · {self.nombre}'


class MaquinaProceso(models.Model):
    maquina = models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name='asignaciones')
    proceso = models.ForeignKey(
        Proceso,
        verbose_name='Proceso',
        on_delete=models.PROTECT,
        related_name='usos_en_maquina',
    )

    class Meta:
        db_table = 'maquina_proceso'
        ordering = ['proceso__codigo', 'id']
        constraints = [
            models.UniqueConstraint(fields=['maquina', 'proceso'], name='maquina_proceso_unico'),
        ]

    def __str__(self):
        return f'{self.maquina.codigo} · {self.proceso.codigo}'


class CorrelativoNota(models.Model):
    anio = models.ForeignKey(Anio, on_delete=models.PROTECT, related_name='correlativos_nota')
    almacen = models.ForeignKey('maestros.Almacen', on_delete=models.PROTECT, related_name='correlativos_nota')
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'correlativo_nota'
        constraints = [
            models.UniqueConstraint(fields=['anio', 'almacen'], name='correlativo_nota_unico'),
        ]

    def __str__(self):
        return f'{self.almacen.codigo}-{self.anio.anio}-{self.ultimo:06d}'


class CorrelativoOp(models.Model):
    anio = models.OneToOneField(Anio, on_delete=models.PROTECT, related_name='correlativo_op')
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'correlativo_op'

    def __str__(self):
        return f'OP-{self.anio.anio}-{self.ultimo:04d}'


class SaldoInicial(models.Model):
    anio = models.ForeignKey(Anio, on_delete=models.PROTECT, related_name='saldos_iniciales')
    almacen = models.ForeignKey(Almacen, on_delete=models.PROTECT, related_name='saldos_iniciales')
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT, related_name='saldos_iniciales')
    cantidad = Decimal4()
    costo_promedio = Decimal4()
    valor = Decimal4()

    class Meta:
        db_table = 'saldo_inicial'
        constraints = [
            models.UniqueConstraint(
                fields=['anio', 'almacen', 'articulo'],
                name='saldo_inicial_unico',
            ),
            models.CheckConstraint(condition=models.Q(cantidad__gte=0), name='saldo_inicial_cant_no_neg'),
            models.CheckConstraint(condition=models.Q(costo_promedio__gte=0), name='saldo_inicial_costo_no_neg'),
            models.CheckConstraint(condition=models.Q(valor__gte=0), name='saldo_inicial_valor_no_neg'),
        ]
        indexes = [
            models.Index(fields=['anio', 'almacen', 'articulo'], name='saldo_inicial_busqueda'),
        ]

    def clean(self):
        super().clean()
        if self.cantidad is None or self.costo_promedio is None or self.valor is None:
            return
        if self.cantidad < 0 or self.costo_promedio < 0:
            raise ValidationError('La cantidad y el costo del saldo inicial no pueden ser negativos.')
        esperado = q4(self.cantidad * self.costo_promedio)
        if q4(self.valor) != esperado:
            raise ValidationError('El valor debe ser igual a cantidad × costo promedio.')

    def __str__(self):
        return f'{self.anio.anio} {self.almacen.codigo} {self.articulo.codigo}'
