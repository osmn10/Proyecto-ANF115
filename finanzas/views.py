import csv
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import CharField, Q, Sum
from django.db.models.functions import Cast, Substr
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.formats import date_format

from categorias.models import Categoria
from gastos.models import Gasto
from ingresos.models import Ingreso
from movimientos.models import MovimientoFinanciero
from .consultas import movimientos_visibles_combinados, resumir


def _fechas(request):
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    desde_raw, hasta_raw = request.GET.get('desde', ''), request.GET.get('hasta', '')
    desde = parse_date(desde_raw) if desde_raw else inicio_mes
    hasta = parse_date(hasta_raw) if hasta_raw else hoy
    if not desde or not hasta:
        messages.error(request, 'Ingresa un rango de fechas válido.')
        return inicio_mes, hoy
    if desde > hasta:
        messages.error(request, 'La fecha inicial debe ser anterior a la fecha final.')
        return inicio_mes, hoy
    return desde, hasta


@login_required
@permission_required('ingresos.view_ingreso', raise_exception=True)
@permission_required('gastos.view_gasto', raise_exception=True)
def panel_financiero(request):
    hoy = timezone.localdate()
    desde = hoy.replace(day=1)
    movimientos = movimientos_visibles_combinados(request.user).filter(
        activo=True, fecha__range=(desde, hoy),
    )
    resumen = resumir(movimientos)
    total_movimientos = resumen['ingresos'] + resumen['gastos']
    porcentaje_ingresos = (
        float(resumen['ingresos'] / total_movimientos * 100) if total_movimientos else 0
    )
    porcentaje_gastos_grafico = (
        float(resumen['gastos'] / total_movimientos * 100) if total_movimientos else 0
    )

    categorias = list(movimientos.values('categoria__nombre', 'tipo').annotate(
        total=Sum('monto'),
    ).order_by('-total')[:6])
    max_categoria = max((c['total'] for c in categorias), default=Decimal('0'))
    for categoria in categorias:
        categoria['ancho'] = float(categoria['total'] / max_categoria * 100) if max_categoria else 0

    return render(request, 'finanzas/panel_financiero.html', {
        **resumen,
        'desde': desde,
        'hasta': hoy,
        'total_movimientos': total_movimientos,
        'porcentaje_ingresos_grafico': porcentaje_ingresos,
        'porcentaje_gastos_grafico': porcentaje_gastos_grafico,
        'categorias_grafico': categorias,
    })


@login_required
@permission_required('ingresos.view_ingreso', raise_exception=True)
@permission_required('gastos.view_gasto', raise_exception=True)
def reportes(request):
    desde, hasta = _fechas(request)
    movimientos = movimientos_visibles_combinados(request.user).filter(
        activo=True, fecha__range=(desde, hasta),
    )
    categorias = Categoria.objects.all().order_by('tipo', 'nombre')
    categoria_id = request.GET.get('categoria', '')
    categoria_seleccionada = None
    if categoria_id:
        try:
            categoria_seleccionada = categorias.get(pk=int(categoria_id))
            movimientos = movimientos.filter(categoria=categoria_seleccionada)
        except (ValueError, Categoria.DoesNotExist):
            categoria_id = ''

    agrupacion = request.GET.get('agrupar', 'mensual')
    truncaciones = {
        'diario': (Substr(Cast('fecha', output_field=CharField()), 1, 10), 'Día'),
        'mensual': (Substr(Cast('fecha', output_field=CharField()), 1, 7), 'Mes'),
        'anual': (Substr(Cast('fecha', output_field=CharField()), 1, 4), 'Año'),
    }
    if agrupacion not in truncaciones:
        agrupacion = 'mensual'

    resumen = resumir(movimientos)
    campo_periodo, nombre_periodo = truncaciones[agrupacion]
    filas = list(movimientos.annotate(periodo=campo_periodo).values('periodo').annotate(
        ingresos=Sum('monto', filter=Q(tipo=Ingreso.TIPO)),
        gastos=Sum('monto', filter=Q(tipo=Gasto.TIPO)),
    ).order_by('periodo'))
    maximo = max((max(f['ingresos'] or 0, f['gastos'] or 0) for f in filas), default=Decimal('0'))
    for fila in filas:
        fila['ingresos'] = fila['ingresos'] or Decimal('0.00')
        fila['gastos'] = fila['gastos'] or Decimal('0.00')
        fila['resultado'] = fila['ingresos'] - fila['gastos']
        fila['porcentaje_gastos'] = fila['gastos'] / fila['ingresos'] * 100 if fila['ingresos'] else None
        fila['ancho_ingresos'] = float(fila['ingresos'] / maximo * 100) if maximo else 0
        fila['ancho_gastos'] = float(fila['gastos'] / maximo * 100) if maximo else 0
        if agrupacion == 'diario':
            fila['etiqueta'] = date_format(parse_date(fila['periodo']), 'd/m/Y')
        elif agrupacion == 'mensual':
            fila['etiqueta'] = date_format(parse_date(fila['periodo'] + '-01'), 'F Y')
        else:
            fila['etiqueta'] = fila['periodo']

    if request.GET.get('exportar') == 'csv':
        respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
        respuesta['Content-Disposition'] = 'attachment; filename="reporte_financiero.csv"'
        respuesta.write('\ufeff')
        escritor = csv.writer(respuesta)
        escritor.writerow([nombre_periodo, 'Ingresos', 'Gastos', 'Resultado', '% gastos'])
        for fila in filas:
            porcentaje = f"{fila['porcentaje_gastos']:.2f}%" if fila['porcentaje_gastos'] is not None else 'N/D'
            escritor.writerow([
                fila['etiqueta'], fila['ingresos'], fila['gastos'], fila['resultado'], porcentaje,
            ])
        total_porcentaje = f"{resumen['porcentaje_gastos']:.2f}%" if resumen['porcentaje_gastos'] is not None else 'N/D'
        escritor.writerow(['Total del período', resumen['ingresos'], resumen['gastos'], resumen['resultado'], total_porcentaje])
        return respuesta

    return render(request, 'finanzas/reportes.html', {
        **resumen,
        'filas': filas,
        'categorias': categorias,
        'categoria_id': str(categoria_seleccionada.pk) if categoria_seleccionada else '',
        'desde': desde,
        'hasta': hasta,
        'agrupacion': agrupacion,
        'nombre_periodo': nombre_periodo,
    })
