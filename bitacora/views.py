from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import EventoBitacora


@login_required
@permission_required('bitacora.view_eventobitacora', raise_exception=True)
def lista_eventos(request):
    eventos = EventoBitacora.objects.select_related('usuario').all()
    accion = request.GET.get('accion', '')
    busqueda = request.GET.get('buscar', '').strip()
    desde_raw = request.GET.get('desde', '')
    hasta_raw = request.GET.get('hasta', '')

    if accion in EventoBitacora.Accion.values:
        eventos = eventos.filter(accion=accion)
    else:
        accion = ''

    if busqueda:
        eventos = eventos.filter(
            Q(resumen__icontains=busqueda)
            | Q(entidad__icontains=busqueda)
            | Q(entidad_id__icontains=busqueda)
            | Q(usuario__username__icontains=busqueda)
        )

    desde = parse_date(desde_raw) if desde_raw else None
    hasta = parse_date(hasta_raw) if hasta_raw else None
    if desde_raw and not desde:
        desde_raw = ''
    if hasta_raw and not hasta:
        hasta_raw = ''
    if desde and hasta and desde > hasta:
        desde, hasta = None, None
        desde_raw, hasta_raw = '', ''
    if desde:
        inicio = timezone.make_aware(datetime.combine(desde, time.min))
        eventos = eventos.filter(fecha_creacion__gte=inicio)
    if hasta:
        dia_siguiente = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
        eventos = eventos.filter(fecha_creacion__lt=dia_siguiente)

    paginador = Paginator(eventos, 30)
    pagina = paginador.get_page(request.GET.get('pagina'))
    return render(request, 'bitacora/lista_eventos.html', {
        'pagina': pagina,
        'acciones': EventoBitacora.Accion.choices,
        'accion_seleccionada': accion,
        'busqueda': busqueda,
        'desde': desde_raw,
        'hasta': hasta_raw,
        'total_eventos': paginador.count,
    })
