from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import get_resolver, reverse

from apps.accounts.models import Rol, RolPantalla, Usuario
from apps.almacen.models import Kardex, Movimiento, StockActual
from apps.almacen.services.numeracion import next_op
from apps.almacen.services.saldo_inicial import registrar_saldo_inicial
from apps.core.authz import RUTAS_SIN_PANTALLA, codigo_de_vista
from apps.core.catalogo import PERMISOS_POR_ROL, PANTALLAS, TIPOS_MATERIAL, USUARIOS_DEMO
from apps.core.seed import seed_base, seed_ejemplo
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    Cliente,
    CorrelativoNota,
    CorrelativoOp,
    Proceso,
    Proveedor,
    Receta,
    Ruta,
    SaldoInicial,
    TipoMaterial,
)
from apps.maestros.services.cierre_anio import cerrar


def entrar(username, password):
    cliente = Client()
    ok = cliente.login(username=username, password=password)
    return cliente, ok


class TestFase1(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_login_de_los_cuatro_usuarios(self):
        for item in USUARIOS_DEMO:
            cliente, ok = entrar(item['username'], item['password'])
            self.assertTrue(ok, item['username'])
            respuesta = cliente.get(reverse('home'))
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, item['nombres'])

    def test_login_muestra_cuentas_de_la_demo(self):
        respuesta = Client().get(reverse('login'))
        self.assertEqual(respuesta.status_code, 200)
        for item in USUARIOS_DEMO:
            self.assertContains(respuesta, item['username'])
            self.assertContains(respuesta, item['password'])

    def test_clave_incorrecta_y_usuario_inactivo_usan_el_mismo_mensaje(self):
        respuesta = Client().post(reverse('login'), {'username': 'maribel', 'password': 'no-es'})
        self.assertContains(respuesta, 'Usuario o contraseña incorrectos.')
        self.assertNotContains(respuesta, 'inactivo')

        usuario = Usuario.objects.get(username='consulta')
        usuario.is_active = False
        usuario.save(update_fields=['is_active'])
        cliente, ok = entrar('consulta', 'demo-consulta')
        self.assertFalse(ok)
        respuesta = Client().post(reverse('login'), {'username': 'consulta', 'password': 'demo-consulta'})
        self.assertContains(respuesta, 'Usuario o contraseña incorrectos.')
        self.assertNotContains(respuesta, 'inactivo')

    def test_consulta_no_ve_ingreso_y_el_post_responde_403(self):
        cliente, _ok = entrar('consulta', 'demo-consulta')
        inicio = cliente.get(reverse('home'))
        self.assertNotContains(inicio, '/almacen/ingreso/')
        self.assertContains(inicio, '/reportes/stock/')
        self.assertContains(inicio, '/reportes/kardex/')
        self.assertContains(inicio, '/reportes/bom-ruta/')

        denegado = cliente.post(reverse('alm.ingreso'), {})
        self.assertContains(denegado, 'No tienes permiso para esta acción.', status_code=403)
        lectura = cliente.get(reverse('alm.ingreso'))
        self.assertEqual(lectura.status_code, 403)

        stock = cliente.get(reverse('rep.stock'))
        self.assertContains(stock, 'fase posterior')
        self.assertContains(stock, 'Stock')

    def test_admin_entra_a_ingreso_como_fase_posterior(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        inicio = cliente.get(reverse('home'))
        self.assertContains(inicio, '/almacen/ingreso/')
        respuesta = cliente.get(reverse('alm.ingreso'))
        self.assertContains(respuesta, 'fase posterior')

    def test_almacenero_consulta_articulos_sin_poder_crearlos(self):
        cliente, _ok = entrar('almacenero', 'demo-alm')
        lista = cliente.get(reverse('mae.articulos'))
        self.assertEqual(lista.status_code, 200)
        self.assertNotContains(lista, '>Nuevo<')
        self.assertEqual(cliente.get(reverse('admin.usuarios')).status_code, 403)
        alta = cliente.post(reverse('mae.articulos_nueva'), {
            'codigo': 'MP-NUEVO',
            'descripcion': 'No debería guardarse',
            'tipo_material': TipoMaterial.objects.get(codigo='MP').pk,
            'unidad_medida': 'kg',
            'activo': 'on',
        })
        self.assertEqual(alta.status_code, 403)
        self.assertFalse(Articulo.objects.filter(codigo='MP-NUEVO').exists())

    def test_jefe_ve_recetas_y_no_usuarios_ni_ingreso(self):
        cliente, _ok = entrar('jefeprod', 'demo-prod')
        self.assertEqual(cliente.get(reverse('mae.recetas')).status_code, 200)
        self.assertEqual(cliente.get(reverse('admin.usuarios')).status_code, 403)
        self.assertEqual(cliente.get(reverse('alm.ingreso')).status_code, 403)
        self.assertNotContains(cliente.get(reverse('home')), '/almacen/ingreso/')

    def test_permisos_de_la_semilla(self):
        for codigo, mapa in PERMISOS_POR_ROL.items():
            rol = Rol.objects.get(codigo=codigo)
            actual = {
                fila.pantalla.codigo: fila.puede_escribir
                for fila in RolPantalla.objects.filter(rol=rol).select_related('pantalla')
            }
            self.assertEqual(actual, mapa, codigo)
        self.assertEqual(
            {item['codigo'] for item in PANTALLAS},
            set(Rol.objects.get(codigo='ADMIN').pantallas.values_list('pantalla__codigo', flat=True)),
        )

    def test_toda_ruta_declara_pantalla_o_es_publica(self):
        def recorrer(patrones):
            for patron in patrones:
                if hasattr(patron, 'url_patterns'):
                    yield from recorrer(patron.url_patterns)
                else:
                    yield patron

        for patron in recorrer(get_resolver().url_patterns):
            if patron.name in RUTAS_SIN_PANTALLA:
                continue
            self.assertTrue(patron.name)
            self.assertTrue(codigo_de_vista(patron.callback), patron.name)

    def test_tipos_fijos_sin_pantalla_de_alta(self):
        self.assertEqual(
            set(TipoMaterial.objects.values_list('codigo', 'nombre')),
            set(TIPOS_MATERIAL),
        )
        cliente, _ok = entrar('maribel', 'demo-admin')
        pagina = cliente.get(reverse('mae.articulos'))
        self.assertContains(pagina, 'solo consulta')
        self.assertContains(pagina, 'Materia prima')
        self.assertEqual(cliente.get('/maestros/tipos/nuevo/').status_code, 404)

    def test_semilla_de_anio_almacen_receta_y_ruta(self):
        anio = Anio.objects.get(anio=2026)
        self.assertTrue(anio.activo)
        self.assertFalse(anio.cerrado)
        self.assertTrue(Almacen.objects.get(codigo='PROC01').es_proceso)
        self.assertFalse(Almacen.objects.get(codigo='ALM01').es_proceso)
        receta = Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B')
        self.assertEqual(receta.lote_base, Decimal('100.0000'))
        self.assertEqual(receta.detalles.count(), 4)
        self.assertFalse(any(campo.name in {'articulo', 'articulo_pt', 'producto'} for campo in Ruta._meta.fields))
        self.assertEqual(Ruta.objects.get(codigo='RUTA-POLO-01').pasos.count(), 5)
        self.assertEqual(CorrelativoOp.objects.get(anio=anio).ultimo, 0)
        self.assertEqual(CorrelativoNota.objects.get(anio=anio, almacen__codigo='PROC01').ultimo, 0)
        self.assertEqual(CorrelativoNota.objects.get(anio=anio, almacen__codigo='ALM02').ultimo, 0)
        self.assertEqual(CorrelativoNota.objects.get(anio=anio, almacen__codigo='ALM01').ultimo, 4)
        self.assertEqual(Cliente.objects.get(codigo='CLI-001').razon_social, 'Textiles Lima S.A.C.')
        self.assertEqual(Proveedor.objects.get(codigo='PROV-001').razon_social, 'Hilos del Sur S.A.C.')
        self.assertFalse(Proveedor.objects.filter(codigo='CLI-001').exists())

    def test_crear_pt_receta_lote_100_y_ruta_sin_producto(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        tipo_pt = TipoMaterial.objects.get(codigo='PT')
        alta = cliente.post(reverse('mae.articulos_nueva'), {
            'codigo': 'pt-demo-2',
            'descripcion': 'Polo demo prueba',
            'tipo_material': tipo_pt.pk,
            'unidad_medida': 'und',
            'activo': 'on',
        })
        self.assertEqual(alta.status_code, 302, alta.content.decode()[:1500])
        articulo = Articulo.objects.get(codigo='PT-DEMO-2')
        insumo = Articulo.objects.get(codigo='MP-HIL-20/1')
        receta = cliente.post(reverse('mae.recetas_nueva'), {
            'articulo_pt': articulo.pk,
            'lote_base': '100',
            'activo': 'on',
            'detalles-TOTAL_FORMS': '1',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-articulo_insumo': insumo.pk,
            'detalles-0-cantidad_por_lote': '25',
            'detalles-0-id': '',
        })
        self.assertEqual(receta.status_code, 302, receta.content.decode()[:1500])
        guardada = Receta.objects.get(articulo_pt=articulo)
        self.assertEqual(guardada.lote_base, Decimal('100.0000'))
        self.assertEqual(guardada.detalles.get().cantidad_por_lote, Decimal('25.0000'))

        pagina = cliente.get(reverse('mae.rutas_nueva'))
        self.assertEqual(list(pagina.context['form'].fields), ['codigo', 'nombre', 'activo'])
        proceso = Proceso.objects.get(codigo='TEJ')
        ruta = cliente.post(reverse('mae.rutas_nueva'), {
            'codigo': 'ruta-test-01',
            'nombre': 'Ruta de prueba',
            'activo': 'on',
            'pasos-TOTAL_FORMS': '1',
            'pasos-INITIAL_FORMS': '0',
            'pasos-MIN_NUM_FORMS': '0',
            'pasos-MAX_NUM_FORMS': '1000',
            'pasos-0-secuencia': '1',
            'pasos-0-proceso': proceso.pk,
            'pasos-0-id': '',
        })
        self.assertEqual(ruta.status_code, 302, ruta.content.decode()[:1500])
        creada = Ruta.objects.get(codigo='RUTA-TEST-01')
        self.assertEqual(creada.pasos.get().proceso_id, proceso.pk)

    def test_receta_rechaza_lote_cero_linea_vacia_e_insumo_igual_al_pt(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        tipo_pt = TipoMaterial.objects.get(codigo='PT')
        cliente.post(reverse('mae.articulos_nueva'), {
            'codigo': 'PT-VALIDA',
            'descripcion': 'PT validación',
            'tipo_material': tipo_pt.pk,
            'unidad_medida': 'und',
            'activo': 'on',
        })
        articulo = Articulo.objects.get(codigo='PT-VALIDA')
        base = {
            'articulo_pt': articulo.pk,
            'activo': 'on',
            'detalles-TOTAL_FORMS': '1',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-id': '',
        }
        vacia = cliente.post(reverse('mae.recetas_nueva'), {
            **base,
            'lote_base': '100',
            'detalles-0-articulo_insumo': '',
            'detalles-0-cantidad_por_lote': '',
        })
        self.assertContains(vacia, 'al menos un insumo')
        self.assertFalse(Receta.objects.filter(articulo_pt=articulo).exists())

        lote = cliente.post(reverse('mae.recetas_nueva'), {
            **base,
            'lote_base': '0',
            'detalles-0-articulo_insumo': Articulo.objects.get(codigo='MP-HIL-20/1').pk,
            'detalles-0-cantidad_por_lote': '1',
        })
        self.assertContains(lote, 'mayor que cero')

        mismo = cliente.post(reverse('mae.recetas_nueva'), {
            **base,
            'lote_base': '100',
            'detalles-0-articulo_insumo': articulo.pk,
            'detalles-0-cantidad_por_lote': '1',
        })
        self.assertContains(mismo, 'no puede ser el mismo producto terminado')
        self.assertFalse(Receta.objects.filter(articulo_pt=articulo).exists())

    def test_ruta_rechaza_secuencia_repetida(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        tej = Proceso.objects.get(codigo='TEJ')
        ten = Proceso.objects.get(codigo='TEN')
        respuesta = cliente.post(reverse('mae.rutas_nueva'), {
            'codigo': 'RUTA-REPETIDA',
            'nombre': 'Secuencias repetidas',
            'activo': 'on',
            'pasos-TOTAL_FORMS': '2',
            'pasos-INITIAL_FORMS': '0',
            'pasos-MIN_NUM_FORMS': '0',
            'pasos-MAX_NUM_FORMS': '1000',
            'pasos-0-secuencia': '1',
            'pasos-0-proceso': tej.pk,
            'pasos-0-id': '',
            'pasos-1-secuencia': '1',
            'pasos-1-proceso': ten.pk,
            'pasos-1-id': '',
        })
        self.assertContains(respuesta, 'repetida')
        self.assertFalse(Ruta.objects.filter(codigo='RUTA-REPETIDA').exists())

    def test_codigo_de_almacen_unico_y_proceso(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        antes = Almacen.objects.count()
        duplicado = cliente.post(reverse('mae.almacenes_nueva'), {
            'codigo': 'alm01',
            'nombre': 'Duplicado',
            'activo': 'on',
        })
        self.assertEqual(duplicado.status_code, 200)
        self.assertEqual(Almacen.objects.count(), antes)
        self.assertContains(duplicado, 'Ya existe un almacén')

        creado = cliente.post(reverse('mae.almacenes_nueva'), {
            'codigo': 'proc02',
            'nombre': 'En proceso costura',
            'es_proceso': 'on',
            'activo': 'on',
        })
        self.assertEqual(creado.status_code, 302, creado.content.decode()[:1500])
        almacen = Almacen.objects.get(codigo='PROC02')
        self.assertTrue(almacen.es_proceso)

    def test_no_desactiva_almacen_con_stock(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        almacen = Almacen.objects.get(codigo='ALM01')
        respuesta = cliente.post(reverse('mae.almacenes_editar', args=[almacen.pk]), {
            'codigo': 'ALM01',
            'nombre': almacen.nombre,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'stock')
        almacen.refresh_from_db()
        self.assertTrue(almacen.activo)

    def test_saldo_inicial_valorizado_con_nota_y_kardex(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        cliente.post(reverse('mae.almacenes_nueva'), {
            'codigo': 'ALMX',
            'nombre': 'Almacén prueba',
            'activo': 'on',
        })
        almacen = Almacen.objects.get(codigo='ALMX')
        anio = Anio.objects.get(anio=2026)
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        tela = Articulo.objects.get(codigo='MP-TEL-JER')
        primero = cliente.post(reverse('admin.saldo_inicial'), {
            'anio': anio.pk,
            'almacen': almacen.pk,
            'articulo': hilo.pk,
            'cantidad': '10,5',
            'costo_unitario': '2',
        })
        self.assertEqual(primero.status_code, 302, primero.content.decode()[:1500])
        saldo = SaldoInicial.objects.get(anio=anio, almacen=almacen, articulo=hilo)
        self.assertEqual(saldo.cantidad, Decimal('10.5000'))
        self.assertEqual(saldo.costo_promedio, Decimal('2.0000'))
        self.assertEqual(saldo.valor, Decimal('21.0000'))
        nota = Movimiento.objects.get(numero_nota='ALMX-2026-000001')
        self.assertEqual(nota.tipo, Movimiento.SALDO_INICIAL)
        self.assertEqual(nota.fecha.year, 2026)
        self.assertIsNone(nota.proveedor_id)
        kardex = Kardex.objects.get(numero_nota='ALMX-2026-000001')
        self.assertEqual(kardex.cantidad_entrada, Decimal('10.5000'))
        self.assertEqual(kardex.saldo_cantidad, Decimal('10.5000'))
        self.assertEqual(kardex.saldo_valor, Decimal('21.0000'))
        self.assertEqual(kardex.costo_unit_promedio, Decimal('2.0000'))
        self.assertFalse(kardex.es_revalorizacion)
        stock = StockActual.objects.get(anio=anio, almacen=almacen, articulo=hilo)
        self.assertEqual(stock.ultima_nota, 'ALMX-2026-000001')
        self.assertEqual(stock.valor, Decimal('21.0000'))

        cliente.post(reverse('admin.saldo_inicial'), {
            'anio': anio.pk,
            'almacen': almacen.pk,
            'articulo': tela.pk,
            'cantidad': '3',
            'costo_unitario': '1.5',
        })
        self.assertTrue(Movimiento.objects.filter(numero_nota='ALMX-2026-000002').exists())
        repetido = cliente.post(reverse('admin.saldo_inicial'), {
            'anio': anio.pk,
            'almacen': almacen.pk,
            'articulo': hilo.pk,
            'cantidad': '1',
            'costo_unitario': '1',
        })
        self.assertContains(repetido, 'Ya existe un saldo inicial')
        self.assertEqual(SaldoInicial.objects.filter(anio=anio, almacen=almacen, articulo=hilo).count(), 1)

    def test_numeracion_de_op(self):
        anio = Anio.objects.get(anio=2026)
        self.assertEqual(next_op(anio), 'OP-2026-0001')
        self.assertEqual(next_op(anio), 'OP-2026-0002')

    def test_cierre_copia_saldo_y_bloquea_el_anio(self):
        anio = Anio.objects.get(anio=2026)
        stocks = list(StockActual.objects.filter(anio=anio))
        self.assertGreaterEqual(len(stocks), 1)
        cliente, _ok = entrar('maribel', 'demo-admin')
        respuesta = cliente.post(reverse('admin.anios_cerrar', args=[anio.pk]), follow=True)
        self.assertContains(respuesta, 'cerrado')
        anio.refresh_from_db()
        self.assertTrue(anio.cerrado)
        self.assertFalse(anio.activo)
        self.assertIsNotNone(anio.fecha_cierre)
        siguiente = Anio.objects.get(anio=2027)
        self.assertTrue(siguiente.activo)
        self.assertFalse(siguiente.cerrado)
        for stock in stocks:
            saldo = SaldoInicial.objects.get(anio=siguiente, almacen=stock.almacen, articulo=stock.articulo)
            self.assertEqual(saldo.cantidad, stock.cantidad)
            self.assertEqual(saldo.costo_promedio, stock.costo_promedio)
            self.assertEqual(saldo.valor, stock.valor)
        self.assertEqual(
            CorrelativoNota.objects.get(anio=siguiente, almacen__codigo='ALM01').ultimo,
            len(stocks),
        )
        otra = cliente.post(reverse('admin.anios_cerrar', args=[anio.pk]), follow=True)
        self.assertContains(otra, 'ya está cerrado')
        self.assertEqual(SaldoInicial.objects.filter(anio=siguiente).count(), len(stocks))

        hilo = Articulo.objects.get(codigo='AUX-BOT-14')
        respuesta_saldo = cliente.post(reverse('admin.saldo_inicial'), {
            'anio': anio.pk,
            'almacen': Almacen.objects.get(codigo='ALM02').pk,
            'articulo': hilo.pk,
            'cantidad': '1',
            'costo_unitario': '1',
        })
        self.assertContains(respuesta_saldo, 'cerrado')
        self.assertFalse(SaldoInicial.objects.filter(anio=anio, almacen__codigo='ALM02', articulo=hilo).exists())
        with self.assertRaises(ValidationError):
            registrar_saldo_inicial(
                anio=anio,
                almacen=Almacen.objects.get(codigo='ALM02'),
                articulo=hilo,
                cantidad=Decimal('1'),
                costo_unitario=Decimal('1'),
                usuario=Usuario.objects.get(username='maribel'),
            )

    def test_cierre_revierte_si_el_anio_siguiente_ya_tiene_el_saldo(self):
        anio = Anio.objects.get(anio=2026)
        siguiente = Anio.objects.create(anio=2027, activo=False, cerrado=False)
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        almacen = Almacen.objects.get(codigo='ALM01')
        registrar_saldo_inicial(
            anio=siguiente,
            almacen=almacen,
            articulo=hilo,
            cantidad=Decimal('1'),
            costo_unitario=Decimal('1'),
            usuario=Usuario.objects.get(username='maribel'),
        )
        with self.assertRaises(ValidationError):
            cerrar(anio.pk, Usuario.objects.get(username='maribel'))
        anio.refresh_from_db()
        self.assertFalse(anio.cerrado)

    def test_ultimo_admin_y_rol_con_usuarios(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        admin = Usuario.objects.get(username='maribel')
        consulta = Rol.objects.get(codigo='CONSULTA')
        respuesta = cliente.post(reverse('admin.usuarios_editar', args=[admin.pk]), {
            'username': 'maribel',
            'nombres': 'Maribel Cano',
            'email': admin.email,
            'rol': consulta.pk,
            'is_active': 'on',
            'password1': '',
            'password2': '',
        })
        self.assertContains(respuesta, 'al menos un usuario Admin activo')
        admin.refresh_from_db()
        self.assertEqual(admin.rol.codigo, 'ADMIN')
        self.assertTrue(admin.is_active)

        rol = Rol.objects.get(codigo='CONSULTA')
        bloqueado = cliente.post(reverse('admin.roles_eliminar', args=[rol.pk]), follow=True)
        self.assertContains(bloqueado, 'tiene usuarios asignados')
        self.assertTrue(Rol.objects.filter(pk=rol.pk).exists())
        admin_rol = Rol.objects.get(codigo='ADMIN')
        protegido = cliente.post(reverse('admin.roles_eliminar', args=[admin_rol.pk]), follow=True)
        self.assertContains(protegido, 'No se puede eliminar el rol Admin')

        nuevo = cliente.post(reverse('admin.roles_nueva'), {
            'codigo': 'temp',
            'nombre': 'Temporal',
            'activo': 'on',
        })
        self.assertEqual(nuevo.status_code, 302, nuevo.content.decode()[:1500])
        temporal = Rol.objects.get(codigo='TEMP')
        cliente.post(reverse('admin.roles_eliminar', args=[temporal.pk]))
        self.assertFalse(Rol.objects.filter(codigo='TEMP').exists())

    def test_checklist_actualiza_el_menu_del_rol(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        rol = Rol.objects.get(codigo='CONSULTA')
        stock = RolPantalla.objects.get(rol=rol, pantalla__codigo='rep.stock').pantalla
        cliente.post(reverse('admin.rol_pantallas_editar', args=[rol.pk]), {'ver': [str(stock.pk)]})
        consulta, _ok = entrar('consulta', 'demo-consulta')
        self.assertEqual(consulta.get(reverse('rep.stock')).status_code, 200)
        self.assertEqual(consulta.get(reverse('rep.kardex')).status_code, 403)

        admin = Rol.objects.get(codigo='ADMIN')
        cliente.post(reverse('admin.rol_pantallas_editar', args=[admin.pk]), {})
        self.assertEqual(cliente.get(reverse('admin.usuarios')).status_code, 200)
        self.assertEqual(cliente.get(reverse('mae.articulos')).status_code, 403)

    def test_alta_de_usuario_con_clave(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        rol = Rol.objects.get(codigo='CONSULTA')
        respuesta = cliente.post(reverse('admin.usuarios_nueva'), {
            'username': 'supervisor1',
            'nombres': 'Supervisor de turno',
            'email': 'sup@ejemplo.local',
            'rol': rol.pk,
            'is_active': 'on',
            'password1': 'Clave-demo-99',
            'password2': 'Clave-demo-99',
        })
        self.assertEqual(respuesta.status_code, 302, respuesta.content.decode()[:1500])
        nuevo, ok = entrar('supervisor1', 'Clave-demo-99')
        self.assertTrue(ok)
        self.assertEqual(nuevo.get(reverse('rep.stock')).status_code, 200)


class TestCargaEjemplo(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()

    def test_boton_carga_una_vez_si_los_maestros_estan_vacios(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        self.assertFalse(Articulo.objects.exists())
        primera = cliente.post(reverse('datos_ejemplo'), follow=True)
        self.assertContains(primera, 'Se cargaron los datos de ejemplo')
        self.assertEqual(Articulo.objects.count(), 5)
        self.assertEqual(Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B').lote_base, Decimal('100.0000'))
        self.assertTrue(Almacen.objects.get(codigo='PROC01').es_proceso)
        self.assertEqual(SaldoInicial.objects.filter(anio__anio=2026).count(), 4)
        self.assertTrue(Kardex.objects.filter(tipo_mov='SALDO_INICIAL').exists())
        segunda = cliente.post(reverse('datos_ejemplo'), follow=True)
        self.assertContains(segunda, 'ya tiene maestros')
        self.assertEqual(Articulo.objects.count(), 5)

        consulta, _ok = entrar('consulta', 'demo-consulta')
        self.assertEqual(consulta.post(reverse('datos_ejemplo'), {}).status_code, 403)
