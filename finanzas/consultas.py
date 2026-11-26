from decimal import Decimal

from django.db.models import Q, Sum

from gastos.models import Gasto
from ingresos.models import Ingreso
from movimientos.consultas import movimientos_visibles
from movimientos.models import MovimientoFinanciero


def movimientos_visibles_combinados(usuario):
    """Devuelve los ingresos y gastos que el usuario tiene permiso de consultar."""
    ingresos = movimientos_visibles(Ingreso, usuario).values('pk')
    gastos = movimientos_visibles(Gasto, usuario).values('pk')
    return MovimientoFinanciero.objects.filter(Q(pk__in=ingresos) | Q(pk__in=gastos))


def resumir(movimientos):
    totales = movimientos.aggregate(
        ingresos=Sum('monto', filter=Q(tipo=Ingreso.TIPO)),
        gastos=Sum('monto', filter=Q(tipo=Gasto.TIPO)),
    )
    ingresos = totales['ingresos'] or Decimal('0.00')
    gastos = totales['gastos'] or Decimal('0.00')
    return {
        'ingresos': ingresos,
        'gastos': gastos,
        'resultado': ingresos - gastos,
        'porcentaje_gastos': gastos / ingresos * 100 if ingresos else None,
    }


def resumen_periodo(usuario, desde, hasta):
    movimientos = movimientos_visibles_combinados(usuario).filter(
        activo=True,
        fecha__range=(desde, hasta),
    )
    return resumir(movimientos)
