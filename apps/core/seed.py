from decimal import Decimal

from django.db import transaction

from apps.accounts.models import Pantalla, Rol, RolPantalla, Usuario
from apps.almacen.services.saldo_inicial import registrar_saldo_inicial
from apps.core.catalogo import (
    PERMISOS_POR_ROL,
    PANTALLAS,
    ROLES_DEMO,
    TIPOS_MATERIAL,
    USUARIOS_DEMO,
)
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    Cliente,
    Proceso,
    Proveedor,
    Maquina,
    MaquinaProceso,
    Receta,
    RecetaDetalle,
    Ruta,
    RutaProceso,
    SaldoInicial,
    TipoMaterial,
    Trabajador,
)
from apps.maestros.services.correlativos import asegurar_correlativos_anio

PROCESOS_EJEMPLO = [
    ('TEJ', 'Tejido'),
    ('TEN', 'Teñido'),
    ('COR', 'Corte'),
    ('COS', 'Costura'),
    ('ACA', 'Acabado'),
    ('SEC', 'Secado'),
    ('BLA', 'Blanqueo'),
    ('REV', 'Revisado'),
]

MAQUINAS_EJEMPLO = [
    ('MAQ-TELAR-01', 'Telar circular 1', 'Telar de punto para el polo piqué.', ('TEJ',)),
    ('MAQ-JIGGER-01', 'Jigger de teñido', 'Teñido y blanqueo de tela jersey.', ('TEN', 'BLA')),
    ('MAQ-LINEA-01', 'Línea polo', 'Acabado y secado del polo.', ('ACA', 'SEC')),
]


SALDOS_EJEMPLO = [
    ('ALM01', 'MP-HIL-20/1', Decimal('100'), Decimal('2')),
    ('ALM01', 'MP-TEL-JER', Decimal('250'), Decimal('4.5')),
    ('ALM01', 'AUX-BOT-14', Decimal('1000'), Decimal('0.05')),
    ('ALM01', 'ENV-BOL-P', Decimal('500'), Decimal('0.02')),
]


def seed_base():
    with transaction.atomic():
        asegurar_pantallas()
        asegurar_roles()
        asegurar_usuarios()
        asegurar_tipos()
        asegurar_anio()


def asegurar_pantallas():
    codigos = []
    for item in PANTALLAS:
        Pantalla.objects.update_or_create(
            codigo=item['codigo'],
            defaults={'nombre': item['nombre'], 'modulo': item['modulo']},
        )
        codigos.append(item['codigo'])
    Pantalla.objects.exclude(codigo__in=codigos).delete()


def asegurar_roles():
    for codigo, nombre in ROLES_DEMO:
        rol, _ = Rol.objects.update_or_create(codigo=codigo, defaults={'nombre': nombre, 'activo': True})
        mapa = PERMISOS_POR_ROL[codigo]
        pantallas = {p.codigo: p for p in Pantalla.objects.all()}
        RolPantalla.objects.filter(rol=rol).exclude(pantalla__codigo__in=mapa).delete()
        for codigo_pantalla, escribir in mapa.items():
            RolPantalla.objects.update_or_create(
                rol=rol,
                pantalla=pantallas[codigo_pantalla],
                defaults={'puede_escribir': escribir},
            )


def asegurar_usuarios():
    roles = {rol.codigo: rol for rol in Rol.objects.all()}
    for item in USUARIOS_DEMO:
        usuario, creado = Usuario.objects.get_or_create(
            username=item['username'],
            defaults={
                'nombres': item['nombres'],
                'email': item['email'],
                'rol': roles[item['rol']],
                'is_active': True,
            },
        )
        if creado:
            usuario.set_password(item['password'])
            usuario.save(update_fields=['password'])


def asegurar_tipos():
    for codigo, nombre in TIPOS_MATERIAL:
        TipoMaterial.objects.update_or_create(codigo=codigo, defaults={'nombre': nombre})


def asegurar_anio():
    anio, _ = Anio.objects.get_or_create(anio=2026, defaults={'activo': True, 'cerrado': False})
    if not anio.cerrado and not Anio.objects.filter(activo=True).exists():
        anio.activo = True
        anio.save()
    return anio


