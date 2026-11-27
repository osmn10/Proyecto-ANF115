import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from categorias.models import Categoria, TipoMovimiento
from categorias.predeterminadas import crear_predeterminadas
from core.datos_prueba import borrar_movimientos, generar_correcciones, generar_movimientos, usuarios_disponibles
from movimientos.models import MovimientoFinanciero


class Command(BaseCommand):
    help = (
        'Genera ingresos y gastos de prueba con datos variados y realistas, repartidos en los '
        'últimos meses, usando las categorías activas. Solo para desarrollo.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--cantidad', type=int, default=150, help='Cuántos movimientos crear (por defecto 150).')
        parser.add_argument('--meses', type=int, default=6, help='Cuántos meses hacia atrás repartir (por defecto 6).')
        parser.add_argument('--usuarios', nargs='+', metavar='USUARIO',
                            help='Registrar los movimientos a nombre de estos usuarios (por defecto, todos los activos).')
        parser.add_argument('--correcciones', type=int, default=0,
                            help='Cuántos de los movimientos creados se corrigen para generar historial (por defecto 0).')
        parser.add_argument('--semilla', type=int, help='Número para obtener siempre los mismos datos.')
        parser.add_argument('--limpiar', action='store_true',
                            help='Elimina antes todos los movimientos existentes.')
        parser.add_argument('--forzar', action='store_true', help='Permitir ejecutarlo con DEBUG=False.')

    def handle(self, *args, **opciones):
        if not settings.DEBUG and not opciones['forzar']:
            raise CommandError('DEBUG está en False: este comando es solo para desarrollo. '
                               'Usa --forzar si estás seguro.')
        cantidad, meses, correcciones = opciones['cantidad'], opciones['meses'], opciones['correcciones']
        if cantidad < 1 or meses < 1 or correcciones < 0:
            raise CommandError('--cantidad y --meses deben ser mayores que cero y --correcciones no puede ser negativo.')
        if correcciones > cantidad:
            raise CommandError('--correcciones no puede superar a --cantidad.')

        usuarios = usuarios_disponibles(opciones['usuarios'])
        if opciones['usuarios']:
            faltan = set(opciones['usuarios']) - {u.username for u in usuarios}
            if faltan:
                raise CommandError(f'No existen usuarios activos con el nombre: {", ".join(sorted(faltan))}.')
        if not usuarios:
            raise CommandError('No hay usuarios activos a cuyo nombre registrar los movimientos. '
                               'Crea uno con: python manage.py createsuperuser')

        rng = random.Random(opciones['semilla'])
        crear_predeterminadas(Categoria)  # por si falta alguna del catalogo base

        if opciones['limpiar']:
            borrados, _ = borrar_movimientos()
            self.stdout.write(f'Se eliminaron {borrados} movimientos anteriores.')

        creados = generar_movimientos(cantidad, meses, rng, usuarios)
        hechas = generar_correcciones(creados, correcciones, rng, usuarios) if correcciones else 0

        ingresos = sum(1 for m in creados if m.tipo == TipoMovimiento.INGRESO)
        self.stdout.write(self.style.SUCCESS(
            f'Creados {len(creados)} movimientos ({ingresos} ingresos y {len(creados) - ingresos} gastos) '
            f'a nombre de {len(usuarios)} usuario(s).'))
        if correcciones:
            self.stdout.write(f'Correcciones aplicadas: {hechas}.')
        if opciones['semilla'] is not None:
            self.stdout.write(f'Semilla usada: {opciones["semilla"]}.')

        totales = {
            tipo: MovimientoFinanciero.objects.filter(tipo=tipo).aggregate(total=Sum('monto'))['total'] or 0
            for tipo in TipoMovimiento.values
        }
        self.stdout.write('Totales en la base de datos (incluye lo que ya había):')
        self.stdout.write(f'  Ingresos: ${totales[TipoMovimiento.INGRESO]:,.2f}')
        self.stdout.write(f'  Gastos:   ${totales[TipoMovimiento.GASTO]:,.2f}')
        self.stdout.write(f'  Resultado: ${totales[TipoMovimiento.INGRESO] - totales[TipoMovimiento.GASTO]:,.2f}')