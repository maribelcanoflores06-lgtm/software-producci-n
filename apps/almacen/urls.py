from django.urls import path

from apps.almacen import vistas
from apps.core.catalogo import PANTALLAS
from apps.core.views import hacer_placeholder

urlpatterns = [
    path('almacen/ingreso/', vistas.IngresoLista.as_view(), name='alm.ingreso'),
    path('almacen/ingreso/nueva/', vistas.IngresoNueva.as_view(), name='alm.ingreso_nueva'),
    path('almacen/ingreso/<int:pk>/', vistas.IngresoDetalle.as_view(), name='alm.ingreso_detalle'),
    path('almacen/salida/', vistas.SalidaLista.as_view(), name='alm.salida'),
    path('almacen/salida/nueva/', vistas.SalidaNueva.as_view(), name='alm.salida_nueva'),
    path('almacen/salida/<int:pk>/', vistas.SalidaDetalle.as_view(), name='alm.salida_detalle'),
    path('almacen/transferencia/', vistas.TransferenciaLista.as_view(), name='alm.transferencia'),
    path('almacen/transferencia/nueva/', vistas.TransferenciaNueva.as_view(), name='alm.transferencia_nueva'),
    path('almacen/transferencia/<int:pk>/', vistas.TransferenciaDetalle.as_view(), name='alm.transferencia_detalle'),
]

urlpatterns += [
    path(item['path'], hacer_placeholder(item).as_view(), name=item['codigo'])
    for item in PANTALLAS
    if item.get('placeholder') and item['modulo'] == 'Almacén'
]
