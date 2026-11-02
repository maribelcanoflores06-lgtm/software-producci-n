from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.almacen.models import Kardex
from apps.core.seed import seed_base, seed_ejemplo
from apps.core.tests.test_fase1 import entrar
from apps.maestros.models import (
    Almacen,
    Anio,
    Articulo,
    CorrelativoNota,
    CorrelativoOp,
    Proceso,
    Receta,
    Ruta,
    RutaProceso,
    SaldoInicial,
    TipoMaterial,
    Trabajador,
)
from apps.maestros.services.correlativos import asegurar_correlativos_anio
from apps.maestros.services.maquinas import maquinas_que_pueden


class TestAceptacionFase2(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_criterios_de_la_fase(self):
        anio = Anio.objects.get(anio=2026)
        self.assertTrue(anio.activo)
        self.assertFalse(anio.cerrado)
        self.assertTrue(Almacen.objects.get(codigo='PROC01').es_proceso)
        self.assertEqual(CorrelativoOp.objects.get(anio=anio).ultimo, 0)
        self.assertEqual(CorrelativoNota.objects.get(anio=anio, almacen__codigo='PROC01').ultimo, 0)

        receta = Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B')
        self.assertEqual(receta.lote_base, Decimal('100.0000'))
        self.assertGreaterEqual(receta.detalles.count(), 1)
        self.assertFalse(any(campo.name in {'articulo', 'articulo_pt', 'producto', 'maquina'} for campo in Ruta._meta.fields))
        self.assertFalse(any(campo.name == 'maquina' for campo in RutaProceso._meta.fields))

        cliente, _ok = entrar('maribel', 'demo-admin')
        tipo_pt = TipoMaterial.objects.get(codigo='PT')
        alta = cliente.post(reverse('mae.articulos_nueva'), {
            'codigo': 'pt-fase2',
            'descripcion': 'Polo fase 2',
            'tipo_material': tipo_pt.pk,
            'unidad_medida': 'und',
            'activo': 'on',
        })
        self.assertEqual(alta.status_code, 302, alta.content.decode()[:800])
        articulo = Articulo.objects.get(codigo='PT-FASE2')
        insumo = Articulo.objects.get(codigo='MP-HIL-20/1')
        receta_nueva = cliente.post(reverse('mae.recetas_nueva'), {
            'articulo_pt': articulo.pk,
            'lote_base': '100',
            'activo': 'on',
            'detalles-TOTAL_FORMS': '1',
            'detalles-INITIAL_FORMS': '0',
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
            'detalles-0-articulo_insumo': insumo.pk,
            'detalles-0-cantidad_por_lote': '10',
            'detalles-0-id': '',
        })
        self.assertEqual(receta_nueva.status_code, 302, receta_nueva.content.decode()[:800])
        self.assertEqual(Receta.objects.get(articulo_pt=articulo).lote_base, Decimal('100.0000'))

        duplicado = cliente.post(reverse('mae.almacenes_nueva'), {
            'codigo': 'proc01',
            'nombre': 'Otro proceso',
            'es_proceso': 'on',
            'activo': 'on',
        })
        self.assertContains(duplicado, 'Ya existe un almacén')
        self.assertEqual(Almacen.objects.filter(codigo='PROC01').count(), 1)

    def test_alta_de_anio_y_almacen_dejan_correlativos_en_cero(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        anios = cliente.post(reverse('admin.anios_nueva'), {'anio': '2031'})
        self.assertEqual(anios.status_code, 302, anios.content.decode()[:800])
        anio = Anio.objects.get(anio=2031)
        self.assertEqual(CorrelativoOp.objects.get(anio=anio).ultimo, 0)
        self.assertEqual(
            CorrelativoNota.objects.filter(anio=anio, ultimo=0).count(),
            Almacen.objects.count(),
        )
        self.assertTrue(Anio.objects.get(anio=2026).activo)

        creado = cliente.post(reverse('mae.almacenes_nueva'), {
            'codigo': 'proc09',
            'nombre': 'En proceso acabado',
            'es_proceso': 'on',
            'activo': 'on',
        })
        self.assertEqual(creado.status_code, 302, creado.content.decode()[:800])
        almacen = Almacen.objects.get(codigo='PROC09')
        self.assertEqual(
            CorrelativoNota.objects.filter(almacen=almacen, ultimo=0).count(),
            Anio.objects.count(),
        )

    def test_rellenar_correlativos_no_reinicia_el_ultimo(self):
        anio = Anio.objects.get(anio=2026)
        nota = CorrelativoNota.objects.get(anio=anio, almacen__codigo='ALM01')
        nota.ultimo = 9
        nota.save(update_fields=['ultimo'])
        asegurar_correlativos_anio(anio)
        nota.refresh_from_db()
        self.assertEqual(nota.ultimo, 9)

    def test_filtro_de_almacenes_y_de_saldos(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        solo_proceso = cliente.get(reverse('mae.almacenes'), {'proceso': 'si'})
        self.assertContains(solo_proceso, 'PROC01')
        self.assertContains(solo_proceso, 'value="si" selected')
        self.assertNotContains(solo_proceso, 'ALM01')
        self.assertNotContains(solo_proceso, 'ALM02')

        normales = cliente.get(reverse('mae.almacenes'), {'proceso': 'no', 'q': 'compras'})
        self.assertContains(normales, 'ALM01')
        self.assertNotContains(normales, 'PROC01')
        self.assertContains(normales, 'value="no" selected')
        self.assertContains(normales, 'value="compras"')

        anio = Anio.objects.get(anio=2026)
        alm01 = Almacen.objects.get(codigo='ALM01')
        filtrado = cliente.get(reverse('admin.saldo_inicial'), {'anio': anio.pk, 'almacen': alm01.pk})
        self.assertContains(filtrado, 'MP-HIL-20/1')
        self.assertContains(filtrado, 'ALM01-2026-')
        self.assertEqual(
            {fila['obj'].almacen.codigo for fila in filtrado.context['saldos']},
            {'ALM01'},
        )

        vacio = cliente.get(reverse('admin.saldo_inicial'), {
            'anio': anio.pk,
            'almacen': Almacen.objects.get(codigo='ALM02').pk,
        })
        self.assertContains(vacio, 'No hay saldos iniciales con ese filtro')
        self.assertEqual(list(vacio.context['saldos']), [])

    def test_la_ruta_muestra_maquinas_que_pueden_y_no_las_guarda(self):
        tej = Proceso.objects.get(codigo='TEJ')
        cor = Proceso.objects.get(codigo='COR')
        self.assertEqual(list(maquinas_que_pueden(tej).values_list('codigo', flat=True)), ['MAQ-TELAR-01'])
        self.assertFalse(maquinas_que_pueden(cor).exists())

        cliente, _ok = entrar('maribel', 'demo-admin')
        lista = cliente.get(reverse('mae.rutas'))
        self.assertContains(lista, 'MAQ-TELAR-01')
        self.assertContains(lista, 'sin máquina')
        self.assertNotContains(lista, 'PT-POL-PIQ-B')

        ruta = Ruta.objects.get(codigo='RUTA-POLO-01')
        edicion = cliente.get(reverse('mae.rutas_editar', args=[ruta.pk]))
        self.assertContains(edicion, 'para cada proceso, una máquina que pueda realizarlo')
        self.assertContains(edicion, 'MAQ-TELAR-01')
        self.assertContains(edicion, 'id="maquinas-ruta"')
        self.assertEqual(ruta.pasos.count(), 5)


class TestSemillaIdempotente(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_segunda_carga_no_duplica_ni_pisa(self):
        receta = Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B')
        receta.lote_base = Decimal('80')
        receta.save(update_fields=['lote_base'])
        articulos = Articulo.objects.count()
        saldos = SaldoInicial.objects.count()
        kardex = Kardex.objects.count()
        notas = CorrelativoNota.objects.get(anio__anio=2026, almacen__codigo='ALM01').ultimo
        tipo = TipoMaterial.objects.get(codigo='MP')
        Articulo.objects.create(
            codigo='MP-PROPIO',
            descripcion='Hilo del taller',
            tipo_material=tipo,
            unidad_medida='kg',
            activo=True,
        )

        ok, mensaje = seed_ejemplo()
        self.assertTrue(ok)
        self.assertIn('No se duplicó', mensaje)
        receta.refresh_from_db()
        self.assertEqual(receta.lote_base, Decimal('80.0000'))
        self.assertEqual(Articulo.objects.filter(codigo='PT-POL-PIQ-B').count(), 1)
        self.assertEqual(Articulo.objects.filter(codigo='MP-PROPIO').count(), 1)
        self.assertEqual(Articulo.objects.count(), articulos + 1)
        self.assertEqual(SaldoInicial.objects.count(), saldos)
        self.assertEqual(Kardex.objects.count(), kardex)
        self.assertEqual(CorrelativoNota.objects.get(anio__anio=2026, almacen__codigo='ALM01').ultimo, notas)
        self.assertEqual(Ruta.objects.filter(codigo='RUTA-POLO-01').count(), 1)

    def test_reponer_lo_que_falta_sin_tocar_el_resto(self):
        Trabajador.objects.filter(codigo='TR-001').delete()
        ok, mensaje = seed_ejemplo()
        self.assertTrue(ok)
        self.assertIn('faltaban', mensaje)
        self.assertEqual(Trabajador.objects.filter(codigo='TR-001').count(), 1)
        self.assertEqual(Trabajador.objects.get(codigo='TR-001').nombres, 'Juan Pérez')

        otra, mensaje_otra = seed_ejemplo()
        self.assertTrue(otra)
        self.assertIn('No se duplicó', mensaje_otra)
        self.assertEqual(Trabajador.objects.filter(codigo='TR-001').count(), 1)
