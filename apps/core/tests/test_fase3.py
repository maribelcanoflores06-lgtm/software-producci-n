from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from apps.almacen.models import Kardex, Movimiento, MovimientoDetalle, StockActual
from apps.almacen.services.kardex import crear_ingreso, crear_salida, crear_transferencia
from apps.almacen.services.numeracion import _bloquear
from apps.core.seed import (
    MARCA_INGRESO_HILO,
    MARCA_SALIDA_HILO,
    MARCA_TRANSFERENCIA_HILO,
    seed_base,
    seed_ejemplo,
)
from apps.core.tests.test_fase1 import entrar
from apps.maestros.models import Almacen, Anio, Articulo, Cliente, CorrelativoNota, Proveedor


def _datos_ingreso(anio, almacen, proveedor, lineas, **extra):
    data = {
        'anio': anio.pk,
        'fecha': extra.get('fecha', '2026-11-02'),
        'subtipo': extra.get('subtipo', 'COMPRA_NAC'),
        'almacen_destino': almacen.pk if almacen else '',
        'proveedor': proveedor.pk if proveedor else '',
        'tipo_comprobante': '',
        'serie_doc': '',
        'numero_doc': '',
        'fecha_doc': '',
        'observacion': extra.get('observacion', ''),
        'lineas-TOTAL_FORMS': str(len(lineas)),
        'lineas-INITIAL_FORMS': '0',
        'lineas-MIN_NUM_FORMS': '0',
        'lineas-MAX_NUM_FORMS': '1000',
    }
    for indice, linea in enumerate(lineas):
        data[f'lineas-{indice}-articulo'] = linea['articulo'].pk
        data[f'lineas-{indice}-cantidad'] = linea['cantidad']
        data[f'lineas-{indice}-costo_unitario'] = linea.get('costo', '')
        data[f'lineas-{indice}-lote_ref'] = ''
        data[f'lineas-{indice}-ubicacion_ref'] = ''
        data[f'lineas-{indice}-observacion'] = ''
    return data


