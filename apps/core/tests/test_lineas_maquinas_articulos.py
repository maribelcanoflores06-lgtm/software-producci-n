import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.seed import seed_base, seed_ejemplo
from apps.maestros.models import Articulo, Maquina, MaquinaProceso, Proceso, Receta, Ruta, TipoMaterial


def entrar(username, password):
    cliente = Client()
    ok = cliente.login(username=username, password=password)
    return cliente, ok


def opciones(html, nombre):
    patron = re.compile(
        r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % re.escape(nombre),
        re.S,
    )
    return [re.findall(r'value="([^"]*)"', bloque) for bloque in patron.findall(html)]


class TestRecetasYLineas(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_editar_receta_oculta_el_producto_terminado_en_los_insumos(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        receta = Receta.objects.select_related('articulo_pt').get(articulo_pt__codigo='PT-POL-PIQ-B')
        pagina = cliente.get(reverse('mae.recetas_editar', args=[receta.pk]))
        self.assertContains(pagina, 'Editar receta')
        self.assertContains(pagina, 'type="button"')
        self.assertContains(pagina, 'onclick="agregarLinea(\'detalles\')"')
        self.assertContains(pagina, '>Quitar</button>')
        self.assertNotContains(pagina, 'Quitar</label>')
        cabecera = opciones(pagina.content.decode(), 'articulo_pt')
        self.assertIn(str(receta.articulo_pt_id), cabecera[0])
        insumos = []
        for nombre in re.findall(r'name="(detalles-\d+-articulo_insumo|detalles-__prefix__-articulo_insumo)"', pagina.content.decode()):
            insumos.extend(opciones(pagina.content.decode(), nombre))
        self.assertTrue(insumos)
        for valores in insumos:
            self.assertNotIn(str(receta.articulo_pt_id), valores)
            self.assertIn(str(Articulo.objects.get(codigo='MP-HIL-20/1').pk), valores)

    def test_servidor_rechaza_el_producto_terminado_como_insumo_y_conserva_lineas(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        receta = Receta.objects.select_related('articulo_pt').get(articulo_pt__codigo='PT-POL-PIQ-B')
        detalles = list(receta.detalles.order_by('id'))
        data = {
            'articulo_pt': receta.articulo_pt_id,
            'lote_base': '100',
            'activo': 'on',
            'detalles-TOTAL_FORMS': str(len(detalles)),
            'detalles-INITIAL_FORMS': str(len(detalles)),
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
        }
        for indice, detalle in enumerate(detalles):
            data[f'detalles-{indice}-id'] = detalle.pk
            data[f'detalles-{indice}-articulo_insumo'] = (
                receta.articulo_pt_id if indice == 0 else detalle.articulo_insumo_id
            )
            data[f'detalles-{indice}-cantidad_por_lote'] = '9.5' if indice == 0 else '4'
        respuesta = cliente.post(reverse('mae.recetas_editar', args=[receta.pk]), data)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Editar receta')
        self.assertContains(respuesta, 'no puede ser el mismo producto terminado')
        self.assertContains(respuesta, 'value="4"')
        receta.refresh_from_db()
        self.assertEqual(receta.detalles.count(), 4)
        self.assertFalse(receta.detalles.filter(articulo_insumo=receta.articulo_pt).exists())

    def test_cambiar_el_producto_terminado_actualiza_las_opciones_de_insumo(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        tipo_pt = TipoMaterial.objects.get(codigo='PT')
        nuevo = Articulo.objects.create(
            codigo='PT-OPC-2',
            descripcion='Segundo polo',
            tipo_material=tipo_pt,
            unidad_medida='und',
            activo=True,
        )
        receta = Receta.objects.select_related('articulo_pt').get(articulo_pt__codigo='PT-POL-PIQ-B')
        detalles = list(receta.detalles.order_by('id'))
        data = {
            'articulo_pt': nuevo.pk,
            'lote_base': '0',
            'activo': 'on',
            'detalles-TOTAL_FORMS': str(len(detalles) + 1),
            'detalles-INITIAL_FORMS': str(len(detalles)),
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
        }
        for indice, detalle in enumerate(detalles):
            data[f'detalles-{indice}-id'] = detalle.pk
            data[f'detalles-{indice}-articulo_insumo'] = detalle.articulo_insumo_id
            data[f'detalles-{indice}-cantidad_por_lote'] = '7'
        extra = len(detalles)
        data[f'detalles-{extra}-id'] = ''
        data[f'detalles-{extra}-articulo_insumo'] = Articulo.objects.get(codigo='MP-TEL-JER').pk
        data[f'detalles-{extra}-cantidad_por_lote'] = '3,25'
        respuesta = cliente.post(reverse('mae.recetas_editar', args=[receta.pk]), data)
        html = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Editar receta')
        self.assertContains(respuesta, 'mayor que cero')
        self.assertContains(respuesta, '3,25')
        self.assertContains(respuesta, 'value="7"')
        nombres = re.findall(r'name="(detalles-(?:\d+|__prefix__)-articulo_insumo)"', html)
        self.assertGreaterEqual(len(nombres), len(detalles) + 1)
        for nombre in nombres:
            for valores in opciones(html, nombre):
                self.assertNotIn(str(nuevo.pk), valores)
                self.assertIn(str(receta.articulo_pt_id), valores)
        self.assertEqual(receta.detalles.count(), 4)

    def test_guardar_con_linea_nueva_permanece_si_hay_error_y_sale_si_es_valido(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        tipo_mp = TipoMaterial.objects.get(codigo='MP')
        extra_art = Articulo.objects.create(
            codigo='MP-EXTRA',
            descripcion='Hilo extra',
            tipo_material=tipo_mp,
            unidad_medida='kg',
            activo=True,
        )
        receta = Receta.objects.get(articulo_pt__codigo='PT-POL-PIQ-B')
        detalles = list(receta.detalles.order_by('id'))
        base = {
            'articulo_pt': receta.articulo_pt_id,
            'activo': 'on',
            'detalles-TOTAL_FORMS': str(len(detalles) + 1),
            'detalles-INITIAL_FORMS': str(len(detalles)),
            'detalles-MIN_NUM_FORMS': '0',
            'detalles-MAX_NUM_FORMS': '1000',
        }
        for indice, detalle in enumerate(detalles):
            base[f'detalles-{indice}-id'] = detalle.pk
            base[f'detalles-{indice}-articulo_insumo'] = detalle.articulo_insumo_id
            base[f'detalles-{indice}-cantidad_por_lote'] = '6'
        extra = len(detalles)
        base[f'detalles-{extra}-id'] = ''
        base[f'detalles-{extra}-articulo_insumo'] = extra_art.pk
        invalido = cliente.post(reverse('mae.recetas_editar', args=[receta.pk]), {
            **base,
            'lote_base': '0',
            f'detalles-{extra}-cantidad_por_lote': '1,5',
        })
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, 'Editar receta')
        self.assertContains(invalido, '1,5')
        self.assertEqual(receta.detalles.count(), 4)

        valido = cliente.post(reverse('mae.recetas_editar', args=[receta.pk]), {
            **base,
            'lote_base': '100',
            f'detalles-{extra}-cantidad_por_lote': '1,5',
        })
        self.assertEqual(valido.status_code, 302)
        self.assertEqual(receta.detalles.count(), 5)
        self.assertEqual(receta.detalles.get(articulo_insumo=extra_art).cantidad_por_lote, Decimal('1.5000'))

    def test_quitar_linea_de_ruta_se_aplica_al_guardar_y_el_boton_no_es_checkbox(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        ruta = Ruta.objects.get(codigo='RUTA-POLO-01')
        pagina = cliente.get(reverse('mae.rutas_editar', args=[ruta.pk]))
        self.assertContains(pagina, 'Editar ruta')
        self.assertContains(pagina, '>Quitar</button>')
        self.assertContains(pagina, 'onclick="quitarLinea(this)"')
        self.assertNotContains(pagina, 'Quitar</label>')
        js = Path(settings.BASE_DIR, 'static', 'js', 'app.js').read_text(encoding='utf-8')
        self.assertIn('function quitarLinea', js)
        self.assertIn('function renumerarSecuencias', js)
        self.assertIn('renumerarSecuencias()', js)

        pasos = list(ruta.pasos.order_by('secuencia'))
        quitado = pasos[1]
        data = {
            'codigo': ruta.codigo,
            'nombre': ruta.nombre,
            'activo': 'on',
            'pasos-TOTAL_FORMS': str(len(pasos)),
            'pasos-INITIAL_FORMS': str(len(pasos)),
            'pasos-MIN_NUM_FORMS': '0',
            'pasos-MAX_NUM_FORMS': '1000',
        }
        visibles = [paso for paso in pasos if paso.pk != quitado.pk]
        for indice, paso in enumerate(pasos):
            data[f'pasos-{indice}-id'] = paso.pk
            data[f'pasos-{indice}-proceso'] = paso.proceso_id
            data[f'pasos-{indice}-secuencia'] = indice + 1
            if paso.pk == quitado.pk:
                data[f'pasos-{indice}-DELETE'] = 'on'
                data[f'pasos-{indice}-secuencia'] = paso.secuencia
        for visible, secuencia in zip(visibles, range(1, len(visibles) + 1)):
            for indice, paso in enumerate(pasos):
                if paso.pk == visible.pk:
                    data[f'pasos-{indice}-secuencia'] = secuencia
        error = cliente.post(reverse('mae.rutas_editar', args=[ruta.pk]), {**data, 'nombre': ''})
        self.assertEqual(error.status_code, 200)
        self.assertContains(error, 'Editar ruta')
        self.assertContains(error, 'obligatorio')
        self.assertEqual(ruta.pasos.count(), 5)

        ok = cliente.post(reverse('mae.rutas_editar', args=[ruta.pk]), data)
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(ruta.pasos.count(), 4)
        self.assertFalse(ruta.pasos.filter(proceso=quitado.proceso).exists())
        self.assertEqual(list(ruta.pasos.order_by('secuencia').values_list('secuencia', flat=True)), [1, 2, 3, 4])


class TestMaquinas(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_semilla_menu_y_permisos(self):
        self.assertEqual(Maquina.objects.count(), 3)
        telar = Maquina.objects.get(codigo='MAQ-TELAR-01')
        self.assertEqual(telar.procesos.model, Proceso)
        self.assertEqual(list(telar.procesos.values_list('codigo', flat=True)), ['TEJ'])
        jigger = Maquina.objects.get(codigo='MAQ-JIGGER-01')
        self.assertEqual(set(jigger.procesos.values_list('nombre', flat=True)), {'Teñido', 'Blanqueo'})
        linea = Maquina.objects.get(codigo='MAQ-LINEA-01')
        self.assertEqual(set(linea.procesos.values_list('nombre', flat=True)), {'Acabado', 'Secado'})

        admin, _ok = entrar('maribel', 'demo-admin')
        inicio = admin.get(reverse('home'))
        self.assertContains(inicio, '/maestros/maquinas/')
        lista = admin.get(reverse('mae.maquinas'))
        self.assertContains(lista, 'Telar circular 1')
        self.assertContains(lista, 'TEN')
        self.assertContains(lista, 'SEC')

        jefe, _ok = entrar('jefeprod', 'demo-prod')
        self.assertEqual(jefe.get(reverse('mae.maquinas')).status_code, 200)
        self.assertContains(jefe.get(reverse('home')), '/maestros/maquinas/')
        edicion = jefe.get(reverse('mae.maquinas_editar', args=[telar.pk]))
        self.assertContains(edicion, '>Quitar</button>')
        self.assertContains(edicion, 'Editar máquina')
        self.assertContains(edicion, 'TEJ - Tejido')
        self.assertContains(edicion, 'TEN - Teñido')
        self.assertContains(edicion, 'SEC - Secado')
        self.assertNotContains(edicion, 'PROC01')
        self.assertNotContains(edicion, 'ALM01')

        consulta, _ok = entrar('consulta', 'demo-consulta')
        self.assertEqual(consulta.get(reverse('mae.maquinas')).status_code, 403)
        self.assertNotContains(consulta.get(reverse('home')), '/maestros/maquinas/')
        almacen, _ok = entrar('almacenero', 'demo-alm')
        self.assertEqual(almacen.get(reverse('mae.maquinas')).status_code, 403)

    def test_alta_rechaza_proceso_inactivo_y_repetido_sin_salir(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        proceso = Proceso.objects.get(codigo='TEN')
        inactivo = Proceso.objects.create(codigo='INACT', nombre='Fuera de uso', activo=False)
        base = {
            'codigo': 'maq-nueva',
            'nombre': 'Overlock',
            'descripcion': 'Prueba',
            'activo': 'on',
            'procesos-TOTAL_FORMS': '2',
            'procesos-INITIAL_FORMS': '0',
            'procesos-MIN_NUM_FORMS': '0',
            'procesos-MAX_NUM_FORMS': '1000',
            'procesos-0-id': '',
            'procesos-1-id': '',
        }
        repetido = cliente.post(reverse('mae.maquinas_nueva'), {
            **base,
            'procesos-0-proceso': proceso.pk,
            'procesos-1-proceso': proceso.pk,
        })
        self.assertEqual(repetido.status_code, 200)
        self.assertContains(repetido, 'Nueva máquina')
        self.assertContains(repetido, 'está repetido')
        self.assertContains(repetido, 'Overlock')
        self.assertFalse(Maquina.objects.filter(codigo='MAQ-NUEVA').exists())

        pagina = cliente.get(reverse('mae.maquinas_nueva'))
        self.assertContains(pagina, 'TEN - Teñido')
        self.assertNotContains(pagina, 'INACT - Fuera de uso')
        self.assertNotContains(pagina, 'PROC01')

        ajeno = cliente.post(reverse('mae.maquinas_nueva'), {
            **base,
            'procesos-TOTAL_FORMS': '1',
            'procesos-0-proceso': inactivo.pk,
        })
        self.assertEqual(ajeno.status_code, 200)
        self.assertContains(ajeno, 'Seleccione un proceso activo')
        self.assertFalse(Maquina.objects.filter(codigo='MAQ-NUEVA').exists())

        creado = cliente.post(reverse('mae.maquinas_nueva'), {
            **base,
            'procesos-TOTAL_FORMS': '1',
            'procesos-0-proceso': proceso.pk,
        })
        self.assertEqual(creado.status_code, 302)
        maquina = Maquina.objects.get(codigo='MAQ-NUEVA')
        self.assertEqual(maquina.nombre, 'Overlock')
        self.assertEqual(maquina.descripcion, 'Prueba')
        self.assertEqual(list(maquina.procesos.values_list('codigo', flat=True)), ['TEN'])
        self.assertEqual(maquina.procesos.get()._meta.model_name, 'proceso')

    def test_quitar_proceso_se_aplica_al_guardar(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        maquina = Maquina.objects.get(codigo='MAQ-LINEA-01')
        asignaciones = list(maquina.asignaciones.order_by('proceso__codigo'))
        self.assertEqual(len(asignaciones), 2)
        data = {
            'codigo': maquina.codigo,
            'nombre': maquina.nombre,
            'descripcion': maquina.descripcion,
            'activo': 'on',
            'procesos-TOTAL_FORMS': '2',
            'procesos-INITIAL_FORMS': '2',
            'procesos-MIN_NUM_FORMS': '0',
            'procesos-MAX_NUM_FORMS': '1000',
        }
        for indice, fila in enumerate(asignaciones):
            data[f'procesos-{indice}-id'] = fila.pk
            data[f'procesos-{indice}-proceso'] = fila.proceso_id
        data['procesos-0-DELETE'] = 'on'
        respuesta = cliente.post(reverse('mae.maquinas_editar', args=[maquina.pk]), data)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(list(maquina.procesos.values_list('codigo', flat=True)), [asignaciones[1].proceso.codigo])
        self.assertEqual(MaquinaProceso.objects.filter(maquina=maquina).count(), 1)

    def test_seed_carga_maquinas_aunque_ya_haya_maestros(self):
        Maquina.objects.all().delete()
        articulos = Articulo.objects.count()
        procesos = Proceso.objects.count()
        ok, mensaje = seed_ejemplo()
        self.assertTrue(ok, mensaje)
        self.assertIn('máquinas', mensaje)
        self.assertEqual(Articulo.objects.count(), articulos)
        self.assertGreaterEqual(procesos, 5)
        self.assertEqual(Maquina.objects.count(), 3)
        self.assertEqual(
            set(Maquina.objects.get(codigo='MAQ-LINEA-01').procesos.values_list('nombre', flat=True)),
            {'Acabado', 'Secado'},
        )
        self.assertTrue(Proceso.objects.filter(codigo='SEC', nombre='Secado').exists())
        otra, mensaje_otra = seed_ejemplo()
        self.assertFalse(otra)
        self.assertIn('ya tiene maestros', mensaje_otra)
        self.assertEqual(Maquina.objects.count(), 3)
        self.assertEqual(Maquina.objects.get(codigo='MAQ-JIGGER-01').asignaciones.count(), 2)


class TestFiltroArticulos(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_base()
        seed_ejemplo()

    def test_filtra_por_tipo_combina_busqueda_y_conserva_el_parametro_al_paginar(self):
        cliente, _ok = entrar('maribel', 'demo-admin')
        todos = cliente.get(reverse('mae.articulos'))
        self.assertContains(todos, 'Tipo de artículo')
        self.assertContains(todos, '>Todos<')
        self.assertContains(todos, 'MP-HIL-20/1')
        self.assertContains(todos, 'PT-POL-PIQ-B')

        solo_mp = cliente.get(reverse('mae.articulos'), {'tipo': 'MP'})
        self.assertContains(solo_mp, 'MP-HIL-20/1')
        self.assertContains(solo_mp, 'MP-TEL-JER')
        self.assertNotContains(solo_mp, 'PT-POL-PIQ-B')
        self.assertNotContains(solo_mp, 'AUX-BOT-14')
        self.assertContains(solo_mp, 'value="MP" selected')

        combinado = cliente.get(reverse('mae.articulos'), {'tipo': 'mp', 'q': 'tel'})
        self.assertContains(combinado, 'MP-TEL-JER')
        self.assertNotContains(combinado, 'MP-HIL-20/1')
        self.assertNotContains(combinado, 'PT-POL-PIQ-B')
        self.assertContains(combinado, 'value="tel"')

        vacio = cliente.get(reverse('mae.articulos'), {'tipo': 'PT', 'q': 'tel'})
        self.assertContains(vacio, 'No hay registros')
        self.assertNotContains(vacio, 'MP-TEL-JER')

        tipo_mp = TipoMaterial.objects.get(codigo='MP')
        Articulo.objects.bulk_create([
            Articulo(
                codigo=f'MP-FILTRO-{indice:02d}',
                descripcion=f'Insumo filtro {indice}',
                tipo_material=tipo_mp,
                unidad_medida='kg',
                activo=True,
            )
            for indice in range(21)
        ])
        primera = cliente.get(reverse('mae.articulos'), {'tipo': 'MP', 'q': 'filtro'})
        self.assertContains(primera, 'MP-FILTRO-00')
        self.assertNotContains(primera, 'PT-POL-PIQ-B')
        self.assertNotContains(primera, 'MP-HIL-20/1')
        self.assertContains(primera, 'tipo=MP')
        self.assertContains(primera, 'q=filtro')
        self.assertContains(primera, 'page=2')
        segunda = cliente.get(reverse('mae.articulos'), {'tipo': 'MP', 'q': 'filtro', 'page': 2})
        self.assertEqual(segunda.status_code, 200)
        self.assertContains(segunda, 'MP-FILTRO-20')
        self.assertNotContains(segunda, 'MP-FILTRO-00')
        self.assertNotContains(segunda, 'PT-POL-PIQ-B')
        self.assertContains(segunda, 'tipo=MP')
        self.assertContains(segunda, 'q=filtro')
