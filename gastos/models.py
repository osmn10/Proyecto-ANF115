from django.db import models

# Create your models here.
from categorias.models import TipoMovimiento
from movimientos.models import MovimientoFinanciero


class Gasto(MovimientoFinanciero):
    """
    Proxy: usa la tabla de MovimientoFinanciero, pero solo ve y crea
    movimientos de tipo GASTO. No crea una tabla nueva.
    """

    TIPO = TipoMovimiento.GASTO
    PERMISO_VER_TODOS = 'gastos.ver_todos_gastos'

    class Meta:
        proxy = True
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        ordering = ['-fecha', '-id']
        # "change" se usará para corregir (Fase 4). Sin "delete": nunca se eliminan.
        default_permissions = ('add', 'change', 'view')
        permissions = [
            ('ver_todos_gastos', 'Ver gastos de todos los usuarios'),
        ]