class TestKardexFase3(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def _base(self):
        return {
            'anio': Anio.objects.get(anio=2026),
            'hilo': Articulo.objects.get(codigo='MP-HIL-20/1'),
            'proveedor': Proveedor.objects.get(codigo='PROV-001'),
            'usuario': Usuario.objects.get(username='maribel'),
        }

    def _almacen(self, codigo):
        return Almacen.objects.create(codigo=codigo, nombre=codigo, es_proceso=False, activo=True)

    def _ingreso(self, almacen, cantidad, costo, **extra):
        base = self._base()
        return crear_ingreso(
            anio=base['anio'],
            fecha=extra.get('fecha', date(2026, 11, 2)),
            subtipo='COMPRA_NAC',
            almacen_destino=almacen,
            proveedor=extra.get('proveedor', base['proveedor']),
            lineas=[{
                'articulo': extra.get('articulo', base['hilo']),
                'cantidad': Decimal(cantidad),
                'costo_unitario': Decimal(costo),
            }],
            usuario=base['usuario'],
        )

    def test_dos_ingresos_dejan_promedio_3_y_la_nota_codalm(self):
        almacen = self._almacen('ALM99')
        primera = self._ingreso(almacen, '100', '2')
        segunda = self._ingreso(almacen, '100', '4')
        self.assertEqual(primera.numero_nota, 'ALM99-2026-000001')
        self.assertEqual(segunda.numero_nota, 'ALM99-2026-000002')
        self.assertEqual(Movimiento.objects.filter(numero_nota=primera.numero_nota).count(), 1)
        stock = StockActual.objects.get(almacen=almacen, articulo=self._base()['hilo'])
        self.assertEqual(stock.cantidad, Decimal('200.0000'))
        self.assertEqual(stock.costo_promedio, Decimal('3.0000'))
        self.assertEqual(stock.valor, Decimal('600.0000'))
        self.assertEqual(stock.ultima_nota, 'ALM99-2026-000002')
        kardex = Kardex.objects.get(numero_nota='ALM99-2026-000002')
        self.assertEqual(kardex.saldo_cantidad, Decimal('200.0000'))
        self.assertEqual(kardex.saldo_valor, Decimal('600.0000'))
        self.assertEqual(kardex.costo_unit_promedio, Decimal('3.0000'))
        self.assertEqual(kardex.valor_entrada, Decimal('400.0000'))

    def test_dos_lineas_en_la_misma_nota_tambien_promedian(self):
        base = self._base()
        almacen = self._almacen('ALM97')
        crear_ingreso(
            anio=base['anio'],
            fecha=date(2026, 11, 2),
            subtipo='COMPRA_NAC',
            almacen_destino=almacen,
            proveedor=base['proveedor'],
            lineas=[
                {'articulo': base['hilo'], 'cantidad': Decimal('100'), 'costo_unitario': Decimal('2')},
                {'articulo': base['hilo'], 'cantidad': Decimal('100'), 'costo_unitario': Decimal('4')},
            ],
            usuario=base['usuario'],
        )
        stock = StockActual.objects.get(almacen=almacen, articulo=base['hilo'])
        self.assertEqual(stock.costo_promedio, Decimal('3.0000'))
        self.assertEqual(stock.cantidad, Decimal('200.0000'))

    def test_transferencia_mueve_el_valor_y_no_cambia_el_promedio_de_origen(self):
        base = self._base()
        origen = self._almacen('ALM96')
        destino = self._almacen('ALM95')
        self._ingreso(origen, '100', '2')
        self._ingreso(origen, '100', '4')
        nota = crear_transferencia(
            anio=base['anio'],
            fecha=date(2026, 11, 2),
            almacen_origen=origen,
            almacen_destino=destino,
            lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('40')}],
            usuario=base['usuario'],
        )
        self.assertEqual(nota.numero_nota, 'ALM96-2026-000003')
        self.assertEqual(nota.almacen_id, origen.pk)
        filas = list(Kardex.objects.filter(numero_nota=nota.numero_nota).order_by('id'))
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0].movimiento_detalle_id, filas[1].movimiento_detalle_id)
        self.assertEqual(filas[0].cantidad_salida, Decimal('40.0000'))
        self.assertEqual(filas[0].valor_salida, Decimal('120.0000'))
        self.assertEqual(filas[0].saldo_cantidad, Decimal('160.0000'))
        self.assertEqual(filas[0].saldo_valor, Decimal('480.0000'))
        self.assertEqual(filas[0].costo_unit_promedio, Decimal('3.0000'))
        self.assertEqual(filas[1].cantidad_entrada, Decimal('40.0000'))
        self.assertEqual(filas[1].valor_entrada, Decimal('120.0000'))
        self.assertEqual(filas[1].costo_unit_promedio, Decimal('3.0000'))
        self.assertEqual(filas[1].saldo_valor, Decimal('120.0000'))
        origen_stock = StockActual.objects.get(almacen=origen, articulo=base['hilo'])
        destino_stock = StockActual.objects.get(almacen=destino, articulo=base['hilo'])
        self.assertEqual(origen_stock.ultima_nota, nota.numero_nota)
        self.assertEqual(destino_stock.ultima_nota, nota.numero_nota)
        self.assertEqual(origen_stock.costo_promedio, Decimal('3.0000'))
        self.assertEqual(destino_stock.valor, Decimal('120.0000'))

    def test_entrada_en_destino_con_stock_recalcula_el_promedio(self):
        base = self._base()
        origen = self._almacen('ALM94')
        destino = self._almacen('ALM93')
        self._ingreso(origen, '100', '3')
        self._ingreso(destino, '10', '5')
        crear_transferencia(
            anio=base['anio'],
            fecha=date(2026, 11, 2),
            almacen_origen=origen,
            almacen_destino=destino,
            lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('40')}],
            usuario=base['usuario'],
        )
        stock = StockActual.objects.get(almacen=destino, articulo=base['hilo'])
        self.assertEqual(stock.cantidad, Decimal('50.0000'))
        self.assertEqual(stock.valor, Decimal('170.0000'))
        self.assertEqual(stock.costo_promedio, Decimal('3.4000'))

    def test_salida_no_cambia_el_promedio(self):
        base = self._base()
        almacen = self._almacen('ALM92')
        self._ingreso(almacen, '100', '2')
        self._ingreso(almacen, '100', '4')
        nota = crear_salida(
            anio=base['anio'],
            fecha=date(2026, 11, 2),
            almacen_origen=almacen,
            lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('10')}],
            usuario=base['usuario'],
            cliente=Cliente.objects.get(codigo='CLI-001'),
        )
        stock = StockActual.objects.get(almacen=almacen, articulo=base['hilo'])
        self.assertEqual(stock.cantidad, Decimal('190.0000'))
        self.assertEqual(stock.costo_promedio, Decimal('3.0000'))
        self.assertEqual(stock.valor, Decimal('570.0000'))
        self.assertEqual(stock.ultima_nota, nota.numero_nota)
        detalle = nota.detalles.get()
        self.assertEqual(detalle.costo_unitario, Decimal('3.0000'))
        self.assertEqual(detalle.costo_total, Decimal('30.0000'))

    def test_stock_insuficiente_no_deja_filas_ni_consume_correlativo(self):
        base = self._base()
        almacen = self._almacen('ALM91')
        self._ingreso(almacen, '5', '2')
        antes = {
            'mov': Movimiento.objects.count(),
            'det': MovimientoDetalle.objects.count(),
            'kardex': Kardex.objects.count(),
            'ultimo': CorrelativoNota.objects.get(anio=base['anio'], almacen=almacen).ultimo,
        }
        with self.assertRaises(ValidationError) as ctx:
            crear_salida(
                anio=base['anio'],
                fecha=date(2026, 11, 2),
                almacen_origen=almacen,
                lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('10')}],
                usuario=base['usuario'],
            )
        self.assertEqual(
            ctx.exception.messages[0],
            'Stock insuficiente de MP-HIL-20/1 en ALM91: disponible 5, pedido 10',
        )
        self.assertEqual(Movimiento.objects.count(), antes['mov'])
        self.assertEqual(MovimientoDetalle.objects.count(), antes['det'])
        self.assertEqual(Kardex.objects.count(), antes['kardex'])
        self.assertEqual(
            CorrelativoNota.objects.get(anio=base['anio'], almacen=almacen).ultimo,
            antes['ultimo'],
        )
        stock = StockActual.objects.get(almacen=almacen, articulo=base['hilo'])
        self.assertEqual(stock.cantidad, Decimal('5.0000'))

    def test_la_segunda_linea_sin_stock_anula_toda_la_nota(self):
        base = self._base()
        almacen = self._almacen('ALM90')
        self._ingreso(almacen, '10', '2')
        antes = Movimiento.objects.count()
        with self.assertRaises(ValidationError):
            crear_salida(
                anio=base['anio'],
                fecha=date(2026, 11, 2),
                almacen_origen=almacen,
                lineas=[
                    {'articulo': base['hilo'], 'cantidad': Decimal('6')},
                    {'articulo': base['hilo'], 'cantidad': Decimal('6')},
                ],
                usuario=base['usuario'],
            )
        self.assertEqual(Movimiento.objects.count(), antes)
        self.assertEqual(
            StockActual.objects.get(almacen=almacen, articulo=base['hilo']).cantidad,
            Decimal('10.0000'),
        )

    def test_ingreso_sin_proveedor_y_a_almacen_de_proceso(self):
        base = self._base()
        almacen = self._almacen('ALM89')
        with self.assertRaises(ValidationError) as ctx:
            crear_ingreso(
                anio=base['anio'],
                fecha=date(2026, 11, 2),
                subtipo='COMPRA_NAC',
                almacen_destino=almacen,
                proveedor=None,
                lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('1'), 'costo_unitario': Decimal('1')}],
                usuario=base['usuario'],
            )
        self.assertIn('proveedor', ctx.exception.messages[0])
        proceso = Almacen.objects.get(codigo='PROC01')
        with self.assertRaises(ValidationError) as ctx_proc:
            crear_ingreso(
                anio=base['anio'],
                fecha=date(2026, 11, 2),
                subtipo='COMPRA_NAC',
                almacen_destino=proceso,
                proveedor=base['proveedor'],
                lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('1'), 'costo_unitario': Decimal('1')}],
                usuario=base['usuario'],
            )
        self.assertIn('PROC01', ctx_proc.exception.messages[0])
        self.assertIn('proceso', ctx_proc.exception.messages[0])
        self.assertFalse(Movimiento.objects.filter(almacen=proceso, tipo=Movimiento.INGRESO).exists())

    def test_anio_cerrado_fecha_ajena_y_costo_cero(self):
        base = self._base()
        almacen = self._almacen('ALM88')
        base['anio'].cerrado = True
        base['anio'].save(update_fields=['cerrado'])
        with self.assertRaises(ValidationError) as cerrado:
            self._ingreso(almacen, '1', '1')
        self.assertIn('cerrado', cerrado.exception.messages[0])
        base['anio'].cerrado = False
        base['anio'].save(update_fields=['cerrado'])
        with self.assertRaises(ValidationError) as fecha:
            self._ingreso(almacen, '1', '1', fecha=date(2025, 11, 2))
        self.assertIn('año', fecha.exception.messages[0])
        with self.assertRaises(ValidationError):
            self._ingreso(almacen, '1', '0')
        with self.assertRaises(ValidationError) as mismo:
            crear_transferencia(
                anio=base['anio'],
                fecha=date(2026, 11, 2),
                almacen_origen=almacen,
                almacen_destino=almacen,
                lineas=[{'articulo': base['hilo'], 'cantidad': Decimal('1')}],
                usuario=base['usuario'],
            )
        self.assertIn('distintos', mismo.exception.messages[0])

    def test_bloqueo_de_correlativo_cuando_el_motor_lo_soporta(self):
        consulta = MagicMock()
        with patch('apps.almacen.services.numeracion.connection') as conn:
            conn.features.has_select_for_update = True
            self.assertIs(_bloquear(consulta), consulta.select_for_update.return_value)
            consulta.select_for_update.assert_called_once_with()
        with patch('apps.almacen.services.numeracion.connection') as conn:
            conn.features.has_select_for_update = False
            self.assertIs(_bloquear(consulta), consulta)

    def test_semilla_de_la_fase_es_idempotente_y_deja_el_promedio(self):
        anio = Anio.objects.get(anio=2026)
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        alm01 = Almacen.objects.get(codigo='ALM01')
        alm02 = Almacen.objects.get(codigo='ALM02')
        stock_01 = StockActual.objects.get(anio=anio, almacen=alm01, articulo=hilo)
        stock_02 = StockActual.objects.get(anio=anio, almacen=alm02, articulo=hilo)
        self.assertEqual(stock_01.cantidad, Decimal('160.0000'))
        self.assertEqual(stock_01.costo_promedio, Decimal('3.0000'))
        self.assertEqual(stock_01.valor, Decimal('480.0000'))
        self.assertEqual(stock_01.ultima_nota, 'ALM01-2026-000006')
        self.assertEqual(stock_02.cantidad, Decimal('35.0000'))
        self.assertEqual(stock_02.costo_promedio, Decimal('3.0000'))
        self.assertEqual(stock_02.valor, Decimal('105.0000'))
        self.assertEqual(stock_02.ultima_nota, 'ALM02-2026-000001')
        ingreso = Movimiento.objects.get(observacion=MARCA_INGRESO_HILO)
        self.assertEqual(ingreso.numero_nota, 'ALM01-2026-000005')
        self.assertEqual(ingreso.proveedor.codigo, 'PROV-001')
        self.assertTrue(Movimiento.objects.filter(observacion=MARCA_TRANSFERENCIA_HILO).exists())
        self.assertTrue(Movimiento.objects.filter(observacion=MARCA_SALIDA_HILO).exists())
        kardex = Kardex.objects.count()
        ultimo = CorrelativoNota.objects.get(anio=anio, almacen=alm01).ultimo
        ok, mensaje = seed_ejemplo()
        self.assertTrue(ok)
        self.assertIn('No se duplicó', mensaje)
        self.assertEqual(Kardex.objects.count(), kardex)
        self.assertEqual(CorrelativoNota.objects.get(anio=anio, almacen=alm01).ultimo, ultimo)
        stock_01.refresh_from_db()
        self.assertEqual(stock_01.cantidad, Decimal('160.0000'))


