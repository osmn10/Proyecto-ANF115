"""
Pruebas del catalogo de categorias predeterminadas.

Ejecutar:  python manage.py test categorias.test_predeterminadas
Cubre: las categorias que crea la migracion 0002, que el catalogo este bien formado
       y que crear_predeterminadas() sea idempotente y respete lo que ya existe.
"""
import importlib

from django.apps import apps
from django.test import TestCase

from .models import Categoria, TipoMovimiento
from .predeterminadas import CATEGORIAS_PREDETERMINADAS, crear_predeterminadas


class CatalogoPredeterminadoTests(TestCase):

    def test_la_migracion_crea_todas_las_categorias_activas(self):
        self.assertEqual(Categoria.objects.count(), len(CATEGORIAS_PREDETERMINADAS))
        self.assertFalse(Categoria.objects.filter(activo=False).exists())
        for tipo, nombre in CATEGORIAS_PREDETERMINADAS:
            with self.subTest(categoria=nombre):
                self.assertTrue(Categoria.objects.filter(tipo=tipo, nombre=nombre).exists())

    def test_el_catalogo_esta_bien_formado(self):
        claves = [(tipo, nombre.lower()) for tipo, nombre in CATEGORIAS_PREDETERMINADAS]
        self.assertEqual(len(claves), len(set(claves)), 'Hay nombres repetidos dentro del mismo tipo')
        for tipo, nombre in CATEGORIAS_PREDETERMINADAS:
            with self.subTest(categoria=nombre):
                self.assertIn(tipo, TipoMovimiento.values)
                self.assertEqual(nombre, nombre.strip())
                self.assertTrue(0 < len(nombre) <= 80)

    def test_hay_variedad_de_ingresos_y_de_gastos(self):
        for tipo in TipoMovimiento.values:
            cantidad = sum(1 for t, _ in CATEGORIAS_PREDETERMINADAS if t == tipo)
            self.assertGreaterEqual(cantidad, 6, f'Pocas categorias de tipo {tipo}')

    def test_incluye_los_gastos_que_menciona_la_guia(self):
        nombres = {nombre for tipo, nombre in CATEGORIAS_PREDETERMINADAS if tipo == TipoMovimiento.GASTO}
        for esperado in ('Alquiler de local', 'Servicios básicos', 'Transporte y combustible', 'Suministros y papelería'):
            self.assertIn(esperado, nombres)

    def test_crear_predeterminadas_es_idempotente(self):
        Categoria.objects.all().delete()
        self.assertEqual(crear_predeterminadas(Categoria), len(CATEGORIAS_PREDETERMINADAS))
        self.assertEqual(crear_predeterminadas(Categoria), 0)
        self.assertEqual(Categoria.objects.count(), len(CATEGORIAS_PREDETERMINADAS))

    def test_solo_crea_las_que_faltan(self):
        Categoria.objects.filter(nombre__in=['Seguros', 'Otros ingresos']).delete()
        self.assertEqual(crear_predeterminadas(Categoria), 2)

    def test_respeta_una_categoria_desactivada_o_con_otras_mayusculas(self):
        Categoria.objects.filter(nombre='Seguros').update(activo=False)
        Categoria.objects.filter(nombre='Capacitación').update(nombre='CAPACITACIÓN')
        self.assertEqual(crear_predeterminadas(Categoria), 0)
        self.assertEqual(Categoria.objects.filter(nombre__iexact='Seguros').count(), 1)
        self.assertFalse(Categoria.objects.get(nombre='Seguros').activo)  # no se reactiva
        # (se cuenta en Python: SQLite no distingue mayusculas en letras con tilde)
        capacitacion = [c for c in Categoria.objects.all() if c.nombre.casefold() == 'capacitación']
        self.assertEqual(len(capacitacion), 1)

    def test_el_mismo_nombre_puede_existir_en_los_dos_tipos(self):
        # La unicidad es por nombre y tipo: una categoria propia no choca con las predeterminadas
        Categoria.objects.create(nombre='Seguros', tipo=TipoMovimiento.INGRESO)
        self.assertEqual(crear_predeterminadas(Categoria), 0)

    def test_la_funcion_de_la_migracion_trabaja_con_el_registro_de_apps(self):
        migracion = importlib.import_module('categorias.migrations.0002_categorias_predeterminadas')
        Categoria.objects.all().delete()
        migracion.crear_categorias(apps, None)
        self.assertEqual(Categoria.objects.count(), len(CATEGORIAS_PREDETERMINADAS))