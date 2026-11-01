from django.urls import path

from apps.core.catalogo import path_de
from apps.maestros import vistas
from apps.maestros.lineas import RecetaFormView, RutaFormView

urlpatterns = [
    path(path_de('mae.recetas'), vistas.RecetaListView.as_view(), name='mae.recetas'),
    path(path_de('mae.recetas') + 'nuevo/', RecetaFormView.as_view(), name='mae.recetas_nueva'),
    path(path_de('mae.recetas') + '<int:pk>/', RecetaFormView.as_view(), name='mae.recetas_editar'),
    path(path_de('mae.rutas'), vistas.RutaListView.as_view(), name='mae.rutas'),
    path(path_de('mae.rutas') + 'nuevo/', RutaFormView.as_view(), name='mae.rutas_nueva'),
    path(path_de('mae.rutas') + '<int:pk>/', RutaFormView.as_view(), name='mae.rutas_editar'),
    path(path_de('admin.anios'), vistas.AnioListView.as_view(), name='admin.anios'),
    path(path_de('admin.anios') + 'nuevo/', vistas.AnioCreateView.as_view(), name='admin.anios_nueva'),
    path(path_de('admin.anios') + '<int:pk>/cerrar/', vistas.AnioCerrarView.as_view(), name='admin.anios_cerrar'),
    path(path_de('admin.anios') + '<int:pk>/activar/', vistas.AnioActivarView.as_view(), name='admin.anios_activar'),
    path(path_de('admin.saldo_inicial'), vistas.SaldoInicialView.as_view(), name='admin.saldo_inicial'),
    path('sistema/datos-ejemplo/', vistas.datos_ejemplo, name='datos_ejemplo'),
]

for _codigo, (_lista, _crear, _editar) in vistas.VISTAS.items():
    _base = path_de(_codigo)
    urlpatterns += [
        path(_base, _lista.as_view(), name=_codigo),
        path(_base + 'nuevo/', _crear.as_view(), name=_codigo + '_nueva'),
        path(_base + '<int:pk>/', _editar.as_view(), name=_codigo + '_editar'),
    ]