class TestPantallasFase3(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_formulario_agrega_linea_sin_salir_y_quita_sin_checkbox(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        pagina = cliente.get(reverse('alm.ingreso_nueva'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'type="button"')
        self.assertContains(pagina, "onclick=\"agregarLinea('lineas')\"")
        self.assertContains(pagina, '>Quitar</button>')
        self.assertNotContains(pagina, 'Quitar</label>')
        self.assertContains(pagina, 'linea-delete')
        self.assertContains(pagina, 'AUTO')
        self.assertContains(pagina, 'id="mes-derivado"')
        self.assertNotContains(pagina, 'PROC01')
        self.assertContains(pagina, '<form method="post"')

    def test_ingreso_sin_proveedor_se_queda_en_la_pantalla(self):
        cliente, _ok = entrar('almacenero', 'demo-alm')
        anio = Anio.objects.get(anio=2026)
        almacen = Almacen.objects.get(codigo='ALM03')
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        antes = Movimiento.objects.count()
        respuesta = cliente.post(reverse('alm.ingreso_nueva'), _datos_ingreso(
            anio, almacen, None, [{'articulo': hilo, 'cantidad': '100', 'costo': '2,50'}],
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El ingreso exige un proveedor.')
        self.assertContains(respuesta, 'Nuevo ingreso')
        self.assertContains(respuesta, '100')
        self.assertEqual(Movimiento.objects.count(), antes)

    def test_almacenero_registra_ingreso_y_el_stock_muestra_la_ultima_nota(self):
        cliente, _ok = entrar('almacenero', 'demo-alm')
        anio = Anio.objects.get(anio=2026)
        almacen = Almacen.objects.get(codigo='ALM03')
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        proveedor = Proveedor.objects.get(codigo='PROV-001')
        respuesta = cliente.post(reverse('alm.ingreso_nueva'), _datos_ingreso(
            anio, almacen, proveedor, [{'articulo': hilo, 'cantidad': '100', 'costo': '2'}],
        ), follow=True)
        nota = Movimiento.objects.get(numero_nota='ALM03-2026-000001')
        self.assertEqual(respuesta.redirect_chain[0][0], reverse('alm.ingreso_detalle', args=[nota.pk]))
        self.assertContains(respuesta, 'ALM03-2026-000001')
        self.assertContains(respuesta, 'Nota ALM03-2026-000001 registrada.')
        stock = cliente.get(reverse('rep.stock'), {'anio': anio.pk, 'almacen': almacen.pk})
        self.assertContains(stock, 'data-autofiltro')
        self.assertContains(stock, 'ALM03-2026-000001')
        self.assertContains(stock, 'class="num">100<')
        self.assertContains(stock, '2.0000')
        self.assertContains(stock, '200.00')
        self.assertNotContains(stock, '100,0000')
        self.assertNotContains(stock, '2,0000')
        self.assertContains(stock, 'Última nota')
        filas = list(stock.context['filas'])
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].ultima_nota, 'ALM03-2026-000001')
        self.assertEqual(filas[0].costo_promedio, Decimal('2.0000'))

    def test_filtros_de_listas_reportes_y_permisos(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        anio = Anio.objects.get(anio=2026)
        alm02 = Almacen.objects.get(codigo='ALM02')
        hilo = Articulo.objects.get(codigo='MP-HIL-20/1')
        lista = cliente.get(reverse('alm.ingreso'))
        self.assertContains(lista, 'data-autofiltro')
        self.assertContains(lista, 'EJEMPLO')
        self.assertContains(lista, 'ALM01-2026-000005')
        transferencia = cliente.get(reverse('alm.transferencia'), {'almacen': alm02.pk})
        self.assertContains(transferencia, 'ALM01-2026-000006')
        self.assertContains(transferencia, 'value="%s" selected' % alm02.pk)
        kardex = cliente.get(reverse('rep.kardex'), {
            'anio': anio.pk,
            'articulo': hilo.pk,
            'almacen': Almacen.objects.get(codigo='ALM01').pk,
            'desde': '2026-11-01',
            'hasta': '2026-11-01',
        })
        self.assertContains(kardex, 'data-autofiltro')
        self.assertContains(kardex, '3.0000')
        self.assertContains(kardex, '600.00')
        self.assertNotContains(kardex, '3,0000')
        self.assertContains(kardex, 'ALM01-2026-000005')
        self.assertEqual(
            {fila.articulo.codigo for fila in kardex.context['filas']},
            {'MP-HIL-20/1'},
        )
        self.assertContains(kardex, 'Revalorización')
        salida = cliente.get(reverse('alm.salida_nueva'))
        self.assertContains(salida, '>Quitar</button>')
        self.assertContains(salida, 'SALIDA')
        self.assertNotContains(salida, 'Costo unit. S/')

        consulta, _ok = entrar('consulta', 'demo-consulta')
        self.assertEqual(consulta.get(reverse('rep.kardex')).status_code, 200)
        self.assertEqual(consulta.get(reverse('rep.stock')).status_code, 200)
        self.assertEqual(consulta.post(reverse('alm.ingreso_nueva'), {}).status_code, 403)
        self.assertEqual(consulta.get(reverse('alm.salida')).status_code, 403)
        jefe, _ok = entrar('jefeprod', 'demo-prod')
        self.assertEqual(jefe.get(reverse('alm.transferencia')).status_code, 403)
        self.assertEqual(jefe.get(reverse('rep.stock')).status_code, 200)

    def test_la_pantalla_de_stock_muestra_el_ejemplo_y_oculta_ceros(self):
        cliente, _ok = entrar('consulta', 'demo-consulta')
        anio = Anio.objects.get(anio=2026)
        pagina = cliente.get(reverse('rep.stock'), {'anio': anio.pk, 'articulo': Articulo.objects.get(codigo='MP-HIL-20/1').pk})
        self.assertContains(pagina, 'class="num">160<')
        self.assertContains(pagina, 'class="num">35<')
        self.assertContains(pagina, 'ALM01-2026-000006')
        self.assertContains(pagina, 'ALM02-2026-000001')
        self.assertContains(pagina, '3.0000')
        self.assertContains(pagina, '480.00')
        self.assertContains(pagina, '105.00')
        self.assertNotContains(pagina, '160,0000')
        self.assertNotContains(pagina, '3,0000')
        codigos = {fila.almacen.codigo for fila in pagina.context['filas']}
        self.assertEqual(codigos, {'ALM01', 'ALM02'})
