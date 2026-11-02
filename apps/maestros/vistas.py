from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.views.generic.edit import FormView

from apps.almacen.models import Movimiento, MovimientoDetalle, StockActual
from apps.almacen.services.saldo_inicial import registrar_saldo_inicial
from apps.core.authz import puede, respuesta_denegada
from apps.core.catalogo import CODIGOS_EJEMPLO, TIPOS_MATERIAL, USUARIOS_DEMO_USERNAME
from apps.core.seed import seed_ejemplo
from apps.core.views import PantallaMixin, requiere_pantalla
from apps.maestros.forms import (
    AlmacenForm,
    AnioForm,
    ArticuloForm,
    ClienteForm,
    ProcesoForm,
    ProveedorForm,
    SaldoInicialForm,
    TrabajadorForm,
)
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    Cliente,
    CorrelativoNota,
    CorrelativoOp,
    Proceso,
    Proveedor,
    Maquina,
    Receta,
    Ruta,
    SaldoInicial,
    TipoMaterial,
    Trabajador,
)
from apps.maestros.services.cierre_anio import cerrar


def si_no(valor):
    return 'Sí' if valor else 'No'


def _tipos_en_orden_de_spec():
    orden = {codigo: indice for indice, (codigo, _nombre) in enumerate(TIPOS_MATERIAL)}
    return sorted(TipoMaterial.objects.all(), key=lambda tipo: orden.get(tipo.codigo, 99))


def dec(valor):
    if valor is None:
        return '—'
    return f'{valor:.4f}'


class CatalogoListView(PantallaMixin, ListView):
    template_name = 'maestros/lista.html'
    paginate_by = 20
    context_object_name = 'registros'
    search_fields = ()
    columnas = ()
    select_related_fields = ()
    prefetch_related_fields = ()
    ordering = ('codigo',)
    url_crear = None
    url_editar = None
    titulo = ''
    mostrar_tipos = False
    filtro_es_proceso = False
    ejemplo_attr = 'codigo'
    enlace_pantallas = False

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.select_related_fields:
            qs = qs.select_related(*self.select_related_fields)
        if self.prefetch_related_fields:
            qs = qs.prefetch_related(*self.prefetch_related_fields)
        if self.ordering:
            qs = qs.order_by(*self.ordering)
        texto = self.request.GET.get('q', '').strip()
        if texto and self.search_fields:
            filtro = Q()
            for campo in self.search_fields:
                filtro |= Q(**{f'{campo}__icontains': texto})
            qs = qs.filter(filtro)
        if self.mostrar_tipos:
            tipo = self.request.GET.get('tipo', '').strip().upper()
            if tipo and tipo != 'TODOS':
                qs = qs.filter(tipo_material__codigo=tipo)
        if self.filtro_es_proceso:
            marca = self.request.GET.get('proceso', '').strip().lower()
            if marca == 'si':
                qs = qs.filter(es_proceso=True)
            elif marca == 'no':
                qs = qs.filter(es_proceso=False)
        return qs

    def es_ejemplo(self, obj):
        codigo = getattr(obj, self.ejemplo_attr, None)
        return codigo in CODIGOS_EJEMPLO or codigo in USUARIOS_DEMO_USERNAME

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filas = []
        for obj in ctx['registros']:
            filas.append({
                'pk': obj.pk,
                'celdas': [fn(obj) for _, fn in self.columnas],
                'ejemplo': self.es_ejemplo(obj),
                'editar': reverse(self.url_editar, args=[obj.pk]) if self.url_editar else None,
            })
        if self.enlace_pantallas and puede(self.request.user, 'admin.rol_pantallas'):
            for fila in filas:
                fila['pantallas'] = reverse('admin.rol_pantallas_editar', args=[fila['pk']])
        tipo = ''
        if self.mostrar_tipos:
            tipo = self.request.GET.get('tipo', '').strip().upper()
            if tipo == 'TODOS':
                tipo = ''
        pagina = ctx.get('page_obj')
        proceso = ''
        if self.filtro_es_proceso:
            proceso = self.request.GET.get('proceso', '').strip().lower()
            if proceso not in {'si', 'no'}:
                proceso = ''
        ctx.update({
            'filas': filas,
            'encabezados': [titulo for titulo, _ in self.columnas],
            'q': self.request.GET.get('q', '').strip(),
            'tipo_seleccionado': tipo,
            'proceso_seleccionado': proceso,
            'titulo': self.titulo,
            'url_crear': reverse(self.url_crear) if self.url_crear else None,
            'mostrar_tipos': self.mostrar_tipos,
            'filtro_es_proceso': self.filtro_es_proceso,
            'tipos': _tipos_en_orden_de_spec() if self.mostrar_tipos else None,
            'url_anterior': _enlace_pagina(self.request, pagina.previous_page_number()) if pagina and pagina.has_previous() else '',
            'url_siguiente': _enlace_pagina(self.request, pagina.next_page_number()) if pagina and pagina.has_next() else '',
        })
        return ctx


