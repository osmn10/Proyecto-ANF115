from movimientos.forms import CorreccionMovimientoForm, MovimientoForm

from .models import Gasto


class GastoForm(MovimientoForm):

    class Meta(MovimientoForm.Meta):
        model = Gasto


class GastoCorreccionForm(CorreccionMovimientoForm):

    class Meta(CorreccionMovimientoForm.Meta):
        model = Gasto