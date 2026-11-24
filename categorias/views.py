from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoriaForm
from .models import Categoria, TipoMovimiento


@login_required
@permission_required('categorias.view_categoria', raise_exception=True)
def lista_categorias(request):
    categorias = Categoria.objects.all()

    # Filtros por GET (?tipo=GASTO&estado=activas)
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    if tipo in TipoMovimiento.values:
        categorias = categorias.filter(tipo=tipo)
    if estado == 'activas':
        categorias = categorias.filter(activo=True)
    elif estado == 'inactivas':
        categorias = categorias.filter(activo=False)

    return render(request, 'categorias/lista_categorias.html', {
        'categorias': categorias,
        'tipos': TipoMovimiento.choices,
        'filtro_tipo': tipo,
        'filtro_estado': estado,
        'hay_filtros': bool(tipo or estado),
    })


@login_required
@permission_required('categorias.add_categoria', raise_exception=True)
def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f'Categoría "{categoria.nombre}" creada correctamente.')
            return redirect('categorias:lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'categorias/form_categoria.html', {'form': form, 'accion': 'Crear'})


@login_required
@permission_required('categorias.change_categoria', raise_exception=True)
def editar_categoria(request, id):
    categoria = get_object_or_404(Categoria, pk=id)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoría actualizada correctamente.')
            return redirect('categorias:lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'categorias/form_categoria.html', {
        'form': form,
        'accion': 'Editar',
        'categoria': categoria,
    })


@login_required
@permission_required('categorias.change_categoria', raise_exception=True)
def cambiar_estado_categoria(request, id, activar):
    """
    Desactiva o reactiva una categoría. Nunca la elimina: sus movimientos
    históricos se conservan. GET muestra la confirmación; POST aplica el cambio.
    """
    categoria = get_object_or_404(Categoria, pk=id)

    if request.method == 'POST':
        categoria.activo = activar
        categoria.save(update_fields=['activo', 'fecha_modificacion'])
        estado = 'reactivada' if activar else 'desactivada'
        messages.success(request, f'Categoría "{categoria.nombre}" {estado} correctamente.')
        return redirect('categorias:lista_categorias')

    return render(request, 'categorias/cambiar_estado_categoria.html', {
        'categoria': categoria,
        'activar': activar,
    })