from django.urls import include, path
from django.views.generic import RedirectView

from apps.core.views import AccesoView, InicioView, SalirView

urlpatterns = [
    path('', InicioView.as_view(), name='home'),
    path('cuentas/ingresar/', AccesoView.as_view(), name='login'),
    path('cuentas/salir/', SalirView.as_view(), name='logout'),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=False), name='favicon'),
    path('', include('apps.accounts.urls')),
    path('', include('apps.maestros.urls')),
    path('', include('apps.almacen.urls')),
    path('', include('apps.produccion.urls')),
    path('', include('apps.reportes.urls')),
]

handler403 = 'apps.core.views.permiso_denegado'
handler404 = 'apps.core.views.no_encontrado'
