from django.db import migrations


def rellenar_correlativos(apps, schema_editor):
    """Bases que ya tienen años y almacenes quedan con correlativo 0 donde faltaba la fila."""
    Anio = apps.get_model('maestros', 'Anio')
    Almacen = apps.get_model('maestros', 'Almacen')
    CorrelativoNota = apps.get_model('maestros', 'CorrelativoNota')
    CorrelativoOp = apps.get_model('maestros', 'CorrelativoOp')
    almacenes = list(Almacen.objects.all().only('id'))
    for anio in Anio.objects.all().only('id'):
        CorrelativoOp.objects.get_or_create(anio_id=anio.id, defaults={'ultimo': 0})
        for almacen in almacenes:
            CorrelativoNota.objects.get_or_create(
                anio_id=anio.id,
                almacen_id=almacen.id,
                defaults={'ultimo': 0},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('maestros', '0003_maquina_proceso_maestro'),
    ]

    operations = [
        migrations.RunPython(rellenar_correlativos, migrations.RunPython.noop),
    ]
