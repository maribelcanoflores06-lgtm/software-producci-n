from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from apps.core.authz import METODOS_LECTURA, RUTAS_SIN_PANTALLA, codigo_de_vista, puede, respuesta_denegada


class PermisosMiddleware:
    """Exige la pantalla de la vista. Sin permiso, el POST (y el GET) responden 403."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return self.get_response(request)

        if match.url_name in RUTAS_SIN_PANTALLA:
            return self.get_response(request)

        codigo = codigo_de_vista(match.func)
        request.pantalla_codigo = codigo
        if not codigo:
            return respuesta_denegada(request)

        if not request.user.is_authenticated:
            login = reverse(settings.LOGIN_URL)
            return redirect(f'{login}?next={request.get_full_path()}')

        escribir = request.method not in METODOS_LECTURA
        if not puede(request.user, codigo, escribir=escribir):
            return respuesta_denegada(request)
        return self.get_response(request)
