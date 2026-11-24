from movimientos.forms import MovimientoForm

from .models import Gasto


class GastoForm(MovimientoForm):

    class Meta(MovimientoForm.Meta):
        model = Gasto