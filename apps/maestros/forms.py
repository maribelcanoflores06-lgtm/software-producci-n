from django import forms
from django.core.exceptions import ValidationError as ErrorModelo
from django.db.models import Q
from django.forms.models import BaseInlineFormSet

from apps.almacen.models import Movimiento, MovimientoDetalle
from apps.core.codigos import MENSAJE_ALMACEN, MENSAJE_CODIGO, PATRON_ALMACEN, PATRON_CODIGO, normalizar_codigo
from apps.core.formularios import DenseForm, MontoField
from apps.core.numeros import q4
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    Cliente,
    Proceso,
    Proveedor,
    Receta,
    RecetaDetalle,
    Ruta,
    RutaProceso,
    TipoMaterial,
    Trabajador,
)


class CodigoForm(DenseForm):
    patron = PATRON_CODIGO
    mensaje = MENSAJE_CODIGO

    def clean_codigo(self):
        try:
            return normalizar_codigo(self.cleaned_data.get('codigo', ''), self.patron, self.mensaje)
        except ErrorModelo as exc:
            raise forms.ValidationError(list(exc.messages))


class ArticuloForm(CodigoForm):
    class Meta:
        model = Articulo
        fields = ['codigo', 'descripcion', 'tipo_material', 'unidad_medida', 'activo']
        help_texts = {
            'unidad_medida': 'Por ejemplo: kg, m, und, cono.',
            'tipo_material': 'Si el tipo es producto terminado, después cree su receta por lote base.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_material'].queryset = TipoMaterial.objects.order_by('codigo')
        if self.instance.pk and MovimientoDetalle.objects.filter(articulo=self.instance).exists():
            self.fields['codigo'].disabled = True
            self.fields['codigo'].help_text = 'El código queda fijo porque el artículo ya tiene movimientos.'


class ClienteForm(CodigoForm):
    class Meta:
        model = Cliente
        fields = ['codigo', 'ruc_documento', 'razon_social', 'direccion', 'telefono', 'activo']


class ProveedorForm(CodigoForm):
    class Meta:
        model = Proveedor
        fields = ['codigo', 'ruc_documento', 'razon_social', 'direccion', 'telefono', 'activo']


class TrabajadorForm(CodigoForm):
    class Meta:
        model = Trabajador
        fields = ['codigo', 'nombres', 'tipo_documento', 'numero_documento', 'activo']


