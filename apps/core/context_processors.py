from apps.accounts.models import RolPantalla
from apps.core.catalogo import PANTALLAS, PANTALLAS_POR_CODIGO
from apps.maestros.models import Anio


def shell(request):
    usuario = getattr(request, 'user', None)
    vinculos = {}
    if (
        usuario is not None
        and usuario.is_authenticated
        and usuario.is_active
        and getattr(usuario, 'rol_id', None)
        and usuario.rol.activo
    ):
        vinculos = {
            fila.pantalla.codigo: fila.puede_escribir
            for fila in RolPantalla.objects.filter(rol_id=usuario.rol_id).select_related('pantalla')
        }

    codigo = getattr(request, 'pantalla_codigo', None)
    grupos = []
    for pantalla in PANTALLAS:
        if pantalla['codigo'] not in vinculos:
            continue
        if not grupos or grupos[-1]['modulo'] != pantalla['modulo']:
            grupos.append({'modulo': pantalla['modulo'], 'items': []})
        grupos[-1]['items'].append(pantalla)

    anio = None
    if usuario is not None and usuario.is_authenticated:
        anio = Anio.objects.filter(activo=True).order_by('-anio').first()

    return {
        'menu_grupos': grupos,
        'pantalla_actual': PANTALLAS_POR_CODIGO.get(codigo),
        'puede_escribir': bool(codigo) and bool(vinculos.get(codigo, False)),
        'puede_datos_ejemplo': bool(vinculos.get('admin.anios', False)),
        'anio_trabajo': anio,
    }
