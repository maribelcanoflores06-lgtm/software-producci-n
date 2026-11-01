from django.contrib import messages
from django.db import transaction
from django.forms.models import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from apps.core.authz import puede
from apps.core.views import PantallaMixin
from apps.maestros.forms import (
    RecetaForm,
    RecetaLineaForm,
    RecetaLineasFormSet,
    RutaForm,
    RutaLineaForm,
    RutaLineasFormSet,
)
from apps.maestros.models import Receta, RecetaDetalle, Ruta, RutaProceso


def _solo(request, codigo):
    return not puede(request.user, codigo, escribir=True)


def _bloquear(formset):
    for form in formset.forms:
        for field in form.fields.values():
            field.disabled = True


def formset_receta(instancia, data=None):
    Formulario = inlineformset_factory(
        Receta,
        RecetaDetalle,
        form=RecetaLineaForm,
        formset=RecetaLineasFormSet,
        extra=0 if instancia.pk else 1,
        can_delete=True,
    )
    if instancia.pk:
        queryset = instancia.detalles.select_related('articulo_insumo').order_by('articulo_insumo__codigo')
    else:
        queryset = RecetaDetalle.objects.none()
    return Formulario(data, instance=instancia, prefix='detalles', queryset=queryset)


def formset_ruta(instancia, data=None):
    Formulario = inlineformset_factory(
        Ruta,
        RutaProceso,
        form=RutaLineaForm,
        formset=RutaLineasFormSet,
        extra=0 if instancia.pk else 1,
        can_delete=True,
    )
    if instancia.pk:
        queryset = instancia.pasos.select_related('proceso').order_by('secuencia')
    else:
        queryset = RutaProceso.objects.none()
    return Formulario(data, instance=instancia, prefix='pasos', queryset=queryset)


class RecetaFormView(PantallaMixin, TemplateView):
    pantalla_codigo = 'mae.recetas'
    template_name = 'maestros/formulario_lineas.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        pk = kwargs.get('pk')
        self.objeto = get_object_or_404(Receta.objects.select_related('articulo_pt'), pk=pk) if pk else None

    def _instancia(self):
        return self.objeto or Receta()

    def _render(self, form, formset):
        return self.render_to_response({
            'form': form,
            'formset': formset,
            'titulo': 'Editar receta' if self.objeto else 'Nueva receta',
            'url_lista': reverse('mae.recetas'),
            'prefijo': 'detalles',
            'sin_cabecera': not form.fields['articulo_pt'].queryset.exists() and self.objeto is None,
            'texto_vacio': 'No hay productos terminados libres. Cree un artículo de tipo PT que aún no tenga receta.',
            'ayuda': 'Las cantidades son para el lote base. La orden de producción escala sobre ese número.',
        })

    def get(self, request, *args, **kwargs):
        lectura = _solo(request, self.pantalla_codigo)
        form = RecetaForm(instance=self._instancia(), solo_lectura=lectura)
        formset = formset_receta(self._instancia())
        if lectura:
            _bloquear(formset)
        return self._render(form, formset)

    def post(self, request, *args, **kwargs):
        instancia = self._instancia()
        form = RecetaForm(request.POST, instance=instancia)
        formset = formset_receta(instancia, request.POST)
        valido = form.is_valid()
        if valido:
            formset.pt_id = form.cleaned_data['articulo_pt'].pk
        if valido and formset.is_valid():
            with transaction.atomic():
                receta = form.save()
                receta.detalles.all().delete()
                for linea in formset.forms:
                    data = getattr(linea, 'cleaned_data', None) or {}
                    if not data or data.get('DELETE'):
                        continue
                    insumo = data.get('articulo_insumo')
                    cantidad = data.get('cantidad_por_lote')
                    if not insumo or not cantidad:
                        continue
                    RecetaDetalle.objects.create(
                        receta=receta,
                        articulo_insumo=insumo,
                        cantidad_por_lote=cantidad,
                    )
            messages.success(request, 'Receta guardada.')
            return redirect('mae.recetas')
        return self._render(form, formset)


class RutaFormView(PantallaMixin, TemplateView):
    pantalla_codigo = 'mae.rutas'
    template_name = 'maestros/formulario_lineas.html'

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        pk = kwargs.get('pk')
        self.objeto = get_object_or_404(Ruta, pk=pk) if pk else None

    def _instancia(self):
        return self.objeto or Ruta()

    def _render(self, form, formset):
        return self.render_to_response({
            'form': form,
            'formset': formset,
            'titulo': 'Editar ruta' if self.objeto else 'Nueva ruta',
            'url_lista': reverse('mae.rutas'),
            'prefijo': 'pasos',
            'sin_cabecera': False,
            'texto_vacio': '',
            'ayuda': 'La ruta es independiente del producto terminado. Ordena procesos, no artículos.',
        })

    def get(self, request, *args, **kwargs):
        lectura = _solo(request, self.pantalla_codigo)
        form = RutaForm(instance=self._instancia(), solo_lectura=lectura)
        formset = formset_ruta(self._instancia())
        if lectura:
            _bloquear(formset)
        return self._render(form, formset)

    def post(self, request, *args, **kwargs):
        instancia = self._instancia()
        form = RutaForm(request.POST, instance=instancia)
        formset = formset_ruta(instancia, request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                ruta = form.save()
                ruta.pasos.all().delete()
                for linea in formset.forms:
                    data = getattr(linea, 'cleaned_data', None) or {}
                    if not data or data.get('DELETE'):
                        continue
                    proceso = data.get('proceso')
                    secuencia = data.get('secuencia')
                    if not proceso or secuencia is None:
                        continue
                    RutaProceso.objects.create(ruta=ruta, proceso=proceso, secuencia=secuencia)
            messages.success(request, 'Ruta guardada.')
            return redirect('mae.rutas')
        return self._render(form, formset)