class AlmacenForm(CodigoForm):
    patron = PATRON_ALMACEN
    mensaje = MENSAJE_ALMACEN

    class Meta:
        model = Almacen
        fields = ['codigo', 'nombre', 'es_proceso', 'activo']
        help_texts = {
            'codigo': 'Forma parte del número de nota: CODIGO-AÑO-CORRELATIVO.',
            'es_proceso': 'Un almacén de proceso solo participa en salida y entrada de producción.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and Movimiento.objects.filter(almacen=self.instance).exists():
            self.fields['codigo'].disabled = True


class ProcesoForm(CodigoForm):
    class Meta:
        model = Proceso
        fields = ['codigo', 'nombre', 'activo']


class AnioForm(DenseForm):
    class Meta:
        model = Anio
        fields = ['anio', 'activo']
        labels = {'anio': 'Año', 'activo': 'Año de trabajo'}
        help_texts = {
            'activo': 'Al marcarlo, los demás años dejan de ser el año de trabajo.',
        }

    def clean_anio(self):
        valor = self.cleaned_data.get('anio')
        if valor is None or valor < 1990 or valor > 2200:
            raise forms.ValidationError('Indique un año entre 1990 y 2200.')
        return valor


class AnioChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        marcas = []
        if obj.activo:
            marcas.append('activo')
        if obj.cerrado:
            marcas.append('cerrado')
        extra = f" ({', '.join(marcas)})" if marcas else ''
        return f'{obj.anio}{extra}'


class SaldoInicialForm(forms.Form):
    anio = AnioChoice(queryset=Anio.objects.none(), label='Año')
    almacen = forms.ModelChoiceField(queryset=Almacen.objects.none(), label='Almacén')
    articulo = forms.ModelChoiceField(queryset=Articulo.objects.none(), label='Artículo')
    cantidad = MontoField(label='Cantidad')
    costo_unitario = MontoField(label='Costo unitario (S/)')

    def __init__(self, *args, solo_lectura=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['anio'].queryset = Anio.objects.order_by('-anio')
        self.fields['almacen'].queryset = Almacen.objects.filter(activo=True).order_by('codigo')
        self.fields['articulo'].queryset = (
            Articulo.objects.filter(activo=True).select_related('tipo_material').order_by('codigo')
        )
        activo = Anio.objects.filter(activo=True, cerrado=False).first()
        if activo and not self.is_bound:
            self.fields['anio'].initial = activo.pk
        if solo_lectura:
            for field in self.fields.values():
                field.disabled = True

    def clean_anio(self):
        anio = self.cleaned_data.get('anio')
        if anio and anio.cerrado:
            raise forms.ValidationError('El año está cerrado y no admite movimientos.')
        return anio

    def clean_cantidad(self):
        valor = self.cleaned_data.get('cantidad')
        if valor is None or valor <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return valor

    def clean_costo_unitario(self):
        valor = self.cleaned_data.get('costo_unitario')
        if valor is None or valor < 0:
            raise forms.ValidationError('El costo unitario no puede ser negativo.')
        return valor


class RecetaForm(DenseForm):
    lote_base = MontoField(
        label='Lote base',
        help_text='Cantidad de producto a la que corresponden los insumos (ej. 100).',
    )

    class Meta:
        model = Receta
        fields = ['articulo_pt', 'lote_base', 'activo']
        labels = {'articulo_pt': 'Producto terminado', 'activo': 'Activo'}
        help_texts = {
            'articulo_pt': 'Solo productos terminados que todavía no tienen receta.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ocupados = Receta.objects.all()
        if self.instance.pk:
            ocupados = ocupados.exclude(pk=self.instance.pk)
        ids = list(ocupados.values_list('articulo_pt_id', flat=True))
        qs = Articulo.objects.filter(tipo_material__codigo='PT').exclude(pk__in=ids)
        if self.instance.pk:
            qs = qs.filter(Q(activo=True) | Q(pk=self.instance.articulo_pt_id))
        else:
            qs = qs.filter(activo=True)
        self.fields['articulo_pt'].queryset = qs.order_by('codigo')

    def clean_lote_base(self):
        valor = self.cleaned_data.get('lote_base')
        if valor is None or valor <= 0:
            raise forms.ValidationError('El lote base debe ser mayor que cero.')
        return q4(valor)

    def clean_articulo_pt(self):
        articulo = self.cleaned_data.get('articulo_pt')
        if articulo and articulo.tipo_material.codigo != 'PT':
            raise forms.ValidationError('La receta es solo para un producto terminado.')
        return articulo


class RecetaLineaForm(forms.ModelForm):
    cantidad_por_lote = MontoField(label='Cantidad por lote')

    class Meta:
        model = RecetaDetalle
        fields = ['articulo_insumo', 'cantidad_por_lote']
        labels = {'articulo_insumo': 'Insumo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Articulo.objects.filter(activo=True)
        if self.instance.pk and self.instance.articulo_insumo_id:
            qs = Articulo.objects.filter(Q(activo=True) | Q(pk=self.instance.articulo_insumo_id))
        self.fields['articulo_insumo'].queryset = qs.order_by('codigo')
        self.fields['articulo_insumo'].empty_label = '—'

    def clean_cantidad_por_lote(self):
        valor = self.cleaned_data.get('cantidad_por_lote')
        if valor is None:
            return valor
        if valor <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return q4(valor)


class RecetaLineasFormSet(BaseInlineFormSet):
    pt_id = None

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        vistos = set()
        completas = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None) or {}
            if not data or data.get('DELETE'):
                continue
            insumo = data.get('articulo_insumo')
            cantidad = data.get('cantidad_por_lote')
            if insumo is None and not cantidad:
                continue
            if insumo is None or not cantidad:
                raise ErrorModelo('Complete insumo y cantidad en cada línea.')
            if self.pt_id and insumo.pk == int(self.pt_id):
                raise ErrorModelo('El insumo no puede ser el mismo producto terminado de la receta.')
            if insumo.pk in vistos:
                raise ErrorModelo(f'El insumo {insumo.codigo} está repetido.')
            vistos.add(insumo.pk)
            completas += 1
        if completas < 1:
            raise ErrorModelo('La receta debe tener al menos un insumo.')


class RutaForm(CodigoForm):
    class Meta:
        model = Ruta
        fields = ['codigo', 'nombre', 'activo']
        help_texts = {
            'nombre': 'La ruta no se ata al producto. Se elige al crear la orden de producción.',
        }


class RutaLineaForm(forms.ModelForm):
    class Meta:
        model = RutaProceso
        fields = ['secuencia', 'proceso']
        labels = {'secuencia': 'Secuencia', 'proceso': 'Proceso'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Proceso.objects.filter(activo=True)
        if self.instance.pk and self.instance.proceso_id:
            qs = Proceso.objects.filter(Q(activo=True) | Q(pk=self.instance.proceso_id))
        self.fields['proceso'].queryset = qs.order_by('codigo')
        self.fields['proceso'].empty_label = '—'
        self.fields['secuencia'].widget.attrs['class'] = 'w80'

    def clean_secuencia(self):
        valor = self.cleaned_data.get('secuencia')
        if valor is not None and valor < 1:
            raise forms.ValidationError('La secuencia empieza en 1.')
        return valor


class RutaLineasFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        secuencias = set()
        completas = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None) or {}
            if not data or data.get('DELETE'):
                continue
            proceso = data.get('proceso')
            secuencia = data.get('secuencia')
            if proceso is None and secuencia is None:
                continue
            if proceso is None or secuencia is None:
                raise ErrorModelo('Complete proceso y secuencia en cada línea.')
            if secuencia < 1:
                raise ErrorModelo('La secuencia empieza en 1.')
            if secuencia in secuencias:
                raise ErrorModelo(f'La secuencia {secuencia} está repetida.')
            secuencias.add(secuencia)
            completas += 1
        if completas < 1:
            raise ErrorModelo('La ruta debe tener al menos un proceso.')
