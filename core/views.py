from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from finanzas.consultas import resumen_periodo


@login_required
def home(request):
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    puede_ver_resumen = request.user.has_perms(['ingresos.view_ingreso', 'gastos.view_gasto'])
    contexto = {
        'resumen_disponible': puede_ver_resumen,
        'inicio_periodo': inicio_mes,
        'fin_periodo': hoy,
    }
    if puede_ver_resumen:
        contexto.update(resumen_periodo(request.user, inicio_mes, hoy))
    return render(request, 'core/home.html', contexto)
