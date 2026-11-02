from decimal import Decimal, InvalidOperation

from django import forms

from apps.core.numeros import formato_cantidad, formato_costo, normalizar_entrada, q4


def opcion_vacia(cosa):
    return f'Seleccionar {cosa}…'


class MontoField(forms.DecimalField):
    """Cantidad (presentacion='cantidad') o costo unitario (presentacion='costo')."""

    def __init__(self, *args, presentacion='cantidad', **kwargs):
        self.presentacion = presentacion
        kwargs.setdefault('max_digits', 14)
        kwargs.setdefault('decimal_places', 4)
        kwargs.setdefault('localize', False)
        widget = kwargs.pop('widget', None) or forms.TextInput()
        widget.attrs.setdefault('inputmode', 'decimal')
        widget.attrs.setdefault('placeholder', '0.0000' if presentacion == 'costo' else '0.00')
        kwargs['widget'] = widget
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = normalizar_entrada(value)
        valor = super().to_python(value)
        if valor is None:
            return None
        return q4(valor)

    def prepare_value(self, value):
        if value in self.empty_values:
            return ''
        try:
            if isinstance(value, str):
                numero = Decimal(normalizar_entrada(value))
            else:
                numero = Decimal(value)
        except (InvalidOperation, ValueError, TypeError):
            return value
        if self.presentacion == 'costo':
            return formato_costo(numero)
        return formato_cantidad(numero)


class DenseForm(forms.ModelForm):
    def __init__(self, *args, solo_lectura=False, **kwargs):
        self.solo_lectura = solo_lectura
        super().__init__(*args, **kwargs)
        if solo_lectura:
            for field in self.fields.values():
                field.disabled = True
