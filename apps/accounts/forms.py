from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorModelo

from apps.accounts.models import Rol, Usuario
from apps.core.codigos import normalizar_codigo
from apps.core.formularios import DenseForm


class AccesoForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Usuario o contraseña incorrectos.',
        'inactive': 'Usuario o contraseña incorrectos.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario'
        self.fields['password'].label = 'Contraseña'
        self.fields['username'].widget.attrs.update({
            'autofocus': True,
            'autocomplete': 'username',
        })
        self.fields['password'].widget.attrs.update({'autocomplete': 'current-password'})


class UsuarioForm(DenseForm):
    password1 = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Usuario
        fields = ['username', 'nombres', 'email', 'rol', 'is_active']
        labels = {
            'username': 'Usuario',
            'nombres': 'Nombres',
            'email': 'Correo',
            'rol': 'Rol',
            'is_active': 'Activo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].queryset = Rol.objects.order_by('nombre')
        self.fields['email'].required = False
        if self.instance.pk:
            self.fields['password1'].help_text = 'Déjela en blanco para mantener la actual.'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['password1'].help_text = 'Mínimo 8 caracteres.'

    def clean_username(self):
        return (self.cleaned_data.get('username') or '').strip()

    def clean_nombres(self):
        nombres = (self.cleaned_data.get('nombres') or '').strip()
        if not nombres:
            raise forms.ValidationError('Los nombres son obligatorios.')
        return nombres

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if not self.instance.pk and not p1:
            self.add_error('password1', 'La contraseña es obligatoria al crear el usuario.')
        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            else:
                try:
                    validate_password(p1, self.instance)
                except ErrorModelo as exc:
                    self.add_error('password1', list(exc.messages))

        rol = cleaned.get('rol')
        activo = cleaned.get('is_active')
        admin = Rol.objects.filter(codigo='ADMIN').first()
        if admin:
            sigue_admin = bool(activo and rol and rol.pk == admin.pk)
            otros = Usuario.objects.filter(rol=admin, is_active=True)
            if self.instance.pk:
                otros = otros.exclude(pk=self.instance.pk)
            if not sigue_admin and not otros.exists():
                raise forms.ValidationError('Debe quedar al menos un usuario Admin activo.')
        return cleaned

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('password1'):
            usuario.set_password(self.cleaned_data['password1'])
        if commit:
            usuario.save()
        return usuario


class RolForm(DenseForm):
    class Meta:
        model = Rol
        fields = ['codigo', 'nombre', 'activo']
        labels = {'codigo': 'Código', 'nombre': 'Nombre', 'activo': 'Activo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.codigo == 'ADMIN':
            self.fields['codigo'].disabled = True
            self.fields['activo'].disabled = True
            self.fields['codigo'].help_text = 'El código del rol Admin queda fijo.'

    def clean_codigo(self):
        if self.instance.pk and self.instance.codigo == 'ADMIN':
            return 'ADMIN'
        try:
            return normalizar_codigo(self.cleaned_data.get('codigo', ''))
        except ErrorModelo as exc:
            raise forms.ValidationError(list(exc.messages))

    def clean_nombre(self):
        nombre = (self.cleaned_data.get('nombre') or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre es obligatorio.')
        return nombre

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.codigo == 'ADMIN':
            cleaned['activo'] = True
        return cleaned
