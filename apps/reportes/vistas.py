from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import TemplateView

from apps.almacen.models import Kardex, Movimiento, StockActual
from apps.core.views import PantallaMixin
from apps.maestros.models import Almacen, Anio, Articulo

ETIQUETAS_MOV = dict(Movimiento.TIPOS)


class StockView(PantallaMixin, TemplateView):
    pantalla_codigo = 'rep.stock'
    template_name = 'reportes/stock.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anio_sel = _entero(self.request.GET.get('anio'))
        almacen_sel = _entero(self.request.GET.get('almacen'))
        articulo_sel = _entero(self.request.GET.get('articulo'))
        stocks = (
            StockActual.objects.select_related('articulo', 'almacen', 'anio')
            .filter(Q(cantidad__gt=0) | Q(valor__gt=0))
            .order_by('almacen__codigo', 'articulo__codigo')
        )
        if anio_sel:
            stocks = stocks.filter(anio_id=anio_sel)
        if almacen_sel:
            stocks = stocks.filter(almacen_id=almacen_sel)
        if articulo_sel:
            stocks = stocks.filter(articulo_id=articulo_sel)
        pagina = Paginator(stocks, 50).get_page(self.request.GET.get('page'))
        ctx.update({
            'filas': pagina.object_list,
            'page_obj': pagina,
            'anios': Anio.objects.order_by('-anio'),
            'almacenes': Almacen.objects.order_by('codigo'),
            'articulos': Articulo.objects.order_by('codigo'),
            'anio_seleccionado': str(anio_sel) if anio_sel else '',
            'almacen_seleccionado': str(almacen_sel) if almacen_sel else '',
            'articulo_seleccionado': str(articulo_sel) if articulo_sel else '',
            'hay_filtro': bool(anio_sel or almacen_sel or articulo_sel),
            'url_anterior': _enlace(self.request, pagina.previous_page_number()) if pagina.has_previous() else '',
            'url_siguiente': _enlace(self.request, pagina.next_page_number()) if pagina.has_next() else '',
        })
        return ctx


class KardexView(PantallaMixin, TemplateView):
    pantalla_codigo = 'rep.kardex'
    template_name = 'reportes/kardex.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anio_sel = _entero(self.request.GET.get('anio'))
        almacen_sel = _entero(self.request.GET.get('almacen'))
        articulo_sel = _entero(self.request.GET.get('articulo'))
        desde = (self.request.GET.get('desde') or '').strip()
        hasta = (self.request.GET.get('hasta') or '').strip()
        filas = (
            Kardex.objects.select_related('articulo', 'almacen', 'anio')
            .order_by('fecha', 'id')
        )
        if anio_sel:
            filas = filas.filter(anio_id=anio_sel)
        if almacen_sel:
            filas = filas.filter(almacen_id=almacen_sel)
        if articulo_sel:
            filas = filas.filter(articulo_id=articulo_sel)
        if _fecha(desde):
            filas = filas.filter(fecha__gte=desde)
        else:
            desde = ''
        if _fecha(hasta):
            filas = filas.filter(fecha__lte=hasta)
        else:
            hasta = ''
        pagina = Paginator(filas, 50).get_page(self.request.GET.get('page'))
        for fila in pagina.object_list:
            fila.tipo_etiqueta = ETIQUETAS_MOV.get(fila.tipo_mov, fila.tipo_mov)
        ctx.update({
            'filas': pagina.object_list,
            'page_obj': pagina,
            'anios': Anio.objects.order_by('-anio'),
            'almacenes': Almacen.objects.order_by('codigo'),
            'articulos': Articulo.objects.order_by('codigo'),
            'anio_seleccionado': str(anio_sel) if anio_sel else '',
            'almacen_seleccionado': str(almacen_sel) if almacen_sel else '',
            'articulo_seleccionado': str(articulo_sel) if articulo_sel else '',
            'desde': desde,
            'hasta': hasta,
            'hay_filtro': bool(anio_sel or almacen_sel or articulo_sel or desde or hasta),
            'url_anterior': _enlace(self.request, pagina.previous_page_number()) if pagina.has_previous() else '',
            'url_siguiente': _enlace(self.request, pagina.next_page_number()) if pagina.has_next() else '',
        })
        return ctx


def _entero(valor):
    valor = (valor or '').strip()
    if valor.isdigit():
        return int(valor)
    return None


def _fecha(valor):
    if len(valor) != 10 or valor[4] != '-' or valor[7] != '-':
        return False
    return valor[0:4].isdigit() and valor[5:7].isdigit() and valor[8:10].isdigit()


def _enlace(request, numero):
    params = request.GET.copy()
    params['page'] = str(numero)
    return '?' + params.urlencode()
