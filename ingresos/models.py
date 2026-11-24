from categorias.models import TipoMovimiento
from movimientos.models import MovimientoFinanciero


class Ingreso(MovimientoFinanciero):
    """
    Proxy: usa la tabla de MovimientoFinanciero, pero solo ve y crea
    movimientos de tipo INGRESO. No crea una tabla nueva.
    """

    TIPO = TipoMovimiento.INGRESO

    class Meta:
        proxy = True
        verbose_name = 'ingreso'
        verbose_name_plural = 'ingresos'
        ordering = ['-fecha', '-id']
        # "change" se usará para corregir (Fase 4). Sin "delete": nunca se eliminan.
        default_permissions = ('add', 'change', 'view')
        permissions = [
            ('ver_todos_ingresos', 'Ver ingresos de todos los usuarios'),
        ]