ALMACENES_EJEMPLO = [
    ('ALM01', 'Almacén de compras', False),
    ('ALM02', 'Materia prima', False),
    ('ALM03', 'Producto terminado', False),
    ('PROC01', 'En proceso tejido', True),
]

ARTICULOS_EJEMPLO = [
    ('MP-HIL-20/1', 'Hilo algodón 20/1 crudo', 'MP', 'kg'),
    ('MP-TEL-JER', 'Tela jersey 180 g/m²', 'MP', 'm'),
    ('AUX-BOT-14', 'Botón 14 mm blanco', 'AUX', 'und'),
    ('ENV-BOL-P', 'Bolsa polietileno polo', 'ENV', 'und'),
    ('PT-POL-PIQ-B', 'Polo piqué blanco M', 'PT', 'und'),
]

RECETA_LINEAS_EJEMPLO = (
    ('MP-HIL-20/1', Decimal('25')),
    ('MP-TEL-JER', Decimal('80')),
    ('AUX-BOT-14', Decimal('300')),
    ('ENV-BOL-P', Decimal('100')),
)

PASOS_RUTA_EJEMPLO = ('TEJ', 'TEN', 'COR', 'COS', 'ACA')


def catalogo_vacio():
    return not any([
        Articulo.objects.exists(),
        Almacen.objects.exists(),
        Cliente.objects.exists(),
        Proveedor.objects.exists(),
        Trabajador.objects.exists(),
        Proceso.objects.exists(),
        Ruta.objects.exists(),
        Receta.objects.exists(),
    ])


def seed_ejemplo():
    """Completa los datos de ejemplo que falten. No duplica ni pisa lo ya editado."""
    if not Usuario.objects.filter(username='maribel', is_active=True).exists():
        return False, 'Falta el usuario maribel. Ejecute primero: python manage.py seed_demo --solo-base'
    vacio = catalogo_vacio()
    with transaction.atomic():
        asegurar_tipos()
        anio = asegurar_anio()
        maestros_nuevos = _asegurar_maestros_ejemplo(anio)
        saldos_nuevos = _asegurar_saldos_ejemplo(anio)
        maquinas_nuevas = _asegurar_maquinas_ejemplo()
    if vacio:
        return True, (
            'Se cargaron los datos de ejemplo del taller textil: almacenes, artículos, '
            'receta, ruta, máquinas, terceros y saldos iniciales.'
        )
    if maquinas_nuevas and not maestros_nuevos and not saldos_nuevos:
        return True, 'Se agregaron las máquinas de ejemplo.'
    agregados = list(maestros_nuevos)
    if saldos_nuevos:
        agregados.append('saldos iniciales (' + ', '.join(saldos_nuevos) + ')')
    if maquinas_nuevas:
        agregados.append('máquinas')
    if agregados:
        return True, (
            'Se completaron datos de ejemplo que faltaban, sin duplicar: '
            + ', '.join(agregados) + '.'
        )
    return True, 'No faltaba ningún dato de ejemplo. No se duplicó nada.'


