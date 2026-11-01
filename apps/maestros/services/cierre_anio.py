from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.almacen.models import StockActual
from apps.almacen.services.saldo_inicial import registrar_saldo_inicial
from apps.maestros.models import Anio


def cerrar(anio_id, usuario):
    """Pasa el stock final del año N como saldo inicial de N+1 y marca N cerrado."""
    with transaction.atomic():
        anio = Anio.objects.select_for_update().get(pk=anio_id) if _soporta_bloqueo() else Anio.objects.get(pk=anio_id)
        if anio.cerrado:
            raise ValidationError('El año ya está cerrado.')
        siguiente, _ = Anio.objects.get_or_create(
            anio=anio.anio + 1,
            defaults={'activo': False, 'cerrado': False},
        )
        if siguiente.cerrado:
            raise ValidationError('El año siguiente está cerrado. No se pasó el saldo.')
        stocks = list(
            StockActual.objects.select_related('almacen', 'articulo')
            .filter(anio=anio)
            .filter(Q(cantidad__gt=0) | Q(valor__gt=0))
        )
        copiados = 0
        for stock in stocks:
            if stock.cantidad <= 0:
                continue
            try:
                registrar_saldo_inicial(
                    anio=siguiente,
                    almacen=stock.almacen,
                    articulo=stock.articulo,
                    cantidad=stock.cantidad,
                    costo_unitario=stock.costo_promedio,
                    usuario=usuario,
                )
            except ValidationError as exc:
                mensaje = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                raise ValidationError(
                    f'No se pudo pasar el saldo de {stock.articulo.codigo} '
                    f'en {stock.almacen.codigo}: {mensaje}'
                ) from exc
            copiados += 1
        anio.cerrado = True
        anio.activo = False
        anio.fecha_cierre = timezone.now()
        anio.cerrado_por = usuario
        anio.save()
        if not Anio.objects.filter(activo=True).exists():
            siguiente.activo = True
            siguiente.save()
        return siguiente, copiados


def _soporta_bloqueo():
    from django.db import connection

    return connection.features.has_select_for_update
