from django.urls import path

from apps.core.catalogo import PANTALLAS
from apps.core.views import hacer_placeholder

urlpatterns = [
    path(item['path'], hacer_placeholder(item).as_view(), name=item['codigo'])
    for item in PANTALLAS
    if item.get('placeholder') and item['modulo'] == 'Almacén'
]
