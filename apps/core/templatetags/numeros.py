from django import template

from apps.core.numeros import formato_cantidad, formato_costo, formato_soles

register = template.Library()


@register.filter(name='cantidad')
def filtro_cantidad(valor):
    return formato_cantidad(valor)


@register.filter(name='costo')
def filtro_costo(valor):
    return formato_costo(valor)


@register.filter(name='soles')
def filtro_soles(valor):
    return formato_soles(valor)