def _enlace_pagina(request, numero):
    params = request.GET.copy()
    params['page'] = str(numero)
    return '?' + params.urlencode()


class _FormularioMixin(PantallaMixin):
    template_name = 'maestros/formulario.html'
    url_lista = None
    titulo_crear = 'Nuevo'
    titulo_editar = 'Editar'
    mensaje_ok = 'Registro guardado.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['solo_lectura'] = not puede(self.request.user, self.pantalla_codigo, escribir=True)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = getattr(self, 'object', None)
        ctx['titulo'] = self.titulo_editar if getattr(obj, 'pk', None) else self.titulo_crear
        ctx['url_lista'] = reverse(self.url_lista)
        ctx['url_eliminar'] = None
        ctx['nota_eliminar'] = None
        return ctx

    def form_valid(self, form):
        messages.success(self.request, self.mensaje_ok)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(self.url_lista)


class CatalogoCreateView(_FormularioMixin, CreateView):
    pass


class CatalogoUpdateView(_FormularioMixin, UpdateView):
    pass


def _armar(cfg):
    class Lista(CatalogoListView):
        model = cfg['model']
        pantalla_codigo = cfg['pantalla']
        columnas = cfg['columnas']
        search_fields = cfg['search']
        select_related_fields = cfg.get('select', ())
        ordering = cfg.get('ordering', ('codigo',))
        url_crear = cfg['pantalla'] + '_nueva'
        url_editar = cfg['pantalla'] + '_editar'
        titulo = cfg['titulo']
        mostrar_tipos = cfg.get('tipos', False)
        filtro_es_proceso = cfg.get('filtro_proceso', False)

    class Crear(CatalogoCreateView):
        model = cfg['model']
        form_class = cfg['form']
        pantalla_codigo = cfg['pantalla']
        url_lista = cfg['pantalla']
        titulo_crear = cfg['titulo_crear']
        titulo_editar = cfg['titulo_editar']
        mensaje_ok = cfg['mensaje']

    class Editar(CatalogoUpdateView):
        model = cfg['model']
        form_class = cfg['form']
        pantalla_codigo = cfg['pantalla']
        url_lista = cfg['pantalla']
        titulo_crear = cfg['titulo_crear']
        titulo_editar = cfg['titulo_editar']
        mensaje_ok = cfg['mensaje']

    nombre = cfg['nombre']
    Lista.__name__ = nombre + 'Lista'
    Crear.__name__ = nombre + 'Crear'
    Editar.__name__ = nombre + 'Editar'
    return Lista, Crear, Editar


