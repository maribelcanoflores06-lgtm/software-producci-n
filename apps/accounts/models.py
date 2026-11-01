from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models


class Rol(models.Model):
    codigo = models.CharField(
        'Código',
        max_length=32,
        unique=True,
        error_messages={'unique': 'Ya existe un rol con este código.'},
    )
    nombre = models.CharField('Nombre', max_length=100)
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        db_table = 'rol'
        ordering = ['nombre']
        verbose_name = 'rol'
        verbose_name_plural = 'roles'

    def __str__(self):
        return self.nombre


class Pantalla(models.Model):
    codigo = models.CharField('Código', max_length=64, unique=True)
    nombre = models.CharField('Nombre', max_length=120)
    modulo = models.CharField('Módulo', max_length=40)

    class Meta:
        db_table = 'pantalla'
        ordering = ['modulo', 'nombre']
        verbose_name = 'pantalla'
        verbose_name_plural = 'pantallas'

    def __str__(self):
        return f'{self.modulo} · {self.nombre}'


class RolPantalla(models.Model):
    """`puede_escribir` distingue la lectura de artículos y almacenes del almacenero,
    y el acceso solo GET del rol Consulta. La spec fija la pareja rol-pantalla;
    el flag guarda esa diferencia de la semilla.
    """

    rol = models.ForeignKey(Rol, on_delete=models.CASCADE, related_name='pantallas')
    pantalla = models.ForeignKey(Pantalla, on_delete=models.CASCADE, related_name='roles')
    puede_escribir = models.BooleanField('Puede modificar', default=True)

    class Meta:
        db_table = 'rol_pantalla'
        constraints = [
            models.UniqueConstraint(fields=['rol', 'pantalla'], name='rol_pantalla_unica'),
        ]

    def __str__(self):
        modo = 'modifica' if self.puede_escribir else 'consulta'
        return f'{self.rol.codigo} · {self.pantalla.codigo} ({modo})'


class UsuarioManager(UserManager):
    def create_user(self, username, email=None, password=None, **extra):
        if not extra.get('rol'):
            raise ValueError('El usuario requiere un rol.')
        return super().create_user(username, email, password, **extra)

    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_active', True)
        extra.setdefault('nombres', username)
        if not extra.get('rol'):
            rol, _ = Rol.objects.get_or_create(
                codigo='ADMIN',
                defaults={'nombre': 'Admin', 'activo': True},
            )
            extra['rol'] = rol
        return self.create_user(username, email, password, **extra)


class Usuario(AbstractUser):
    username = models.CharField(
        'Usuario',
        max_length=150,
        unique=True,
        validators=[UnicodeUsernameValidator()],
        error_messages={'unique': 'Ese usuario ya existe.'},
    )
    nombres = models.CharField('Nombres', max_length=150)
    rol = models.ForeignKey(Rol, verbose_name='Rol', on_delete=models.PROTECT, related_name='usuarios')

    objects = UsuarioManager()
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'usuario'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'
        ordering = ['username']

    def save(self, *args, **kwargs):
        if self.nombres:
            self.first_name = self.nombres[:150]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombres or self.username