def _asegurar_maestros_ejemplo(anio):
    nuevos = []
    for codigo, nombre, es_proceso in ALMACENES_EJEMPLO:
        _almacen, creado = Almacen.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'es_proceso': es_proceso, 'activo': True},
        )
        if creado:
            nuevos.append(codigo)
    asegurar_correlativos_anio(anio)

    tipos = {t.codigo: t for t in TipoMaterial.objects.all()}
    articulos = {}
    for codigo, descripcion, tipo, um in ARTICULOS_EJEMPLO:
        articulo, creado = Articulo.objects.get_or_create(
            codigo=codigo,
            defaults={
                'descripcion': descripcion,
                'tipo_material': tipos[tipo],
                'unidad_medida': um,
                'activo': True,
            },
        )
        articulos[codigo] = articulo
        if creado:
            nuevos.append(codigo)

    pt = articulos['PT-POL-PIQ-B']
    if pt.tipo_material.codigo == 'PT':
        receta, creada = Receta.objects.get_or_create(
            articulo_pt=pt,
            defaults={'lote_base': Decimal('100'), 'activo': True},
        )
        if creada:
            nuevos.append('receta')
        if creada or not receta.detalles.exists():
            for codigo, cantidad in RECETA_LINEAS_EJEMPLO:
                insumo = articulos[codigo]
                if insumo.pk == pt.pk:
                    continue
                RecetaDetalle.objects.get_or_create(
                    receta=receta,
                    articulo_insumo=insumo,
                    defaults={'cantidad_por_lote': cantidad},
                )

    for codigo, nombre in PROCESOS_EJEMPLO:
        _proceso, creado = Proceso.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'activo': True},
        )
        if creado:
            nuevos.append(codigo)

    ruta, ruta_creada = Ruta.objects.get_or_create(
        codigo='RUTA-POLO-01',
        defaults={'nombre': 'Polo básico', 'activo': True},
    )
    if ruta_creada:
        nuevos.append('RUTA-POLO-01')
    if ruta_creada or not ruta.pasos.exists():
        procesos = {p.codigo: p for p in Proceso.objects.filter(codigo__in=PASOS_RUTA_EJEMPLO)}
        for secuencia, codigo in enumerate(PASOS_RUTA_EJEMPLO, start=1):
            RutaProceso.objects.get_or_create(
                ruta=ruta,
                secuencia=secuencia,
                defaults={'proceso': procesos[codigo]},
            )

    _cliente, creado = Cliente.objects.get_or_create(
        codigo='CLI-001',
        defaults={
            'ruc_documento': '20555111222',
            'razon_social': 'Textiles Lima S.A.C.',
            'activo': True,
        },
    )
    if creado:
        nuevos.append('CLI-001')
    _proveedor, creado = Proveedor.objects.get_or_create(
        codigo='PROV-001',
        defaults={
            'ruc_documento': '20123456789',
            'razon_social': 'Hilos del Sur S.A.C.',
            'activo': True,
        },
    )
    if creado:
        nuevos.append('PROV-001')
    _trabajador, creado = Trabajador.objects.get_or_create(
        codigo='TR-001',
        defaults={
            'nombres': 'Juan Pérez',
            'tipo_documento': Trabajador.DNI,
            'numero_documento': '12345678',
            'activo': True,
        },
    )
    if creado:
        nuevos.append('TR-001')
    return nuevos


def _asegurar_saldos_ejemplo(anio):
    if anio.cerrado:
        return []
    usuario = Usuario.objects.get(username='maribel')
    nuevos = []
    for codigo_alm, codigo_art, cantidad, costo in SALDOS_EJEMPLO:
        almacen = Almacen.objects.filter(codigo=codigo_alm).first()
        articulo = Articulo.objects.filter(codigo=codigo_art).first()
        if almacen is None or articulo is None:
            continue
        if SaldoInicial.objects.filter(anio=anio, almacen=almacen, articulo=articulo).exists():
            continue
        registrar_saldo_inicial(
            anio=anio,
            almacen=almacen,
            articulo=articulo,
            cantidad=cantidad,
            costo_unitario=costo,
            usuario=usuario,
        )
        nuevos.append(f'{codigo_alm}:{codigo_art}')
    return nuevos


def _asegurar_maquinas_ejemplo():
    """Crea las máquinas de ejemplo si no existen. No duplica ni pisa asignaciones ya hechas."""
    procesos = {}
    for codigo, nombre in PROCESOS_EJEMPLO:
        proceso, _creado = Proceso.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'activo': True},
        )
        procesos[codigo] = proceso
    nuevas = False
    for codigo, nombre, descripcion, codigos_proceso in MAQUINAS_EJEMPLO:
        maquina, creada = Maquina.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'descripcion': descripcion, 'activo': True},
        )
        if not creada and maquina.asignaciones.exists():
            continue
        for codigo_proceso in codigos_proceso:
            MaquinaProceso.objects.get_or_create(maquina=maquina, proceso=procesos[codigo_proceso])
        nuevas = True
    return nuevas