CATALOGOS = [
    {
        'nombre': 'Articulo',
        'model': Articulo,
        'form': ArticuloForm,
        'pantalla': 'mae.articulos',
        'titulo': 'Artículos',
        'titulo_crear': 'Nuevo artículo',
        'titulo_editar': 'Editar artículo',
        'mensaje': 'Artículo guardado.',
        'search': ('codigo', 'descripcion', 'unidad_medida'),
        'select': ('tipo_material',),
        'tipos': True,
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('Descripción', lambda o: o.descripcion),
            ('Tipo', lambda o: f'{o.tipo_material.codigo} · {o.tipo_material.nombre}'),
            ('UM', lambda o: o.unidad_medida),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
    {
        'nombre': 'Cliente',
        'model': Cliente,
        'form': ClienteForm,
        'pantalla': 'mae.clientes',
        'titulo': 'Clientes',
        'titulo_crear': 'Nuevo cliente',
        'titulo_editar': 'Editar cliente',
        'mensaje': 'Cliente guardado.',
        'search': ('codigo', 'razon_social', 'ruc_documento'),
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('RUC / documento', lambda o: o.ruc_documento or '—'),
            ('Razón social', lambda o: o.razon_social),
            ('Teléfono', lambda o: o.telefono or '—'),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
    {
        'nombre': 'Proveedor',
        'model': Proveedor,
        'form': ProveedorForm,
        'pantalla': 'mae.proveedores',
        'titulo': 'Proveedores',
        'titulo_crear': 'Nuevo proveedor',
        'titulo_editar': 'Editar proveedor',
        'mensaje': 'Proveedor guardado.',
        'search': ('codigo', 'razon_social', 'ruc_documento'),
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('RUC / documento', lambda o: o.ruc_documento or '—'),
            ('Razón social', lambda o: o.razon_social),
            ('Teléfono', lambda o: o.telefono or '—'),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
    {
        'nombre': 'Trabajador',
        'model': Trabajador,
        'form': TrabajadorForm,
        'pantalla': 'mae.trabajadores',
        'titulo': 'Trabajadores',
        'titulo_crear': 'Nuevo trabajador',
        'titulo_editar': 'Editar trabajador',
        'mensaje': 'Trabajador guardado.',
        'search': ('codigo', 'nombres', 'numero_documento'),
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('Nombres', lambda o: o.nombres),
            ('Documento', lambda o: o.get_tipo_documento_display()),
            ('Número', lambda o: o.numero_documento),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
    {
        'nombre': 'Almacen',
        'model': Almacen,
        'form': AlmacenForm,
        'pantalla': 'mae.almacenes',
        'titulo': 'Almacenes',
        'titulo_crear': 'Nuevo almacén',
        'titulo_editar': 'Editar almacén',
        'mensaje': 'Almacén guardado.',
        'search': ('codigo', 'nombre'),
        'filtro_proceso': True,
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('Nombre', lambda o: o.nombre),
            ('Es proceso', lambda o: si_no(o.es_proceso)),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
    {
        'nombre': 'Proceso',
        'model': Proceso,
        'form': ProcesoForm,
        'pantalla': 'mae.procesos',
        'titulo': 'Procesos',
        'titulo_crear': 'Nuevo proceso',
        'titulo_editar': 'Editar proceso',
        'mensaje': 'Proceso guardado.',
        'search': ('codigo', 'nombre'),
        'columnas': [
            ('Código', lambda o: o.codigo),
            ('Nombre', lambda o: o.nombre),
            ('Activo', lambda o: si_no(o.activo)),
        ],
    },
]

VISTAS = {}
for _cfg in CATALOGOS:
    VISTAS[_cfg['pantalla']] = _armar(_cfg)


class RecetaListView(CatalogoListView):
    model = Receta
    pantalla_codigo = 'mae.recetas'
    titulo = 'Recetas (BOM)'
    search_fields = ('articulo_pt__codigo', 'articulo_pt__descripcion')
    ordering = ('articulo_pt__codigo',)
    select_related_fields = ('articulo_pt',)
    url_crear = 'mae.recetas_nueva'
    url_editar = 'mae.recetas_editar'
    columnas = [
        ('PT', lambda o: o.articulo_pt.codigo),
        ('Descripción', lambda o: o.articulo_pt.descripcion),
        ('Lote base', lambda o: dec(o.lote_base)),
        ('Insumos', lambda o: o.n_insumos),
        ('Activo', lambda o: si_no(o.activo)),
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(n_insumos=Count('detalles'))

    def es_ejemplo(self, obj):
        return obj.articulo_pt.codigo in CODIGOS_EJEMPLO


class MaquinaListView(CatalogoListView):
    model = Maquina
    pantalla_codigo = 'mae.maquinas'
    titulo = 'Máquinas'
    search_fields = ('codigo', 'nombre', 'descripcion')
    ordering = ('codigo',)
    prefetch_related_fields = ('asignaciones__proceso',)
    url_crear = 'mae.maquinas_nueva'
    url_editar = 'mae.maquinas_editar'
    columnas = [
        ('Código', lambda o: o.codigo),
        ('Nombre', lambda o: o.nombre),
        ('Procesos', lambda o: _resumen_maquina(o)),
        ('Activo', lambda o: si_no(o.activo)),
    ]


def _resumen_maquina(maquina):
    codigos = [fila.proceso.codigo for fila in maquina.asignaciones.all()]
    return ', '.join(codigos) if codigos else '—'


class RutaListView(CatalogoListView):
    model = Ruta
    pantalla_codigo = 'mae.rutas'
    titulo = 'Rutas'
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    prefetch_related_fields = ('pasos__proceso__maquinas',)
    url_crear = 'mae.rutas_nueva'
    url_editar = 'mae.rutas_editar'
    columnas = [
        ('Código', lambda o: o.codigo),
        ('Nombre', lambda o: o.nombre),
        ('Procesos y máquinas que pueden', lambda o: _resumen_ruta(o)),
        ('Activo', lambda o: si_no(o.activo)),
    ]


def _resumen_ruta(ruta):
    partes = []
    for paso in ruta.pasos.all():
        maquinas = [maquina.codigo for maquina in paso.proceso.maquinas.all() if maquina.activo]
        if maquinas:
            partes.append(f'{paso.secuencia} {paso.proceso.codigo} ({", ".join(maquinas)})')
        else:
            partes.append(f'{paso.secuencia} {paso.proceso.codigo} (sin máquina)')
    return ' → '.join(partes) if partes else '—'


class AnioListView(PantallaMixin, TemplateView):
    pantalla_codigo = 'admin.anios'
    template_name = 'maestros/anios.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anios = list(Anio.objects.order_by('-anio'))
        almacenes = list(Almacen.objects.order_by('codigo'))
        notas = {(fila.anio_id, fila.almacen_id): fila.ultimo for fila in CorrelativoNota.objects.all()}
        ops = {fila.anio_id: fila.ultimo for fila in CorrelativoOp.objects.all()}
        correlativos = []
        for anio in anios:
            for almacen in almacenes:
                correlativos.append({
                    'anio': anio.anio,
                    'almacen': almacen.codigo,
                    'ultimo': notas.get((anio.id, almacen.id), 0),
                })
        ctx.update({
            'anios': anios,
            'correlativos': correlativos,
            'ops': [(anio.anio, ops.get(anio.id, 0)) for anio in anios],
            'hay_almacenes': bool(almacenes),
        })
        return ctx


class AnioCreateView(CatalogoCreateView):
    model = Anio
    form_class = AnioForm
    pantalla_codigo = 'admin.anios'
    url_lista = 'admin.anios'
    titulo_crear = 'Nuevo año'
    titulo_editar = 'Editar año'
    mensaje_ok = 'Año guardado.'


class AnioCerrarView(PantallaMixin, TemplateView):
    pantalla_codigo = 'admin.anios'
    template_name = 'maestros/anio_cerrar.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.anio = get_object_or_404(Anio, pk=kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['anio'] = self.anio
        ctx['siguiente'] = self.anio.anio + 1
        ctx['n_saldos'] = (
            StockActual.objects.filter(anio=self.anio)
            .filter(Q(cantidad__gt=0) | Q(valor__gt=0))
            .count()
        )
        return ctx

    def post(self, request, *args, **kwargs):
        try:
            siguiente, copiados = cerrar(self.anio.pk, request.user)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('admin.anios')
        if copiados:
            messages.success(
                request,
                f'Año {self.anio.anio} cerrado. {copiados} saldo(s) inicial(es) quedaron en {siguiente.anio}.',
            )
        else:
            messages.success(
                request,
                f'Año {self.anio.anio} cerrado. No había saldos para pasar a {siguiente.anio}.',
            )
        return redirect('admin.anios')


class AnioActivarView(PantallaMixin, View):
    pantalla_codigo = 'admin.anios'

    def post(self, request, pk):
        anio = get_object_or_404(Anio, pk=pk)
        if anio.cerrado:
            messages.error(request, 'Un año cerrado no vuelve a ser el año de trabajo.')
        else:
            anio.activo = True
            anio.save()
            messages.success(request, f'El año de trabajo es {anio.anio}.')
        return redirect('admin.anios')


class SaldoInicialView(PantallaMixin, FormView):
    pantalla_codigo = 'admin.saldo_inicial'
    template_name = 'maestros/saldo_inicial.html'
    form_class = SaldoInicialForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['solo_lectura'] = not puede(self.request.user, self.pantalla_codigo, escribir=True)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        saldos = SaldoInicial.objects.select_related('anio', 'almacen', 'articulo').order_by(
            '-anio__anio', 'almacen__codigo', 'articulo__codigo'
        )
        anio_sel = self.request.GET.get('anio', '').strip()
        almacen_sel = self.request.GET.get('almacen', '').strip()
        if anio_sel.isdigit():
            saldos = saldos.filter(anio_id=int(anio_sel))
        else:
            anio_sel = ''
        if almacen_sel.isdigit():
            saldos = saldos.filter(almacen_id=int(almacen_sel))
        else:
            almacen_sel = ''
        notas = {
            (detalle.movimiento.anio_id, detalle.movimiento.almacen_id, detalle.articulo_id): detalle.movimiento.numero_nota
            for detalle in MovimientoDetalle.objects.filter(
                movimiento__tipo=Movimiento.SALDO_INICIAL
            ).select_related('movimiento')
        }
        ctx['saldos'] = [
            {
                'obj': saldo,
                'nota': notas.get((saldo.anio_id, saldo.almacen_id, saldo.articulo_id), '—'),
                'ejemplo': saldo.articulo.codigo in CODIGOS_EJEMPLO,
            }
            for saldo in saldos
        ]
        ctx['anios_filtro'] = Anio.objects.order_by('-anio')
        ctx['almacenes_filtro'] = Almacen.objects.order_by('codigo')
        ctx['anio_seleccionado'] = anio_sel
        ctx['almacen_seleccionado'] = almacen_sel
        return ctx

    def form_valid(self, form):
        try:
            _saldo, movimiento = registrar_saldo_inicial(
                anio=form.cleaned_data['anio'],
                almacen=form.cleaned_data['almacen'],
                articulo=form.cleaned_data['articulo'],
                cantidad=form.cleaned_data['cantidad'],
                costo_unitario=form.cleaned_data['costo_unitario'],
                usuario=self.request.user,
            )
        except ValidationError as exc:
            for mensaje in exc.messages:
                form.add_error(None, mensaje)
            return self.form_invalid(form)
        messages.success(self.request, f'Saldo inicial registrado. Nota {movimiento.numero_nota}.')
        return redirect('admin.saldo_inicial')


@requiere_pantalla('admin.anios')
def datos_ejemplo(request):
    if request.method != 'POST':
        return redirect('home')
    rol = getattr(request.user, 'rol', None)
    if rol is None or rol.codigo != 'ADMIN':
        return respuesta_denegada(request)
    ok, mensaje = seed_ejemplo()
    if ok:
        messages.success(request, mensaje)
    else:
        messages.error(request, mensaje)
    if request.POST.get('volver') == 'saldo':
        return redirect('admin.saldo_inicial')
    return redirect('home')
