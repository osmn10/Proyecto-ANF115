from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from bitacora.models import EventoBitacora
from bitacora.servicios import registrar_evento
from movimientos.consultas import movimientos_visibles, paginar, puede_ver_todos, resumir
from movimientos.forms import FiltroMovimientosForm
from movimientos.servicios import ConflictoDeVersion

from .forms import IngresoCorreccionForm, IngresoForm
from .models import Ingreso


@login_required
@permission_required('ingresos.view_ingreso', raise_exception=True)
def lista_ingresos(request):
    ingresos = movimientos_visibles(Ingreso, request.user)
    filtros = FiltroMovimientosForm(request.GET, tipo=Ingreso.TIPO)

    contexto = {
        'filtros': filtros,
        've_todos': puede_ver_todos(Ingreso, request.user),
    }
    # Con filtros inválidos (p. ej. rango invertido) se muestra el error y ningún
    # resultado, para no presentar cifras que no corresponden a lo pedido.
    if filtros.is_valid():
        ingresos = filtros.filtrar(ingresos)
        contexto['resumen'] = resumir(ingresos)
        contexto['pagina'], contexto['rango'] = paginar(request, ingresos)
    return render(request, 'ingresos/lista_ingresos.html', contexto)


@login_required
@permission_required('ingresos.add_ingreso', raise_exception=True)
def registrar_ingreso(request):
    if request.method == 'POST':
        form = IngresoForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.creado_por = request.user  # el autor siempre sale de la sesión
            ingreso.save()
            registrar_evento(
                usuario=request.user,
                accion=EventoBitacora.Accion.INGRESO_CREADO,
                resumen=f'Ingreso #{ingreso.pk}: {ingreso.concepto}',
                entidad='Ingreso',
                entidad_id=ingreso.pk,
                detalles={
                    'monto': str(ingreso.monto),
                    'fecha': ingreso.fecha.isoformat(),
                    'categoria': ingreso.categoria.nombre,
                },
            )
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
    contexto = {
        'ingreso': ingreso,
        've_todos': puede_ver_todos(Ingreso, request.user),
    }
    # El historial de correcciones solo lo ve quien puede corregir (administrador)
    if request.user.has_perm('ingresos.change_ingreso'):
        contexto['correcciones'] = ingreso.correcciones.select_related('realizado_por')
    return render(request, 'ingresos/detalle_ingreso.html', contexto)


@login_required
@permission_required('ingresos.change_ingreso', raise_exception=True)
def corregir_ingreso(request, id):
    # Mismo alcance que la consulta: sin "ver todos" solo se corrigen los propios
    ingreso = get_object_or_404(movimientos_visibles(Ingreso, request.user), pk=id)
    if request.method == 'POST':
        form = IngresoCorreccionForm(request.POST, instance=ingreso)
        if form.is_valid():
            try:
                form.guardar_correccion(request.user)
            except ConflictoDeVersion:
                # Otra persona corrigió el registro mientras esta pantalla estaba abierta
                messages.error(
                    request,
                    'El registro cambió. Recarga antes de guardar: revisa los valores actuales '
                    'y vuelve a aplicar tu corrección.')
                return redirect('ingresos:corregir_ingreso', id=id)
            messages.success(request, f'Ingreso #{id} corregido correctamente.')
            return redirect('ingresos:detalle_ingreso', id=id)
    else:
        form = IngresoCorreccionForm(instance=ingreso)
    return render(request, 'ingresos/corregir_ingreso.html', {'form': form, 'ingreso': ingreso})
