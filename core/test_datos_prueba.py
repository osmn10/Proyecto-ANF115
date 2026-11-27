"""
Pruebas de los comandos `generar_datos_prueba` y `limpiar_datos_prueba`.

Ejecutar:  python manage.py test core.test_datos_prueba
Cubre: cantidad y calidad de los datos generados (mismas reglas que la aplicacion),
       reproducibilidad con semilla, uso de usuarios y categorias validos, correcciones
       de ejemplo, y que la limpieza borre solo lo que corresponde y pida confirmacion.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from categorias.predeterminadas import CATEGORIAS_PREDETERMINADAS
from core.datos_prueba import borrar_categorias_no_predeterminadas
from ingresos.models import Ingreso
from movimientos.models import CorreccionMovimiento, MovimientoFinanciero
from seguridad.models import Usuario

CLAVE = 'Clave.Segura.123'


def ejecutar(comando, *args, **opciones):
    salida = StringIO()
    call_command(comando, *args, stdout=salida, **opciones)
    return salida.getvalue()


class DatosPruebaTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user('ana', password=CLAVE)
        cls.beto = Usuario.objects.create_user('beto', password=CLAVE)
        cls.hoy = timezone.localdate()

    def crear_movimiento(self, **cambios):
        datos = {
            'concepto': 'Existente', 'monto': 10, 'fecha': self.hoy, 'creado_por': self.ana,
            'categoria': Categoria.objects.filter(tipo=TipoMovimiento.INGRESO).first(),
        }
        datos.update(cambios)
        return Ingreso.objects.create(**datos)

    def instantanea(self):
        return list(MovimientoFinanciero.objects.order_by('id').values_list(
            'concepto', 'monto', 'fecha', 'categoria__nombre', 'creado_por__username', 'tipo'))


@override_settings(DEBUG=True)
class GenerarDatosPruebaTests(DatosPruebaTestCase):

    def test_crea_la_cantidad_pedida_con_ambos_tipos(self):
        salida = ejecutar('generar_datos_prueba', cantidad=60, semilla=1)
        self.assertEqual(MovimientoFinanciero.objects.count(), 60)
        self.assertTrue(MovimientoFinanciero.objects.filter(tipo=TipoMovimiento.INGRESO).exists())
        self.assertTrue(MovimientoFinanciero.objects.filter(tipo=TipoMovimiento.GASTO).exists())
        self.assertIn('Creados 60 movimientos', salida)

    def test_los_datos_cumplen_las_reglas_de_la_aplicacion(self):
        ejecutar('generar_datos_prueba', cantidad=80, meses=3, semilla=2)
        desde = self.hoy - timedelta(days=90)
        for movimiento in MovimientoFinanciero.objects.select_related('categoria'):
            movimiento.full_clean()                                   # mismas validaciones que las pantallas
            self.assertGreater(movimiento.monto, 0)
            self.assertEqual(movimiento.monto, movimiento.monto.quantize(movimiento.monto))
            self.assertLessEqual(movimiento.fecha, self.hoy)          # nunca futura
            self.assertGreaterEqual(movimiento.fecha, desde)
            self.assertEqual(movimiento.categoria.tipo, movimiento.tipo)
            self.assertTrue(movimiento.categoria.activo)
            self.assertEqual(movimiento.version, 1)

    def test_los_montos_tienen_dos_decimales_como_maximo(self):
        ejecutar('generar_datos_prueba', cantidad=50, semilla=3)
        for monto in MovimientoFinanciero.objects.values_list('monto', flat=True):
            self.assertEqual(monto, round(monto, 2))

    def test_con_la_misma_semilla_salen_los_mismos_datos(self):
        ejecutar('generar_datos_prueba', cantidad=40, semilla=7)
        primera = self.instantanea()
        ejecutar('generar_datos_prueba', cantidad=40, semilla=7, limpiar=True)
        self.assertEqual(self.instantanea(), primera)

    def test_con_otra_semilla_salen_datos_distintos(self):
        ejecutar('generar_datos_prueba', cantidad=40, semilla=7)
        primera = self.instantanea()
        ejecutar('generar_datos_prueba', cantidad=40, semilla=8, limpiar=True)
        self.assertNotEqual(self.instantanea(), primera)

    def test_reparte_los_movimientos_entre_los_usuarios(self):
        ejecutar('generar_datos_prueba', cantidad=80, semilla=4)
        autores = set(MovimientoFinanciero.objects.values_list('creado_por__username', flat=True))
        self.assertEqual(autores, {'ana', 'beto'})

    def test_con_usuarios_usa_solo_esos(self):
        ejecutar('generar_datos_prueba', cantidad=30, semilla=5, usuarios=['beto'])
        self.assertEqual(set(MovimientoFinanciero.objects.values_list('creado_por__username', flat=True)), {'beto'})

    def test_ignora_usuarios_inactivos_y_eliminados(self):
        Usuario.objects.create_user('inactivo', password=CLAVE, is_active=False)
        eliminado = Usuario.objects.create_user('borrado', password=CLAVE)
        eliminado.eliminar()
        ejecutar('generar_datos_prueba', cantidad=60, semilla=6)
        autores = set(MovimientoFinanciero.objects.values_list('creado_por__username', flat=True))
        self.assertEqual(autores, {'ana', 'beto'})

    def test_no_usa_categorias_desactivadas(self):
        Categoria.objects.filter(nombre='Ventas de productos').update(activo=False)
        ejecutar('generar_datos_prueba', cantidad=100, semilla=8)
        self.assertFalse(MovimientoFinanciero.objects.filter(categoria__nombre='Ventas de productos').exists())

    def test_usa_una_categoria_creada_por_el_usuario(self):
        Categoria.objects.filter(tipo=TipoMovimiento.GASTO).update(activo=False)
        propia = Categoria.objects.create(nombre='Gasto propio', tipo=TipoMovimiento.GASTO)
        ejecutar('generar_datos_prueba', cantidad=40, semilla=9)
        gastos = MovimientoFinanciero.objects.filter(tipo=TipoMovimiento.GASTO)
        self.assertTrue(gastos.exists())
        self.assertEqual(set(gastos.values_list('categoria', flat=True)), {propia.pk})

    def test_recrea_las_categorias_predeterminadas_que_falten(self):
        Categoria.objects.all().delete()
        ejecutar('generar_datos_prueba', cantidad=20, semilla=1)
        self.assertEqual(Categoria.objects.count(), len(CATEGORIAS_PREDETERMINADAS))

    def test_sin_limpiar_agrega_a_lo_existente(self):
        self.crear_movimiento()
        ejecutar('generar_datos_prueba', cantidad=10, semilla=1)
        self.assertEqual(MovimientoFinanciero.objects.count(), 11)

    def test_limpiar_reemplaza_lo_existente(self):
        self.crear_movimiento(concepto='Viejo')
        ejecutar('generar_datos_prueba', cantidad=10, semilla=1, limpiar=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 10)
        self.assertFalse(MovimientoFinanciero.objects.filter(concepto='Viejo').exists())

    def test_correcciones_genera_historial_con_el_servicio_real(self):
        ejecutar('generar_datos_prueba', cantidad=30, semilla=11, correcciones=6)
        self.assertEqual(CorreccionMovimiento.objects.count(), 6)
        self.assertEqual(MovimientoFinanciero.objects.filter(version=2).count(), 6)
        for correccion in CorreccionMovimiento.objects.select_related('realizado_por'):
            self.assertIn(correccion.realizado_por.username, {'ana', 'beto'})
            self.assertTrue(correccion.motivo)
            self.assertNotEqual(correccion.antes['monto'], correccion.despues['monto'])
            self.assertEqual((correccion.version_anterior, correccion.version_nueva), (1, 2))

    def test_sin_correcciones_no_crea_historial(self):
        ejecutar('generar_datos_prueba', cantidad=20, semilla=1)
        self.assertEqual(CorreccionMovimiento.objects.count(), 0)

    def test_el_resumen_muestra_los_totales(self):
        salida = ejecutar('generar_datos_prueba', cantidad=20, semilla=1)
        for texto in ('Ingresos:', 'Gastos:', 'Resultado:', 'Semilla usada: 1'):
            self.assertIn(texto, salida)

    def test_sin_usuarios_falla_con_un_mensaje_claro(self):
        Usuario.objects.all().delete()
        with self.assertRaisesMessage(CommandError, 'createsuperuser'):
            ejecutar('generar_datos_prueba')
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_usuario_inexistente_falla(self):
        with self.assertRaisesMessage(CommandError, 'nadie'):
            ejecutar('generar_datos_prueba', usuarios=['ana', 'nadie'])
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_argumentos_invalidos_fallan(self):
        for opciones in ({'cantidad': 0}, {'meses': 0}, {'correcciones': -1}, {'cantidad': 5, 'correcciones': 6}):
            with self.subTest(opciones=opciones):
                with self.assertRaises(CommandError):
                    ejecutar('generar_datos_prueba', **opciones)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_con_debug_apagado_se_niega_salvo_que_se_fuerce(self):
        with self.assertRaisesMessage(CommandError, 'DEBUG'):
            ejecutar('generar_datos_prueba', cantidad=5)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)
        ejecutar('generar_datos_prueba', cantidad=5, forzar=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 5)


@override_settings(DEBUG=True)
class LimpiarDatosPruebaTests(DatosPruebaTestCase):

    def preparar(self):
        ejecutar('generar_datos_prueba', cantidad=20, semilla=1, correcciones=3)
        self.assertEqual(MovimientoFinanciero.objects.count(), 20)

    def test_borra_movimientos_y_correcciones_y_conserva_lo_demas(self):
        self.preparar()
        categorias = Categoria.objects.count()
        ejecutar('limpiar_datos_prueba', si=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)
        self.assertEqual(CorreccionMovimiento.objects.count(), 0)
        self.assertEqual(Categoria.objects.count(), categorias)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_sin_la_opcion_de_categorias_no_las_toca(self):
        Categoria.objects.create(nombre='Categoria de prueba', tipo=TipoMovimiento.GASTO)
        ejecutar('limpiar_datos_prueba', si=True)
        self.assertTrue(Categoria.objects.filter(nombre='Categoria de prueba').exists())

    def test_con_categorias_borra_solo_las_no_predeterminadas(self):
        Categoria.objects.create(nombre='Categoria de prueba', tipo=TipoMovimiento.GASTO)
        Categoria.objects.create(nombre='Seguros', tipo=TipoMovimiento.INGRESO)   # mismo nombre, otro tipo
        self.preparar()
        ejecutar('limpiar_datos_prueba', si=True, categorias=True)
        self.assertFalse(Categoria.objects.filter(nombre='Categoria de prueba').exists())
        self.assertFalse(Categoria.objects.filter(nombre='Seguros', tipo=TipoMovimiento.INGRESO).exists())
        self.assertEqual(Categoria.objects.count(), len(CATEGORIAS_PREDETERMINADAS))  # el catalogo base sigue completo

    def test_con_categorias_muestra_cuales_va_a_borrar_antes_de_preguntar(self):
        Categoria.objects.create(nombre='Categoria de prueba', tipo=TipoMovimiento.GASTO)
        with mock.patch('builtins.input', return_value='no'):
            salida = ejecutar('limpiar_datos_prueba', categorias=True)
        self.assertIn('Categoria de prueba (Gasto)', salida)
        self.assertNotIn('Seguros', salida)                       # las predeterminadas no se listan
        self.assertTrue(Categoria.objects.filter(nombre='Categoria de prueba').exists())

    def test_una_categoria_en_uso_no_se_borra(self):
        propia = Categoria.objects.create(nombre='Categoria en uso', tipo=TipoMovimiento.INGRESO)
        self.crear_movimiento(categoria=propia)
        borradas, conservadas = borrar_categorias_no_predeterminadas()
        self.assertEqual((borradas, conservadas), (0, 1))
        self.assertTrue(Categoria.objects.filter(pk=propia.pk).exists())

    def test_pide_confirmacion_y_cancela_si_no_se_escribe_si(self):
        self.preparar()
        for respuesta in ('no', '', 'tal vez'):
            with self.subTest(respuesta=respuesta):
                with mock.patch('builtins.input', return_value=respuesta):
                    salida = ejecutar('limpiar_datos_prueba')
                self.assertIn('Cancelado', salida)
                self.assertEqual(MovimientoFinanciero.objects.count(), 20)

    def test_borra_si_se_confirma(self):
        self.preparar()
        for respuesta in ('SI', ' si ', 'sí'):
            with self.subTest(respuesta=respuesta):
                if not MovimientoFinanciero.objects.exists():
                    self.preparar()
                with mock.patch('builtins.input', return_value=respuesta):
                    ejecutar('limpiar_datos_prueba')
                self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_con_si_no_pregunta_nada(self):
        self.preparar()
        with mock.patch('builtins.input', side_effect=AssertionError('no debia preguntar')):
            ejecutar('limpiar_datos_prueba', si=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_informa_lo_que_va_a_borrar(self):
        self.preparar()
        with mock.patch('builtins.input', return_value='no'):
            salida = ejecutar('limpiar_datos_prueba')
        self.assertIn('20 movimientos', salida)
        self.assertIn('3 correcciones', salida)

    def test_con_la_base_vacia_no_falla(self):
        salida = ejecutar('limpiar_datos_prueba', si=True)
        self.assertIn('Eliminados 0 movimientos y 0 correcciones', salida)

    def test_los_ids_vuelven_a_empezar_en_1(self):
        if connection.vendor != 'sqlite':
            self.skipTest('El reinicio de numeracion solo aplica a SQLite')
        self.crear_movimiento()
        self.crear_movimiento()
        ejecutar('limpiar_datos_prueba', si=True)
        self.assertEqual(self.crear_movimiento().pk, 1)

    @override_settings(DEBUG=False)
    def test_con_debug_apagado_se_niega_salvo_que_se_fuerce(self):
        self.crear_movimiento()
        with self.assertRaisesMessage(CommandError, 'DEBUG'):
            ejecutar('limpiar_datos_prueba', si=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 1)
        ejecutar('limpiar_datos_prueba', si=True, forzar=True)
        self.assertEqual(MovimientoFinanciero.objects.count(), 0)

    def test_generar_y_limpiar_dejan_la_base_como_al_inicio(self):
        ejecutar('generar_datos_prueba', cantidad=50, semilla=3, correcciones=5)
        ejecutar('limpiar_datos_prueba', si=True)
        self.assertEqual((MovimientoFinanciero.objects.count(), CorreccionMovimiento.objects.count()), (0, 0))