from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import ModeloBase


class EventoBitacora(ModeloBase):
    class Accion(models.TextChoices):
        INGRESO_CREADO = 'ingreso_creado', 'Ingreso registrado'
        GASTO_CREADO = 'gasto_creado', 'Gasto registrado'
        MOVIMIENTO_CORREGIDO = 'movimiento_corregido', 'Movimiento corregido'
        CATEGORIA_CREADA = 'categoria_creada', 'Categoría creada'
        CATEGORIA_EDITADA = 'categoria_editada', 'Categoría modificada'
        CATEGORIA_ESTADO = 'categoria_estado', 'Estado de categoría cambiado'
        USUARIO_CREADO = 'usuario_creado', 'Usuario creado'
        USUARIO_EDITADO = 'usuario_editado', 'Usuario modificado'
        USUARIO_DESACTIVADO = 'usuario_desactivado', 'Usuario desactivado'
        PASSWORD_REINICIADA = 'password_reiniciada', 'Contraseña restablecida'
        PASSWORD_CAMBIADA = 'password_cambiada', 'Contraseña cambiada'
        ROL_CREADO = 'rol_creado', 'Rol creado'
        ROL_EDITADO = 'rol_editado', 'Rol modificado'
        ROL_ELIMINADO = 'rol_eliminado', 'Rol eliminado'
        USUARIO_AGREGADO_ROL = 'usuario_agregado_rol', 'Usuario agregado a un rol'
        USUARIO_QUITADO_ROL = 'usuario_quitado_rol', 'Usuario retirado de un rol'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='eventos_bitacora',
        verbose_name='realizado por',
    )
    accion = models.CharField(max_length=32, choices=Accion.choices)
    resumen = models.CharField(max_length=255)
    entidad = models.CharField(max_length=60)
    entidad_id = models.CharField(max_length=64, blank=True)
    detalles = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'evento de bitácora'
        verbose_name_plural = 'eventos de bitácora'
        ordering = ('-fecha_creacion', '-pk')
        default_permissions = ('view',)
        indexes = [
            models.Index(fields=('fecha_creacion', 'accion'), name='bitacora_fecha_accion_idx'),
        ]

    def __str__(self):
        return f'{self.get_accion_display()} · {self.usuario}'

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Los eventos de bitácora son inmutables.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los eventos de bitácora no se pueden eliminar.')
