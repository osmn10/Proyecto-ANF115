from django.db import models
from django.db.models.functions import Lower

from core.models import ModeloBase


class TipoMovimiento(models.TextChoices):
    INGRESO = 'INGRESO', 'Ingreso'
    GASTO = 'GASTO', 'Gasto'


class Categoria(ModeloBase):
    """
    Catálogo para clasificar movimientos. Hereda de ModeloBase:
    fecha_creacion, fecha_modificacion y activo (activa / desactivada).
    """

    nombre = models.CharField('nombre', max_length=80)
    tipo = models.CharField('tipo', max_length=7, choices=TipoMovimiento.choices)

    class Meta:
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'
        ordering = ['tipo', 'nombre']
        # Sin permiso "delete": las categorías nunca se eliminan, solo se desactivan
        default_permissions = ('add', 'change', 'view')
        constraints = [
            models.UniqueConstraint(
                Lower('nombre'), 'tipo',
                name='categoria_nombre_tipo_unico',
                violation_error_message='Ya existe una categoría con ese nombre para este tipo.',
            ),
        ]

    def __str__(self):
        return self.nombre

    def esta_en_uso(self):
        """True si algún modelo (p. ej. movimientos) apunta a esta categoría."""
        for relacion in self._meta.related_objects:
            if getattr(self, relacion.get_accessor_name()).exists():
                return True
        return False