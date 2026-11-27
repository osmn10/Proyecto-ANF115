from django.db import migrations

from categorias.predeterminadas import crear_predeterminadas


def crear_categorias(apps, schema_editor):
    crear_predeterminadas(apps.get_model('categorias', 'Categoria'))


class Migration(migrations.Migration):

    dependencies = [
        ('categorias', '0001_initial'),
    ]

    operations = [
        # Al revertir no se borra nada: las categorias pueden estar en uso por movimientos
        migrations.RunPython(crear_categorias, migrations.RunPython.noop),
    ]