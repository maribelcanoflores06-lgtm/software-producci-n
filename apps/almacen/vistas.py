from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from apps.almacen.forms import (
    IngresoForm,
    SalidaForm,
    TransferenciaForm,
    formset_lineas,
    lineas_de_formset,
)
from apps.almacen.models import Kardex, Movimiento
from apps.almacen.services.kardex import crear_ingreso, crear_salida, crear_transferencia
from apps.core.authz import puede
from apps.core.views import PantallaMixin
from apps.maestros.models import Almacen, Anio

MESES = (
    '', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
    'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE',
)

OPERACIONES = {
    'ingreso': {
        'nombre': 'Ingreso',
        'codigo': 'alm.ingreso',
        'tipo': Movimiento.INGRESO,
        'modo': 'ingreso',
        'titulo': 'Ingresos',
        'titulo_nuevo': 'Nuevo ingreso',
        'ayuda': (
            'Compra nacional, importación, muestras u otros. El proveedor es obligatorio. '
            'El costo de cada línea es el de la compra, en soles (S/), y el promedio del almacén se recalcula.'
        ),
        'con_costo': True,
        'form': IngresoForm,
    },
    'salida': {
        'nombre': 'Salida',
        'codigo': 'alm.salida',
        'tipo': Movimiento.SALIDA,
        'modo': 'salida',
        'titulo': 'Salidas',
        'titulo_nuevo': 'Nueva salida',
        'ayuda': (
            'Sale de un almacén normal al costo promedio vigente. Ese costo no se escribe '
            'y el promedio del almacén no cambia.'
        ),
        'con_costo': False,
        'form': SalidaForm,
    },
    'transferencia': {
        'nombre': 'Transferencia',
        'codigo': 'alm.transferencia',
        'tipo': Movimiento.TRANSFERENCIA,
        'modo': 'transferencia',
        'titulo': 'Transferencias',
        'titulo_nuevo': 'Nueva transferencia',
        'ayuda': (
            'Origen y destino son almacenes normales y distintos. Sale al promedio del origen '
            'y entra al destino con ese mismo costo; allí el promedio se recalcula.'
        ),
        'con_costo': False,
        'form': TransferenciaForm,
    },
}


class NotaListaView(PantallaMixin, TemplateView):
    template_name = 'almacen/lista.html'
    config = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cfg = self.config
        anio_sel = _entero(self.request.GET.get('anio'))
        almacen_sel = _entero(self.request.GET.get('almacen'))
        q = self.request.GET.get('q', '').strip()
        notas = (
            Movimiento.objects.filter(tipo=cfg['tipo'])
            .select_related('anio', 'almacen', 'almacen_origen', 'almacen_destino', 'proveedor', 'cliente')
            .order_by('-fecha', '-id')
        )
        if anio_sel:
            notas = notas.filter(anio_id=anio_sel)
        if almacen_sel:
            if cfg['modo'] == 'transferencia':
                notas = notas.filter(
                    Q(almacen_id=almacen_sel)
                    | Q(almacen_origen_id=almacen_sel)
                    | Q(almacen_destino_id=almacen_sel)
                )
            else:
                notas = notas.filter(almacen_id=almacen_sel)
        if q:
            notas = notas.filter(
                Q(numero_nota__icontains=q)
                | Q(observacion__icontains=q)
                | Q(proveedor__razon_social__icontains=q)
                | Q(proveedor__codigo__icontains=q)
                | Q(detalles__articulo__codigo__icontains=q)
            ).distinct()
        pagina = Paginator(notas, 20).get_page(self.request.GET.get('page'))
        ctx.update({
            'cfg': cfg,
            'notas': pagina.object_list,
            'page_obj': pagina,
            'q': q,
            'anio_seleccionado': str(anio_sel) if anio_sel else '',
            'almacen_seleccionado': str(almacen_sel) if almacen_sel else '',
            'anios': Anio.objects.order_by('-anio'),
            'almacenes': Almacen.objects.filter(es_proceso=False).order_by('codigo'),
            'url_nueva': reverse(cfg['codigo'] + '_nueva'),
            'detalle_nombre': cfg['codigo'] + '_detalle',
            'url_anterior': _enlace(self.request, pagina.previous_page_number()) if pagina.has_previous() else '',
            'url_siguiente': _enlace(self.request, pagina.next_page_number()) if pagina.has_next() else '',
        })
        return ctx


