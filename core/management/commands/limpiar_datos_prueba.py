from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.datos_prueba import (
    borrar_categorias_no_predeterminadas, borrar_movimientos, categorias_no_predeterminadas,
)
from movimientos.models import CorreccionMovimiento, MovimientoFinanciero


class Command(BaseCommand):
    help = (
        'Elimina los ingresos, gastos y correcciones de la base de datos (datos de prueba). '
        'No toca usuarios, roles ni las categorias predeterminadas. Solo para desarrollo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--categorias', action='store_true',
            help='Tambien elimina las categorias que no son predeterminadas y que ningun movimiento usa.')
        parser.add_argument('--si', action='store_true', help='No pedir confirmacion.')
        parser.add_argument('--forzar', action='store_true', help='Permitir ejecutarlo con DEBUG=False.')

    def handle(self, *args, **opciones):
        if not settings.DEBUG and not opciones['forzar']:
            raise CommandError('DEBUG está en False: este comando borra datos y es solo para desarrollo. '
                               'Usa --forzar si estás seguro.')

        movimientos = MovimientoFinanciero.objects.count()
        correcciones = CorreccionMovimiento.objects.count()
        propias = categorias_no_predeterminadas() if opciones['categorias'] else []

        self.stdout.write('Se eliminará:')
        self.stdout.write(f'  - {movimientos} movimientos (ingresos y gastos)')
        self.stdout.write(f'  - {correcciones} correcciones del historial')
        if opciones['categorias']:
            self.stdout.write(f'  - hasta {len(propias)} categorías no predeterminadas (las que estén en uso se conservan):')
            for categoria in propias:
                self.stdout.write(f'      * {categoria.nombre} ({categoria.get_tipo_display()})')
        self.stdout.write('No se tocan usuarios, roles ni categorías predeterminadas.')

        if not opciones['si']:
            respuesta = input('Escribe SI para continuar: ')
            if respuesta.strip().lower() not in ('si', 'sí'):
                self.stdout.write(self.style.WARNING('Cancelado. No se borró nada.'))
                return

        borrados, historial = borrar_movimientos()
        self.stdout.write(self.style.SUCCESS(f'Eliminados {borrados} movimientos y {historial} correcciones.'))
        if opciones['categorias']:
            borradas, conservadas = borrar_categorias_no_predeterminadas()
            self.stdout.write(self.style.SUCCESS(f'Eliminadas {borradas} categorías no predeterminadas.'))
            if conservadas:
                self.stdout.write(f'Se conservaron {conservadas} porque aún tienen movimientos.')