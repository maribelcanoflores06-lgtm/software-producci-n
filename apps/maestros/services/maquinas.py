"""Máquinas que pueden realizar un proceso del maestro.

La ruta no guarda la máquina. En la orden de producción se elige la ruta y,
para cada proceso, una máquina activa vinculada a ese proceso.
"""

from apps.maestros.models import Maquina, MaquinaProceso


def maquinas_que_pueden(proceso, *, solo_activas=True):
    qs = Maquina.objects.filter(procesos=proceso)
    if solo_activas:
        qs = qs.filter(activo=True)
    return qs.order_by('codigo')


def catalogo_maquinas_por_proceso():
    """Mapa proceso_id → máquinas activas, para la pantalla de la ruta."""
    mapa = {}
    filas = (
        MaquinaProceso.objects.filter(maquina__activo=True, proceso__activo=True)
        .select_related('maquina')
        .order_by('maquina__codigo')
    )
    for fila in filas:
        mapa.setdefault(str(fila.proceso_id), []).append({
            'codigo': fila.maquina.codigo,
            'nombre': fila.maquina.nombre,
        })
    return mapa
