from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from movimientos.consultas import movimientos_visibles, paginar, puede_ver_todos, resumir
from movimientos.forms import FiltroMovimientosForm

from .forms import GastoForm
from .models import Gasto


@login_required
@permission_required('gastos.view_gasto', raise_exception=True)
def lista_gastos(request):
    gastos = movimientos_visibles(Gasto, request.user)
    filtros = FiltroMovimientosForm(request.GET, tipo=Gasto.TIPO)

    contexto = {
        'filtros': filtros,
        've_todos': puede_ver_todos(Gasto, request.user),
    }
    # Con filtros inválidos (p. ej. rango invertido) se muestra el error y ningún
    # resultado, para no presentar cifras que no corresponden a lo pedido.
    if filtros.is_valid():
        gastos = filtros.filtrar(gastos)
        contexto['resumen'] = resumir(gastos)
        contexto['pagina'], contexto['rango'] = paginar(request, gastos)
    return render(request, 'gastos/lista_gastos.html', contexto)


@login_required
@permission_required('gastos.add_gasto', raise_exception=True)
def registrar_gasto(request):
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.creado_por = request.user  # el autor siempre sale de la sesión
            gasto.save()
            messages.success(request, f'Gasto #{gasto.pk} registrado correctamente.')
            # Redirigir después del POST evita que "recargar" registre el gasto dos veces
            return redirect('gastos:detalle_gasto', id=gasto.pk)
    else:
        form = GastoForm()
    return render(request, 'gastos/registrar_gasto.html', {'form': form})


@login_required
@permission_required('gastos.view_gasto', raise_exception=True)
def detalle_gasto(request, id):
    # Si el gasto es de otro usuario y no tiene "ver todos", responde 404
    gasto = get_object_or_404(movimientos_visibles(Gasto, request.user), pk=id)
    return render(request, 'gastos/detalle_gasto.html', {
        'gasto': gasto,
        've_todos': puede_ver_todos(Gasto, request.user),
    })