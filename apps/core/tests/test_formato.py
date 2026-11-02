from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.formats import get_format

from apps.core.formularios import MontoField
from apps.core.numeros import formato_cantidad, formato_costo, formato_soles, normalizar_entrada
from apps.core.seed import seed_base, seed_ejemplo
from apps.core.tests.test_fase1 import entrar
from apps.maestros.models import Almacen, Anio, Maquina, Receta, Ruta


class TestFormatoNumerico(TestCase):
    def test_miles_con_punto_decimal(self):
        self.assertEqual(formato_soles(Decimal('1250')), '1,250.00')
        self.assertEqual(formato_soles(Decimal('480')), '480.00')
        self.assertEqual(formato_soles(Decimal('1125')), '1,125.00')
        self.assertEqual(formato_soles(Decimal('0.05')), '0.05')
        self.assertEqual(formato_cantidad(Decimal('50')), '50')
        self.assertEqual(formato_cantidad(Decimal('2.5')), '2.5')
        self.assertEqual(formato_cantidad(Decimal('1250.5000')), '1,250.5')
        self.assertEqual(formato_cantidad(Decimal('1000')), '1,000')
        self.assertEqual(formato_cantidad(Decimal('0')), '0')
        self.assertEqual(formato_costo(Decimal('3')), '3.0000')
        self.assertEqual(formato_costo(Decimal('0.05')), '0.0500')
        self.assertEqual(formato_costo(Decimal('1250.5')), '1,250.5000')

    def test_el_input_acepta_punto_decimal_y_coma_de_miles(self):
        campo = MontoField()
        self.assertEqual(normalizar_entrada('1,250.50'), '1250.50')
        self.assertEqual(campo.to_python('1,250.50'), Decimal('1250.5000'))
        self.assertEqual(campo.to_python('2.5'), Decimal('2.5000'))
        self.assertEqual(campo.to_python('10,5'), Decimal('10.5000'))
        self.assertEqual(campo.to_python('2,50'), Decimal('2.5000'))
        self.assertEqual(campo.prepare_value(Decimal('50.0000')), '50')
        self.assertEqual(campo.prepare_value('2.5'), '2.5')
        costo = MontoField(presentacion='costo')
        self.assertEqual(costo.prepare_value(Decimal('3')), '3.0000')
        self.assertEqual(costo.widget.attrs['placeholder'], '0.0000')
        self.assertEqual(campo.widget.attrs['placeholder'], '0.00')

    def test_el_locale_es_no_usa_coma_decimal(self):
        self.assertTrue(settings.USE_THOUSAND_SEPARATOR)
        self.assertEqual(settings.DECIMAL_SEPARATOR, '.')
        self.assertEqual(settings.THOUSAND_SEPARATOR, ',')
        with translation.override('es'):
            self.assertEqual(get_format('DECIMAL_SEPARATOR'), '.')
            self.assertEqual(get_format('THOUSAND_SEPARATOR'), ',')


class TestPantallasConFormato(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_stock_saldo_y_receta_usan_el_formato_peruano(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        anio = Anio.objects.get(anio=2026)
        almacen = cliente.get(reverse('rep.stock'), {
            'anio': anio.pk,
            'almacen': Almacen.objects.get(codigo='ALM01').pk,
        })
        self.assertContains(almacen, '1,000')
        self.assertContains(almacen, '0.0500')
        self.assertContains(almacen, '1,125.00')
        self.assertContains(almacen, '4.5000')
        self.assertNotContains(almacen, '1000,0000')
        self.assertNotContains(almacen, '4,5000')

        saldo = cliente.get(reverse('admin.saldo_inicial'), {'anio': anio.pk})
        self.assertContains(saldo, '2.0000')
        self.assertContains(saldo, '200.00')
        self.assertContains(saldo, '1,125.00')
        self.assertNotContains(saldo, '2,0000')

        recetas = cliente.get(reverse('mae.recetas'))
        self.assertContains(recetas, '>100<')
        self.assertNotContains(recetas, '100.0000')
        self.assertNotContains(almacen, '160,0000')

    def test_las_grillas_marcan_el_campo_vacio_y_el_borde(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        ingreso = cliente.get(reverse('alm.ingreso_nueva'))
        self.assertContains(ingreso, 'Seleccionar artículo…')
        self.assertContains(ingreso, 'Seleccionar almacén…')
        self.assertContains(ingreso, 'Seleccionar proveedor…')
        self.assertContains(ingreso, 'placeholder="0.00"')
        self.assertContains(ingreso, 'placeholder="0.0000"')
        self.assertContains(ingreso, 'placeholder="Opcional"')
        self.assertNotContains(ingreso, '>—</option>')

        receta = Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B')
        edicion = cliente.get(reverse('mae.recetas_editar', args=[receta.pk]))
        self.assertContains(edicion, 'Seleccionar artículo…')
        self.assertContains(edicion, 'placeholder="0.00"')
        self.assertContains(edicion, 'value="25"')
        self.assertNotContains(edicion, 'value="25.0000"')

        ruta = Ruta.objects.get(codigo='RUTA-POLO-01')
        self.assertContains(cliente.get(reverse('mae.rutas_editar', args=[ruta.pk])), 'Seleccionar proceso…')
        maquina = Maquina.objects.get(codigo='MAQ-TELAR-01')
        self.assertContains(cliente.get(reverse('mae.maquinas_editar', args=[maquina.pk])), 'Seleccionar proceso…')

        saldo = cliente.get(reverse('admin.saldo_inicial'))
        self.assertContains(saldo, 'Seleccionar almacén…')
        self.assertContains(saldo, 'Seleccionar artículo…')
        self.assertContains(saldo, 'Seleccionar año…')
        self.assertContains(saldo, 'placeholder="0.00"')
        self.assertContains(saldo, 'placeholder="0.0000"')

        css = Path(settings.BASE_DIR, 'static', 'css', 'app.css').read_text(encoding='utf-8')
        self.assertIn('table.grid input, table.grid select, table.grid textarea', css)
        self.assertIn('border: 1px solid #bdbdbd', css)
        self.assertIn('border-radius: 3px', css)
        self.assertIn('background: #fff', css)
        self.assertIn('border-color: var(--accent)', css)
        js = Path(settings.BASE_DIR, 'static', 'js', 'app.js').read_text(encoding='utf-8')
        self.assertIn('Seleccionar artículo…', js)
