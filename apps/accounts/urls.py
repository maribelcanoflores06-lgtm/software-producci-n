from django.urls import path

from apps.accounts import vistas
from apps.core.catalogo import path_de

urlpatterns = [
    path(path_de('admin.usuarios'), vistas.UsuarioListView.as_view(), name='admin.usuarios'),
    path(path_de('admin.usuarios') + 'nuevo/', vistas.UsuarioCreateView.as_view(), name='admin.usuarios_nueva'),
    path(path_de('admin.usuarios') + '<int:pk>/', vistas.UsuarioUpdateView.as_view(), name='admin.usuarios_editar'),
    path(path_de('admin.roles'), vistas.RolListView.as_view(), name='admin.roles'),
    path(path_de('admin.roles') + 'nuevo/', vistas.RolCreateView.as_view(), name='admin.roles_nueva'),
    path(path_de('admin.roles') + '<int:pk>/', vistas.RolUpdateView.as_view(), name='admin.roles_editar'),
    path(path_de('admin.roles') + '<int:pk>/eliminar/', vistas.RolEliminarView.as_view(), name='admin.roles_eliminar'),
    path(path_de('admin.rol_pantallas'), vistas.PermisosIndexView.as_view(), name='admin.rol_pantallas'),
    path(
        path_de('admin.roles') + '<int:pk>/pantallas/',
        vistas.RolPantallasView.as_view(),
        name='admin.rol_pantallas_editar',
    ),
]
