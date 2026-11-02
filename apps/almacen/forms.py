from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory

from apps.almacen.models import Movimiento
from apps.core.formularios import MontoField
from apps.maestros.models import Almacen, Anio, Articulo, Cliente, Proveedor

def _fecha():
    return forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})

COMPROBANTES = [
    ('', '—'),
    ('FACTURA', 'Factura'),
    ('BOLETA', 'Boleta'),
    ('OTROS', 'Otros'),
]


class _CabeceraNota(forms.Form):
    anio = forms.ModelChoiceField(queryset=Anio.objects.none(), label='Año')
    fecha = forms.DateField(label='F. registro', widget=_fecha())
    tipo_comprobante = forms.ChoiceField(
        label='Tipo comprobante',
        required=False,
        choices=COMPROBANTES,
    )
    serie_doc = forms.CharField(label='Serie doc. ref.', required=False, max_length=20)
    numero_doc = forms.CharField(label='Número', required=False, max_length=30)
    fecha_doc = forms.DateField(label='Fecha doc. ref.', required=False, widget=_fecha())
    observacion = forms.CharField(label='Obs.', required=False, widget=forms.TextInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['anio'].queryset = Anio.objects.filter(cerrado=False).order_by('-anio')
        self.fields['anio'].empty_label = None

    def clean_observacion(self):
        return (self.cleaned_data.get('observacion') or '').strip()


class IngresoForm(_CabeceraNota):
    subtipo = forms.ChoiceField(label='Tipo de operación', choices=Movimiento.SUBTIPOS)
    almacen_destino = forms.ModelChoiceField(
        queryset=Almacen.objects.none(),
        label='Almacén',
        empty_label='—',
    )
    proveedor = forms.ModelChoiceField(
        queryset=Proveedor.objects.none(),
        label='Proveedor',
        empty_label='—',
        error_messages={'required': 'El ingreso exige un proveedor.'},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['almacen_destino'].queryset = _almacenes_normales()
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True).order_by('codigo')
        self.order_fields([
            'almacen_destino', 'anio', 'fecha', 'subtipo', 'proveedor',
            'tipo_comprobante', 'serie_doc', 'numero_doc', 'fecha_doc', 'observacion',
        ])


class SalidaForm(_CabeceraNota):
    almacen_origen = forms.ModelChoiceField(
        queryset=Almacen.objects.none(),
        label='Almacén',
        empty_label='—',
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.none(),
        label='Cliente',
        required=False,
        empty_label='—',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['almacen_origen'].queryset = _almacenes_normales()
        self.fields['cliente'].queryset = Cliente.objects.filter(activo=True).order_by('codigo')
        self.order_fields([
            'almacen_origen', 'anio', 'fecha', 'cliente',
            'tipo_comprobante', 'serie_doc', 'numero_doc', 'fecha_doc', 'observacion',
        ])


class TransferenciaForm(_CabeceraNota):
    almacen_origen = forms.ModelChoiceField(
        queryset=Almacen.objects.none(),
        label='Almacén origen',
        empty_label='—',
    )
    almacen_destino = forms.ModelChoiceField(
        queryset=Almacen.objects.none(),
        label='Almacén destino',
        empty_label='—',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        normales = _almacenes_normales()
        self.fields['almacen_origen'].queryset = normales
        self.fields['almacen_destino'].queryset = normales
        self.order_fields([
            'anio', 'fecha', 'almacen_origen', 'almacen_destino',
            'tipo_comprobante', 'serie_doc', 'numero_doc', 'fecha_doc', 'observacion',
        ])

    def clean(self):
        data = super().clean()
        origen = data.get('almacen_origen')
        destino = data.get('almacen_destino')
        if origen and destino and origen.pk == destino.pk:
            self.add_error('almacen_destino', 'El almacén de origen y el de destino deben ser distintos.')
        return data


class LineaForm(forms.Form):
    articulo = forms.ModelChoiceField(
        queryset=Articulo.objects.none(),
        label='Artículo',
        required=False,
        empty_label='—',
    )
    cantidad = MontoField(label='Cantidad', required=False)
    costo_unitario = MontoField(label='Costo unit. S/', required=False)
    lote_ref = forms.CharField(label='Lote', required=False, max_length=40)
    ubicacion_ref = forms.CharField(label='Ubicación', required=False, max_length=40)
    observacion = forms.CharField(label='Obs.', required=False, max_length=200)

    def __init__(self, *args, con_costo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.con_costo = con_costo
        self.fields['articulo'].queryset = Articulo.objects.filter(activo=True).order_by('codigo')
        if not con_costo:
            self.fields.pop('costo_unitario')

    def clean(self):
        data = super().clean()
        if data.get('DELETE'):
            return data
        articulo = data.get('articulo')
        cantidad = data.get('cantidad')
        costo = data.get('costo_unitario') if self.con_costo else None
        lote = (data.get('lote_ref') or '').strip()
        ubicacion = (data.get('ubicacion_ref') or '').strip()
        obs = (data.get('observacion') or '').strip()
        vacia = articulo is None and cantidad in (None, '') and costo in (None, '') and not lote and not ubicacion and not obs
        if vacia:
            return data
        if articulo is None:
            self.add_error('articulo', 'Seleccione un artículo.')
        if cantidad is None or cantidad <= 0:
            self.add_error('cantidad', 'La cantidad debe ser mayor que cero.')
        if self.con_costo and (costo is None or costo <= 0):
            self.add_error('costo_unitario', 'El costo unitario debe ser mayor que cero.')
        data['lote_ref'] = lote
        data['ubicacion_ref'] = ubicacion
        data['observacion'] = obs
        return data


class LineasFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        completas = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', None) or {}
            if not data or data.get('DELETE'):
                continue
            if not data.get('articulo'):
                continue
            completas += 1
        if completas < 1:
            raise ValidationError('Agregue al menos una línea.')


def formset_lineas(data=None, con_costo=False):
    Formulario = formset_factory(
        LineaForm,
        formset=LineasFormSet,
        extra=1,
        can_delete=True,
    )
    return Formulario(data, prefix='lineas', form_kwargs={'con_costo': con_costo})


def lineas_de_formset(formset):
    lineas = []
    for form in formset.forms:
        data = getattr(form, 'cleaned_data', None) or {}
        if not data or data.get('DELETE') or not data.get('articulo'):
            continue
        linea = {
            'articulo': data['articulo'],
            'cantidad': data.get('cantidad'),
            'lote_ref': data.get('lote_ref') or '',
            'ubicacion_ref': data.get('ubicacion_ref') or '',
            'observacion': data.get('observacion') or '',
        }
        if 'costo_unitario' in data:
            linea['costo_unitario'] = data.get('costo_unitario')
        lineas.append(linea)
    return lineas


def _almacenes_normales():
    return Almacen.objects.filter(activo=True, es_proceso=False).order_by('codigo')
