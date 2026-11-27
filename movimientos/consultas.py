"""
Consultas compartidas por ingresos y gastos.
Cada proxy define PERMISO_VER_TODOS (p. ej. 'ingresos.ver_todos_ingresos').
"""
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Sum

POR_PAGINA = 20


def puede_ver_todos(modelo, usuario):
    return usuario.has_perm(modelo.PERMISO_VER_TODOS)


def movimientos_visibles(modelo, usuario):
    """
    RN13: con el permiso "ver todos" se ven los movimientos de toda la empresa;
    sin él, solo los que registró el propio usuario. Se usa en listas Y detalles,
    así un ID ajeno escrito en la URL responde 404.
    """
    movimientos = modelo.objects.select_related('categoria', 'creado_por')
    if puede_ver_todos(modelo, usuario):
        return movimientos
    return movimientos.filter(creado_por=usuario)


def resumir(movimientos):
    """
    Total y cantidad del conjunto COMPLETO filtrado (no solo de la página visible).
    Sin registros, el total es 0.00.
    """
    datos = movimientos.aggregate(total=Sum('monto'), cantidad=Count('id'))
    return {
        'total': datos['total'] or Decimal('0.00'),
        'cantidad': datos['cantidad'],
    }


def paginar(request, movimientos, por_pagina=POR_PAGINA):
    """
    Devuelve la página pedida en ?pagina=N y el rango de números a mostrar.
    Un número inválido o fuera de rango muestra la primera o la última página.
    """
    paginador = Paginator(movimientos, por_pagina)
    pagina = paginador.get_page(request.GET.get('pagina'))
    rango = paginador.get_elided_page_range(pagina.number, on_each_side=1, on_ends=1)
    return pagina, rango