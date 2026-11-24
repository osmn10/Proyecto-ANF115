"""
Consultas compartidas por ingresos y gastos.
Cada proxy define PERMISO_VER_TODOS (p. ej. 'ingresos.ver_todos_ingresos').
"""


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