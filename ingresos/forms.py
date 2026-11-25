from movimientos.forms import CorreccionMovimientoForm, MovimientoForm

from .models import Ingreso


class IngresoForm(MovimientoForm):

    class Meta(MovimientoForm.Meta):
        model = Ingreso


class IngresoCorreccionForm(CorreccionMovimientoForm):

    class Meta(CorreccionMovimientoForm.Meta):
        model = Ingreso