class NotaNuevaView(PantallaMixin, TemplateView):
    template_name = 'almacen/nota_form.html'
    config = None

    def get(self, request):
        anio, fecha = _predeterminados()
        form = self.config['form'](initial={'anio': anio, 'fecha': fecha})
        formset = formset_lineas(con_costo=self.config['con_costo'])
        return self._render(form, formset, anio is None)

    def post(self, request):
        form = self.config['form'](request.POST)
        formset = formset_lineas(request.POST, con_costo=self.config['con_costo'])
        if form.is_valid() and formset.is_valid():
            try:
                movimiento = self._guardar(form, formset)
            except ValidationError as exc:
                for mensaje in exc.messages:
                    form.add_error(None, mensaje)
            else:
                messages.success(request, f'Nota {movimiento.numero_nota} registrada.')
                return redirect(self.config['codigo'] + '_detalle', pk=movimiento.pk)
        return self._render(form, formset, False)

    def _guardar(self, form, formset):
        data = form.cleaned_data
        comunes = {
            'anio': data['anio'],
            'fecha': data['fecha'],
            'lineas': lineas_de_formset(formset),
            'usuario': self.request.user,
            'tipo_comprobante': data.get('tipo_comprobante') or '',
            'serie_doc': data.get('serie_doc') or '',
            'numero_doc': data.get('numero_doc') or '',
            'fecha_doc': data.get('fecha_doc'),
            'observacion': data.get('observacion') or '',
        }
        modo = self.config['modo']
        if modo == 'ingreso':
            return crear_ingreso(
                subtipo=data['subtipo'],
                almacen_destino=data['almacen_destino'],
                proveedor=data['proveedor'],
                **comunes,
            )
        if modo == 'salida':
            return crear_salida(
                almacen_origen=data['almacen_origen'],
                cliente=data.get('cliente'),
                **comunes,
            )
        return crear_transferencia(
            almacen_origen=data['almacen_origen'],
            almacen_destino=data['almacen_destino'],
            **comunes,
        )

    def _render(self, form, formset, sin_anio):
        if not puede(self.request.user, self.pantalla_codigo, escribir=True):
            for field in form.fields.values():
                field.disabled = True
            for linea in formset.forms:
                for field in linea.fields.values():
                    field.disabled = True
        fecha = _fecha_visible(form)
        return self.render_to_response({
            'form': form,
            'formset': formset,
            'cfg': self.config,
            'titulo': self.config['titulo_nuevo'],
            'url_lista': reverse(self.config['codigo']),
            'prefijo': 'lineas',
            'mes': MESES[fecha.month] if fecha else '',
            'sin_anio': sin_anio,
        })


class NotaDetalleView(PantallaMixin, TemplateView):
    template_name = 'almacen/detalle.html'
    config = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cfg = self.config
        movimiento = get_object_or_404(
            Movimiento.objects.select_related(
                'anio', 'almacen', 'almacen_origen', 'almacen_destino', 'proveedor', 'cliente', 'created_by',
            ),
            pk=self.kwargs['pk'],
            tipo=cfg['tipo'],
        )
        detalles = list(movimiento.detalles.select_related('articulo').order_by('id'))
        kardex = list(
            Kardex.objects.filter(movimiento_detalle__movimiento=movimiento)
            .select_related('articulo', 'almacen')
            .order_by('id')
        )
        total = movimiento.detalles.aggregate(total=Sum('costo_total'))['total']
        ctx.update({
            'cfg': cfg,
            'movimiento': movimiento,
            'detalles': detalles,
            'kardex': kardex,
            'total': total,
            'mes': MESES[movimiento.fecha.month],
            'url_lista': reverse(cfg['codigo']),
            'url_kardex': (
                reverse('rep.kardex')
                + f'?anio={movimiento.anio_id}&desde={movimiento.fecha.isoformat()}&hasta={movimiento.fecha.isoformat()}'
            ),
            'url_stock': reverse('rep.stock') + f'?anio={movimiento.anio_id}&almacen={movimiento.almacen_id}',
        })
        return ctx


def construir(clave):
    cfg = OPERACIONES[clave]

    class Lista(NotaListaView):
        pantalla_codigo = cfg['codigo']
        config = cfg

    class Nueva(NotaNuevaView):
        pantalla_codigo = cfg['codigo']
        config = cfg

    class Detalle(NotaDetalleView):
        pantalla_codigo = cfg['codigo']
        config = cfg

    Lista.__name__ = cfg['nombre'] + 'Lista'
    Nueva.__name__ = cfg['nombre'] + 'Nueva'
    Detalle.__name__ = cfg['nombre'] + 'Detalle'
    return Lista, Nueva, Detalle


IngresoLista, IngresoNueva, IngresoDetalle = construir('ingreso')
SalidaLista, SalidaNueva, SalidaDetalle = construir('salida')
TransferenciaLista, TransferenciaNueva, TransferenciaDetalle = construir('transferencia')


def _predeterminados():
    anio = Anio.objects.filter(activo=True, cerrado=False).order_by('-anio').first()
    if anio is None:
        anio = Anio.objects.filter(cerrado=False).order_by('-anio').first()
    hoy = timezone.localdate()
    if anio and hoy.year == anio.anio:
        return anio, hoy
    if anio:
        return anio, date(anio.anio, 1, 1)
    return None, hoy


def _fecha_visible(form):
    if form.is_bound:
        try:
            fecha = form.fields['fecha'].to_python(form.data.get('fecha'))
        except ValidationError:
            fecha = None
        if fecha:
            return fecha
    return form.initial.get('fecha')


def _entero(valor):
    valor = (valor or '').strip()
    if valor.isdigit():
        return int(valor)
    return None


def _enlace(request, numero):
    params = request.GET.copy()
    params['page'] = str(numero)
    return '?' + params.urlencode()
