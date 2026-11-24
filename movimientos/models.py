from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from core.models import ModeloBase


def validar_fecha_no_futura(fecha):
    """RN03 (provisional D05): no se registran operaciones con fecha posterior a hoy."""
    if fecha and fecha > timezone.localdate():
        raise ValidationError('La fecha no puede ser posterior a hoy.')


class MovimientoManager(models.Manager):
    """
    En MovimientoFinanciero devuelve todos los movimientos.
    En un proxy (Ingreso, Gasto) devuelve solo los de su tipo, usando el atributo TIPO.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        tipo = getattr(self.model, 'TIPO', None)
        return queryset.filter(tipo=tipo) if tipo else queryset


class MovimientoFinanciero(ModeloBase):
    """
    Tabla única de ingresos y gastos (modelo ER). No se usa directamente en
    pantallas: las apps ingresos y gastos trabajan con sus modelos proxy.
    Hereda de ModeloBase: fecha_creacion, fecha_modificacion y activo (vigente).
    """

    TIPO = None  # cada proxy define su tipo

    tipo = models.CharField('tipo', max_length=7, choices=TipoMovimiento.choices, editable=False)
    concepto = models.CharField('concepto', max_length=250)
    monto = models.DecimalField(
        'monto', max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'), 'El monto debe ser mayor que cero.')],
    )
    fecha = models.DateField('fecha', validators=[validar_fecha_no_futura])
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT,
        related_name='movimientos', verbose_name='categoría',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='movimientos_creados', verbose_name='registrado por', editable=False,
    )
    version = models.PositiveIntegerField('versión', default=1, editable=False)

    objects = MovimientoManager()

    class Meta:
        verbose_name = 'movimiento financiero'
        verbose_name_plural = 'movimientos financieros'
        ordering = ['-fecha', '-id']
        default_permissions = ()  # los permisos viven en los proxies Ingreso y Gasto
        indexes = [models.Index(fields=['tipo', 'fecha'], name='movimiento_tipo_fecha_idx')]
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name='movimiento_monto_positivo'),
            models.CheckConstraint(condition=Q(tipo__in=TipoMovimiento.values), name='movimiento_tipo_valido'),
            models.CheckConstraint(condition=Q(version__gte=1), name='movimiento_version_valida'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} #{self.pk} · {self.concepto}'

    def _asignar_tipo(self):
        if self.TIPO:
            self.tipo = self.TIPO

    def clean(self):
        super().clean()
        self._asignar_tipo()
        if not self.categoria_id:
            return  # el error de "campo obligatorio" ya lo reporta Django

        # RN02: la categoría debe ser del mismo tipo que el movimiento
        if self.categoria.tipo != self.tipo:
            raise ValidationError({'categoria': 'La categoría no corresponde a este tipo de movimiento.'})

        # RN02: solo categorías activas para registros nuevos o al cambiar de categoría.
        # Una categoría que se desactivó después puede conservarse en registros existentes.
        categoria_cambia = self._state.adding or not MovimientoFinanciero.objects.filter(
            pk=self.pk, categoria_id=self.categoria_id).exists()
        if categoria_cambia and not self.categoria.activo:
            raise ValidationError({'categoria': 'Selecciona una categoría activa.'})

    def save(self, *args, **kwargs):
        self._asignar_tipo()
        super().save(*args, **kwargs)