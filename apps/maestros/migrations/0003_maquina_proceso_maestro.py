import django.db.models.deletion
from django.db import migrations, models


def vaciar_asignaciones_de_almacen(apps, schema_editor):
    """Las filas de 0002 apuntan a almacenes. Ese vínculo no sirve para el maestro Proceso."""
    MaquinaProceso = apps.get_model('maestros', 'MaquinaProceso')
    MaquinaProceso.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('maestros', '0002_maquina'),
    ]

    operations = [
        migrations.RunPython(vaciar_asignaciones_de_almacen, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='maquinaproceso',
            name='proceso',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='usos_en_maquina',
                to='maestros.proceso',
                verbose_name='Proceso',
            ),
        ),
        migrations.AlterField(
            model_name='maquina',
            name='procesos',
            field=models.ManyToManyField(
                related_name='maquinas',
                through='maestros.MaquinaProceso',
                to='maestros.proceso',
                verbose_name='Procesos',
            ),
        ),
    ]
