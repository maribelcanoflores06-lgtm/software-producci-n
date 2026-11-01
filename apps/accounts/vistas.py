from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.forms import RolForm, UsuarioForm
from apps.accounts.models import Pantalla, Rol, RolPantalla, Usuario
from apps.core.authz import puede, respuesta_denegada
from apps.core.catalogo import PANTALLAS, PANTALLAS_ADMIN_FIJAS, USUARIOS_DEMO_USERNAME
from apps.core.views import PantallaMixin
from apps.maestros.vistas import CatalogoCreateView, CatalogoListView, CatalogoUpdateView


def _si(valor):
    return 'Sí' if valor else 'No'


class UsuarioListView(CatalogoListView):
    model = Usuario
    pantalla_codigo = 'admin.usuarios'
    titulo = 'Usuarios'
    search_fields = ('username', 'nombres', 'email')
    ordering = ('username',)
    url_crear = 'admin.usuarios_nueva'
    url_editar = 'admin.usuarios_editar'
    ejemplo_attr = 'username'
    columnas = [
        ('Usuario', lambda o: o.username),
        ('Nombres', lambda o: o.nombres),
        ('Correo', lambda o: o.email or '—'),
        ('Rol', lambda o: o.rol.nombre),
        ('Activo', lambda o: _si(o.is_active)),
    ]
    select_related_fields = ('rol',)

    def es_ejemplo(self, obj):
        return obj.username in USUARIOS_DEMO_USERNAME


class UsuarioCreateView(CatalogoCreateView):
    model = Usuario
    form_class = UsuarioForm
    pantalla_codigo = 'admin.usuarios'
    url_lista = 'admin.usuarios'
    titulo_crear = 'Nuevo usuario'
    titulo_editar = 'Editar usuario'
    mensaje_ok = 'Usuario guardado.'


class UsuarioUpdateView(CatalogoUpdateView):
    model = Usuario
    form_class = UsuarioForm
    pantalla_codigo = 'admin.usuarios'
    url_lista = 'admin.usuarios'
    titulo_crear = 'Nuevo usuario'
    titulo_editar = 'Editar usuario'
    mensaje_ok = 'Usuario guardado.'


class RolListView(CatalogoListView):
    model = Rol
    pantalla_codigo = 'admin.roles'
    titulo = 'Roles'
    search_fields = ('codigo', 'nombre')
    ordering = ('nombre',)
    url_crear = 'admin.roles_nueva'
    url_editar = 'admin.roles_editar'
    enlace_pantallas = True
    columnas = [
        ('Código', lambda o: o.codigo),
        ('Nombre', lambda o: o.nombre),
        ('Usuarios', lambda o: o.n_usuarios),
        ('Activo', lambda o: _si(o.activo)),
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(n_usuarios=Count('usuarios'))


class RolCreateView(CatalogoCreateView):
    model = Rol
    form_class = RolForm
    pantalla_codigo = 'admin.roles'
    url_lista = 'admin.roles'
    titulo_crear = 'Nuevo rol'
    titulo_editar = 'Editar rol'
    mensaje_ok = 'Rol guardado.'


class RolUpdateView(CatalogoUpdateView):
    model = Rol
    form_class = RolForm
    pantalla_codigo = 'admin.roles'
    url_lista = 'admin.roles'
    titulo_crear = 'Nuevo rol'
    titulo_editar = 'Editar rol'
    mensaje_ok = 'Rol guardado.'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.object.codigo == 'ADMIN':
            ctx['nota_eliminar'] = 'El rol Admin permanece en el sistema.'
        elif self.object.usuarios.exists():
            ctx['nota_eliminar'] = 'Para eliminar el rol, primero reasigne sus usuarios.'
        else:
            ctx['url_eliminar'] = reverse('admin.roles_eliminar', args=[self.object.pk])
        return ctx


class RolEliminarView(PantallaMixin, View):
    pantalla_codigo = 'admin.roles'

    def post(self, request, pk):
        rol = get_object_or_404(Rol, pk=pk)
        if rol.codigo == 'ADMIN':
            messages.error(request, 'No se puede eliminar el rol Admin.')
            return redirect('admin.roles_editar', rol.pk)
        if rol.usuarios.exists():
            messages.error(request, 'No se puede eliminar un rol que tiene usuarios asignados.')
            return redirect('admin.roles_editar', rol.pk)
        rol.delete()
        messages.success(request, 'Rol eliminado.')
        return redirect('admin.roles')


class PermisosIndexView(PantallaMixin, TemplateView):
    pantalla_codigo = 'admin.rol_pantallas'
    template_name = 'accounts/permisos_index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['roles'] = Rol.objects.annotate(n_usuarios=Count('usuarios')).order_by('nombre')
        return ctx


class RolPantallasView(PantallaMixin, TemplateView):
    pantalla_codigo = 'admin.rol_pantallas'
    template_name = 'accounts/rol_pantallas.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.rol = get_object_or_404(Rol, pk=kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        asignados = {
            fila.pantalla_id: fila.puede_escribir
            for fila in RolPantalla.objects.filter(rol=self.rol)
        }
        orden = [item['codigo'] for item in PANTALLAS]
        pantallas = sorted(
            Pantalla.objects.all(),
            key=lambda pantalla: orden.index(pantalla.codigo) if pantalla.codigo in orden else 999,
        )
        grupos = []
        for pantalla in pantallas:
            if not grupos or grupos[-1]['modulo'] != pantalla.modulo:
                grupos.append({'modulo': pantalla.modulo, 'items': []})
            grupos[-1]['items'].append({
                'id': pantalla.id,
                'codigo': pantalla.codigo,
                'nombre': pantalla.nombre,
                'ver': pantalla.id in asignados,
                'modificar': bool(asignados.get(pantalla.id, False)),
                'fija': self.rol.codigo == 'ADMIN' and pantalla.codigo in PANTALLAS_ADMIN_FIJAS,
            })
        ctx['grupos'] = grupos
        ctx['rol'] = self.rol
        return ctx

    def post(self, request, *args, **kwargs):
        if not puede(request.user, self.pantalla_codigo, escribir=True):
            return respuesta_denegada(request)
        ver = set(request.POST.getlist('ver'))
        modificar = set(request.POST.getlist('modificar'))
        RolPantalla.objects.filter(rol=self.rol).delete()
        for pantalla in Pantalla.objects.all():
            pid = str(pantalla.id)
            fija = self.rol.codigo == 'ADMIN' and pantalla.codigo in PANTALLAS_ADMIN_FIJAS
            escribe = fija or pid in modificar
            ve = fija or escribe or pid in ver
            if not ve:
                continue
            RolPantalla.objects.create(rol=self.rol, pantalla=pantalla, puede_escribir=escribe)
        messages.success(request, 'Permisos actualizados.')
        return redirect('admin.rol_pantallas_editar', self.rol.pk)
