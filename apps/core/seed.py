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
    CorrelativoNota,
    CorrelativoOp,
    Proceso,
    Proveedor,
    Maquina,
    MaquinaProceso,
    Receta,
    RecetaDetalle,
    Ruta,
    RutaProceso,
    TipoMaterial,
    Trabajador,
)

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
    if catalogo_vacio() and not Usuario.objects.filter(username='maribel', is_active=True).exists():
        return False, 'Falta el usuario maribel. Ejecute primero: python manage.py seed_demo --solo-base'
    cargo_catalogo = False
    if catalogo_vacio():
        with transaction.atomic():
            asegurar_tipos()
            anio = asegurar_anio()
            _crear_maestros_ejemplo(anio)
            _crear_saldos_ejemplo(anio)
        cargo_catalogo = True
    with transaction.atomic():
        maquinas_nuevas = _asegurar_maquinas_ejemplo()
    if cargo_catalogo:
        return True, (
            'Se cargaron los datos de ejemplo del taller textil: almacenes, artículos, '
            'receta, ruta, máquinas, terceros y saldos iniciales.'
        )
    if maquinas_nuevas:
        return True, 'Se agregaron las máquinas de ejemplo.'
    return False, 'La base ya tiene maestros. No se cargaron datos de ejemplo.'


def _crear_maestros_ejemplo(anio):
    almacenes = [
        ('ALM01', 'Almacén de compras', False),
        ('ALM02', 'Materia prima', False),
        ('ALM03', 'Producto terminado', False),
        ('PROC01', 'En proceso tejido', True),
    ]
    alm = {}
    for codigo, nombre, proceso in almacenes:
        alm[codigo] = Almacen.objects.create(codigo=codigo, nombre=nombre, es_proceso=proceso, activo=True)
        CorrelativoNota.objects.get_or_create(anio=anio, almacen=alm[codigo], defaults={'ultimo': 0})
    CorrelativoOp.objects.get_or_create(anio=anio, defaults={'ultimo': 0})

    tipos = {t.codigo: t for t in TipoMaterial.objects.all()}
    articulos = [
        ('MP-HIL-20/1', 'Hilo algodón 20/1 crudo', 'MP', 'kg'),
        ('MP-TEL-JER', 'Tela jersey 180 g/m²', 'MP', 'm'),
        ('AUX-BOT-14', 'Botón 14 mm blanco', 'AUX', 'und'),
        ('ENV-BOL-P', 'Bolsa polietileno polo', 'ENV', 'und'),
        ('PT-POL-PIQ-B', 'Polo piqué blanco M', 'PT', 'und'),
    ]
    art = {}
    for codigo, descripcion, tipo, um in articulos:
        art[codigo] = Articulo.objects.create(
            codigo=codigo,
            descripcion=descripcion,
            tipo_material=tipos[tipo],
            unidad_medida=um,
            activo=True,
        )

    receta = Receta.objects.create(articulo_pt=art['PT-POL-PIQ-B'], lote_base=Decimal('100'), activo=True)
    for codigo, cantidad in (
        ('MP-HIL-20/1', Decimal('25')),
        ('MP-TEL-JER', Decimal('80')),
        ('AUX-BOT-14', Decimal('300')),
        ('ENV-BOL-P', Decimal('100')),
    ):
        RecetaDetalle.objects.create(receta=receta, articulo_insumo=art[codigo], cantidad_por_lote=cantidad)

    for codigo, nombre in PROCESOS_EJEMPLO:
        Proceso.objects.create(codigo=codigo, nombre=nombre, activo=True)
    ruta = Ruta.objects.create(codigo='RUTA-POLO-01', nombre='Polo básico', activo=True)
    procesos_ruta = {p.codigo: p for p in Proceso.objects.filter(codigo__in=('TEJ', 'TEN', 'COR', 'COS', 'ACA'))}
    for secuencia, codigo in enumerate(('TEJ', 'TEN', 'COR', 'COS', 'ACA'), start=1):
        RutaProceso.objects.create(ruta=ruta, proceso=procesos_ruta[codigo], secuencia=secuencia)

    Cliente.objects.create(
        codigo='CLI-001',
        ruc_documento='20555111222',
        razon_social='Textiles Lima S.A.C.',
        activo=True,
    )
    Proveedor.objects.create(
        codigo='PROV-001',
        ruc_documento='20123456789',
        razon_social='Hilos del Sur S.A.C.',
        activo=True,
    )
    Trabajador.objects.create(
        codigo='TR-001',
        nombres='Juan Pérez',
        tipo_documento=Trabajador.DNI,
        numero_documento='12345678',
        activo=True,
    )


def _crear_saldos_ejemplo(anio):
    usuario = Usuario.objects.get(username='maribel')
    for codigo_alm, codigo_art, cantidad, costo in SALDOS_EJEMPLO:
        registrar_saldo_inicial(
            anio=anio,
            almacen=Almacen.objects.get(codigo=codigo_alm),
            articulo=Articulo.objects.get(codigo=codigo_art),
            cantidad=cantidad,
            costo_unitario=costo,
            usuario=usuario,
        )


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
