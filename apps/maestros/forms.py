from django import forms
from django.core.exceptions import ValidationError as ErrorModelo
from django.db.models import Q
from django.forms.models import BaseInlineFormSet, ModelChoiceIterator

from apps.almacen.models import Movimiento, MovimientoDetalle
from apps.core.codigos import MENSAJE_ALMACEN, MENSAJE_CODIGO, PATRON_ALMACEN, PATRON_CODIGO, normalizar_codigo
from apps.core.formularios import DenseForm, MontoField
from apps.core.numeros import q4
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    Cliente,
    Maquina,
    MaquinaProceso,
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


class IteradorSinProducto(ModelChoiceIterator):
    """Oculta el producto terminado de la receta sin sacarlo del queryset."""

    def __iter__(self):
        excluido = getattr(self.field, 'producto_excluido', None)
        for valor, etiqueta in super().__iter__():
            if excluido is not None and str(valor) == str(excluido):
                continue
            yield valor, etiqueta


class RecetaLineaForm(forms.ModelForm):
    cantidad_por_lote = MontoField(label='Cantidad por lote')

    class Meta:
        model = RecetaDetalle
        fields = ['articulo_insumo', 'cantidad_por_lote']
        labels = {'articulo_insumo': 'Insumo'}

    def __init__(self, *args, pt_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pt_id = pt_id
        qs = Articulo.objects.filter(activo=True)
        if self.instance.pk and self.instance.articulo_insumo_id:
            qs = Articulo.objects.filter(Q(activo=True) | Q(pk=self.instance.articulo_insumo_id))
        campo = self.fields['articulo_insumo']
        campo.iterator = IteradorSinProducto
        campo.producto_excluido = pt_id
        campo.empty_label = '—'
        campo.queryset = qs.order_by('codigo')

    def clean_cantidad_por_lote(self):
        valor = self.cleaned_data.get('cantidad_por_lote')
        if valor is None:
            return valor
        if valor <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return q4(valor)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned
        insumo = cleaned.get('articulo_insumo')
        if insumo is not None and self.pt_id and insumo.pk == int(self.pt_id):
            self.add_error(
                'articulo_insumo',
                'El insumo no puede ser el mismo producto terminado de la receta.',
            )
        return cleaned


class RecetaLineasFormSet(BaseInlineFormSet):
    def __init__(self, *args, pt_id=None, **kwargs):
        self.pt_id = pt_id
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['pt_id'] = self.pt_id
        return kwargs

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
            'nombre': (
                'No se ata al producto ni a una máquina. En la orden se elige la ruta '
                'y, para cada proceso, una máquina que pueda realizarlo.'
            ),
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


class MaquinaForm(CodigoForm):
    class Meta:
        model = Maquina
        fields = ['codigo', 'nombre', 'descripcion', 'activo']
        help_texts = {
            'descripcion': 'Opcional. Sirve para distinguir el equipo en el taller.',
        }

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre es obligatorio.')
        return nombre


class CampoProcesoMaquina(forms.ModelChoiceField):
    """Muestra código - nombre y solo acepta procesos activos del maestro."""

    def label_from_instance(self, obj):
        return f'{obj.codigo} - {obj.nombre}'

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            proceso = Proceso.objects.get(pk=value)
        except (Proceso.DoesNotExist, ValueError, TypeError):
            raise forms.ValidationError('Seleccione un proceso válido.')
        permitido = getattr(self, 'inactivo_permitido', None)
        if not proceso.activo and proceso.pk != permitido:
            raise forms.ValidationError('Seleccione un proceso activo.')
        return proceso


class MaquinaLineaForm(forms.ModelForm):
    class Meta:
        model = MaquinaProceso
        fields = ['proceso']
        labels = {'proceso': 'Proceso'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actual = self.instance.proceso_id if self.instance.pk else None
        qs = Proceso.objects.filter(Q(activo=True) | Q(pk=actual))
        campo = CampoProcesoMaquina(queryset=qs.order_by('codigo'), label='Proceso', empty_label='—', required=False)
        campo.inactivo_permitido = actual
        self.fields['proceso'] = campo


class MaquinaLineasFormSet(BaseInlineFormSet):
    def validate_unique(self):
        # El mensaje genérico de Django no dice cuál proceso se repitió.
        return

    def clean(self):
        super().clean()
        vistos = set()
        completas = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None) or {}
            if not data or data.get('DELETE'):
                continue
            proceso = data.get('proceso')
            if proceso is None:
                continue
            if not proceso.activo and proceso.pk != getattr(form.instance, 'proceso_id', None):
                raise ErrorModelo('Seleccione un proceso activo.')
            if proceso.pk in vistos:
                raise ErrorModelo(f'El proceso {proceso.codigo} está repetido.')
            vistos.add(proceso.pk)
            completas += 1
        if completas < 1 and not any(self.errors):
            raise ErrorModelo('La máquina debe tener al menos un proceso.')
