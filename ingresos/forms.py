from movimientos.forms import MovimientoForm

from .models import Ingreso


class IngresoForm(MovimientoForm):

    class Meta(MovimientoForm.Meta):
        model = Ingreso