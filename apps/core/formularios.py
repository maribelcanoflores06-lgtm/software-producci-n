from django import forms

from apps.core.numeros import q4


class MontoField(forms.DecimalField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_digits', 14)
        kwargs.setdefault('decimal_places', 4)
        kwargs.setdefault('localize', False)
        kwargs.setdefault('widget', forms.TextInput(attrs={'inputmode': 'decimal'}))
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            texto = value.strip().replace(' ', '')
            if ',' in texto and '.' in texto:
                texto = texto.replace('.', '').replace(',', '.')
            else:
                texto = texto.replace(',', '.')
            value = texto
        valor = super().to_python(value)
        if valor is None:
            return None
        return q4(valor)


class DenseForm(forms.ModelForm):
    def __init__(self, *args, solo_lectura=False, **kwargs):
        self.solo_lectura = solo_lectura
        super().__init__(*args, **kwargs)
        if solo_lectura:
            for field in self.fields.values():
                field.disabled = True
