from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from movimientos.consultas import movimientos_visibles, puede_ver_todos

from .forms import IngresoForm
from .models import Ingreso


@login_required
@permission_required('ingresos.view_ingreso', raise_exception=True)
def lista_ingresos(request):
    ingresos = movimientos_visibles(Ingreso, request.user)
    return render(request, 'ingresos/lista_ingresos.html', {
        'ingresos': ingresos,
        've_todos': puede_ver_todos(Ingreso, request.user),
    })


@login_required
@permission_required('ingresos.add_ingreso', raise_exception=True)
def registrar_ingreso(request):
    if request.method == 'POST':
        form = IngresoForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.creado_por = request.user  # el autor siempre sale de la sesión
            ingreso.save()
            messages.success(request, f'Ingreso #{ingreso.pk} registrado correctamente.')
            # Redirigir después del POST evita que "recargar" registre el ingreso dos veces
            return redirect('ingresos:detalle_ingreso', id=ingreso.pk)
    else:
        form = IngresoForm()
    return render(request, 'ingresos/registrar_ingreso.html', {'form': form})


@login_required
@permission_required('ingresos.view_ingreso', raise_exception=True)
def detalle_ingreso(request, id):
    # Si el ingreso es de otro usuario y no tiene "ver todos", responde 404
    ingreso = get_object_or_404(movimientos_visibles(Ingreso, request.user), pk=id)
    return render(request, 'ingresos/detalle_ingreso.html', {
        'ingreso': ingreso,
        've_todos': puede_ver_todos(Ingreso, request.user),
    })