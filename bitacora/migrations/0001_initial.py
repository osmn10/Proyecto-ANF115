from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def importar_correcciones_existentes(apps, schema_editor):
    Correccion = apps.get_model('movimientos', 'CorreccionMovimiento')
    Evento = apps.get_model('bitacora', 'EventoBitacora')
    db = schema_editor.connection.alias
    for correccion in Correccion.objects.using(db).select_related('movimiento').iterator():
        tipo = {
            'INGRESO': 'Ingreso',
            'GASTO': 'Gasto',
        }.get(correccion.movimiento.tipo, 'Movimiento')
        evento = Evento.objects.using(db).create(
            usuario_id=correccion.realizado_por_id,
            accion='movimiento_corregido',
            resumen=f'{tipo} #{correccion.movimiento_id} corregido',
            entidad='Movimiento financiero',
            entidad_id=str(correccion.movimiento_id),
            detalles={
                'motivo': correccion.motivo,
                'antes': correccion.antes,
                'despues': correccion.despues,
                'version_anterior': correccion.version_anterior,
                'version_nueva': correccion.version_nueva,
            },
        )
        Evento.objects.using(db).filter(pk=evento.pk).update(
            fecha_creacion=correccion.fecha_creacion,
            fecha_modificacion=correccion.fecha_creacion,
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('movimientos', '0002_correccionmovimiento'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoBitacora',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_modificacion', models.DateTimeField(auto_now=True)),
                ('activo', models.BooleanField(default=True)),
                ('accion', models.CharField(choices=[
                    ('ingreso_creado', 'Ingreso registrado'),
                    ('gasto_creado', 'Gasto registrado'),
                    ('movimiento_corregido', 'Movimiento corregido'),
                    ('categoria_creada', 'Categoría creada'),
                    ('categoria_editada', 'Categoría modificada'),
                    ('categoria_estado', 'Estado de categoría cambiado'),
                    ('usuario_creado', 'Usuario creado'),
                    ('usuario_editado', 'Usuario modificado'),
                    ('usuario_desactivado', 'Usuario desactivado'),
                    ('password_reiniciada', 'Contraseña restablecida'),
                    ('password_cambiada', 'Contraseña cambiada'),
                    ('rol_creado', 'Rol creado'),
                    ('rol_editado', 'Rol modificado'),
                    ('rol_eliminado', 'Rol eliminado'),
                    ('usuario_agregado_rol', 'Usuario agregado a un rol'),
                    ('usuario_quitado_rol', 'Usuario retirado de un rol'),
                ], max_length=32)),
                ('resumen', models.CharField(max_length=255)),
                ('entidad', models.CharField(max_length=60)),
                ('entidad_id', models.CharField(blank=True, max_length=64)),
                ('detalles', models.JSONField(blank=True, default=dict)),
                ('usuario', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='eventos_bitacora',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='realizado por',
                )),
            ],
            options={
                'verbose_name': 'evento de bitácora',
                'verbose_name_plural': 'eventos de bitácora',
                'ordering': ('-fecha_creacion', '-pk'),
                'default_permissions': ('view',),
            },
        ),
        migrations.AddIndex(
            model_name='eventobitacora',
            index=models.Index(fields=['fecha_creacion', 'accion'], name='bitacora_fecha_accion_idx'),
        ),
        migrations.RunPython(importar_correcciones_existentes, migrations.RunPython.noop),
    ]
