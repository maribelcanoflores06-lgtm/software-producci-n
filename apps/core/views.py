from functools import wraps

from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.accounts.forms import AccesoForm
from apps.accounts.models import Usuario
from apps.core.catalogo import USUARIOS_DEMO


class PantallaMixin:
    pantalla_codigo = None

    def dispatch(self, request, *args, **kwargs):
        request.pantalla_codigo = self.pantalla_codigo
        return super().dispatch(request, *args, **kwargs)


def requiere_pantalla(codigo):
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            request.pantalla_codigo = codigo
            return vista(request, *args, **kwargs)

        envoltura.pantalla_codigo = codigo
        return envoltura

    return decorador


def hacer_placeholder(pantalla):
    class Vista(PantallaMixin, TemplateView):
        template_name = 'core/proximamente.html'
        pantalla_codigo = pantalla['codigo']

    Vista.__name__ = 'Ph_' + pantalla['codigo'].replace('.', '_')
    return Vista


class AccesoView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = AccesoForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuarios_demo'] = USUARIOS_DEMO
        ctx['sin_usuarios'] = not Usuario.objects.exists()
        return ctx


class SalirView(LogoutView):
    next_page = 'login'


class InicioView(TemplateView):
    template_name = 'core/inicio.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)


def permiso_denegado(request, exception=None):
    from apps.core.authz import MENSAJE_DENEGADO, respuesta_denegada

    if getattr(request, 'pantalla_codigo', None):
        return respuesta_denegada(request)
    from django.shortcuts import render

    return render(request, '403.html', {'mensaje': MENSAJE_DENEGADO}, status=403)


def no_encontrado(request, exception=None):
    from django.shortcuts import render

    return render(request, '404.html', status=404)
