from django.shortcuts import render

from apps.core.catalogo import PANTALLAS_POR_CODIGO

RUTAS_SIN_PANTALLA = {'home', 'login', 'logout', 'favicon'}
MENSAJE_DENEGADO = 'No tienes permiso para esta acción.'
METODOS_LECTURA = {'GET', 'HEAD', 'OPTIONS'}


def codigo_de_vista(func):
    codigo = getattr(func, 'pantalla_codigo', None)
    if codigo:
        return codigo
    clase = getattr(func, 'view_class', None)
    if clase is not None:
        return getattr(clase, 'pantalla_codigo', None)
    return None


def puede(usuario, codigo, escribir=False):
    if not getattr(usuario, 'is_authenticated', False) or not usuario.is_active:
        return False
    if not getattr(usuario, 'rol_id', None):
        return False
    rol = usuario.rol
    if rol is None or not rol.activo:
        return False
    from apps.accounts.models import RolPantalla

    vinculo = (
        RolPantalla.objects.filter(rol_id=rol.id, pantalla__codigo=codigo)
        .only('puede_escribir')
        .first()
    )
    if vinculo is None:
        return False
    if escribir and not vinculo.puede_escribir:
        return False
    return True


def respuesta_denegada(request):
    codigo = getattr(request, 'pantalla_codigo', None)
    return render(
        request,
        '403.html',
        {
            'mensaje': MENSAJE_DENEGADO,
            'pantalla_denegada': PANTALLAS_POR_CODIGO.get(codigo),
        },
        status=403,
    )
