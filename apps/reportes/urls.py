from django.urls import path

from apps.core.catalogo import PANTALLAS
from apps.core.views import hacer_placeholder
from apps.reportes import vistas

urlpatterns = [
    path('reportes/stock/', vistas.StockView.as_view(), name='rep.stock'),
    path('reportes/kardex/', vistas.KardexView.as_view(), name='rep.kardex'),
]

urlpatterns += [
    path(item['path'], hacer_placeholder(item).as_view(), name=item['codigo'])
    for item in PANTALLAS
    if item.get('placeholder') and item['modulo'] == 'Reportes'
]
