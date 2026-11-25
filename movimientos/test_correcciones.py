"""
Pruebas de la correccion de movimientos (CU08): modelo de historial, servicio y formularios.

Ejecutar:  python manage.py test movimientos.test_correcciones
Cubre: RF07 (correccion con motivo), RN01-RN03 (se validan de nuevo), RN10 (autor y tipo
       inmutables), RN11 (cambio e historial se guardan juntos) y RNF09 (control de
       cambios concurrentes), con los escenarios T09 y T10 del plan de pruebas.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from gastos.forms import GastoCorreccionForm
from gastos.models import Gasto
from ingresos.forms import IngresoCorreccionForm
from ingresos.models import Ingreso
from seguridad.models import Usuario

from .models import CorreccionMovimiento, MovimientoFinanciero
from .servicios import ConflictoDeVersion

CLAVE = 'Clave.Segura.123'


class CorreccionTestCase(TestCase):
    """Datos comunes: un empleado (autor), un administrador y categorias de ambos tipos."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = Usuario.objects.create_user('ana', password=CLAVE)
        cls.admin = Usuario.objects.create_user('jefa', password=CLAVE)
        cls.otro_admin = Usuario.objects.create_user('jefe', password=CLAVE)

        cls.ventas = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        cls.servicios = Categoria.objects.create(nombre='Servicios', tipo=TipoMovimiento.INGRESO)
        cls.antigua = Categoria.objects.create(nombre='Antigua', tipo=TipoMovimiento.INGRESO, activo=False)
        cls.alquiler = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)
        cls.transporte = Categoria.objects.create(nombre='Transporte', tipo=TipoMovimiento.GASTO)
        cls.hoy = timezone.localdate()

    def crear_ingreso(self, **cambios):
        datos = {
            'concepto': 'Venta de contado', 'monto': Decimal('100.00'),
            'fecha': self.hoy, 'categoria': self.ventas, 'creado_por': self.ana,
        }
        datos.update(cambios)
        return Ingreso.objects.create(**datos)

    def crear_gasto(self, **cambios):
        datos = {
            'concepto': 'Pago de local', 'monto': Decimal('300.00'),
            'fecha': self.hoy, 'categoria': self.alquiler, 'creado_por': self.ana,
        }
        datos.update(cambios)
        return Gasto.objects.create(**datos)

    def formulario(self, ingreso, version=None, clase=IngresoCorreccionForm, **cambios):
        """Formulario de correccion con los datos actuales del movimiento y los cambios dados."""
        datos = {
            'concepto': ingreso.concepto,
            'monto': str(ingreso.monto),
            'fecha': ingreso.fecha.isoformat(),
            'categoria': ingreso.categoria_id,
            'motivo': 'Error de captura',
            'version_esperada': ingreso.version if version is None else version,
        }
        datos.update(cambios)
        # Se recarga la instancia, como hace la vista: cada formulario trabaja con su propia copia
        modelo = clase._meta.model
        return clase(datos, instance=modelo.objects.get(pk=ingreso.pk))

    def corregir(self, ingreso, usuario=None, **cambios):
        form = self.formulario(ingreso, **cambios)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        return form.guardar_correccion(usuario or self.admin)


# ---------------------------------------------------------------------------
# Correccion valida y su historial (RF07 / RN10)
# ---------------------------------------------------------------------------
class CorreccionValidaTests(CorreccionTestCase):

    def test_corregir_actualiza_los_campos_y_sube_la_version(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, concepto='Venta al crédito', monto='250.75',
                      categoria=self.servicios.pk, fecha=(self.hoy - timedelta(days=2)).isoformat())

        ingreso.refresh_from_db()
        self.assertEqual(ingreso.concepto, 'Venta al crédito')
        self.assertEqual(ingreso.monto, Decimal('250.75'))
        self.assertEqual(ingreso.categoria, self.servicios)
        self.assertEqual(ingreso.fecha, self.hoy - timedelta(days=2))
        self.assertEqual(ingreso.version, 2)

    def test_el_historial_guarda_autor_motivo_versiones_y_valores(self):
        ingreso = self.crear_ingreso()
        correccion = self.corregir(ingreso, monto='120.00', motivo='El cliente pagó 120')

        correccion.refresh_from_db()
        self.assertEqual(correccion.movimiento_id, ingreso.pk)
        self.assertEqual(correccion.realizado_por, self.admin)
        self.assertEqual(correccion.motivo, 'El cliente pagó 120')
        self.assertEqual((correccion.version_anterior, correccion.version_nueva), (1, 2))
        self.assertEqual(correccion.antes['monto'], '100.00')
        self.assertEqual(correccion.despues['monto'], '120.00')
        self.assertEqual(correccion.antes['categoria'], {'id': self.ventas.pk, 'nombre': 'Ventas'})
        self.assertIsNotNone(correccion.fecha_creacion)

    def test_cambios_solo_lista_lo_que_realmente_cambio(self):
        ingreso = self.crear_ingreso(monto=Decimal('1000.00'))
        correccion = self.corregir(ingreso, monto='1234.50', categoria=self.servicios.pk)
        self.assertEqual(correccion.cambios(), [
            ('Monto', '$1,000.00', '$1,234.50'),
            ('Categoría', 'Ventas', 'Servicios'),
        ])

    def test_autor_y_tipo_no_cambian(self):
        ingreso = self.crear_ingreso()
        form = self.formulario(ingreso, creado_por=self.admin.pk, tipo=TipoMovimiento.GASTO, monto='90.00')
        self.assertTrue(form.is_valid())
        form.guardar_correccion(self.admin)

        movimiento = MovimientoFinanciero.objects.get(pk=ingreso.pk)
        self.assertEqual(movimiento.creado_por, self.ana)       # el autor original se conserva
        self.assertEqual(movimiento.tipo, TipoMovimiento.INGRESO)
        self.assertNotIn('creado_por', form.fields)
        self.assertNotIn('tipo', form.fields)

    def test_varias_correcciones_acumulan_historial(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, monto='110.00')
        self.corregir(ingreso, monto='120.00', version=2)

        ingreso.refresh_from_db()
        self.assertEqual(ingreso.version, 3)
        versiones = list(ingreso.correcciones.values_list('version_nueva', flat=True))
        self.assertEqual(versiones, [3, 2])  # la mas reciente primero
        self.assertEqual(ingreso.correcciones.first().antes['monto'], '110.00')

    def test_exactitud_decimal(self):
        ingreso = self.crear_ingreso()
        correccion = self.corregir(ingreso, monto='0.10')
        ingreso.refresh_from_db()
        self.assertEqual(ingreso.monto, Decimal('0.10'))
        self.assertEqual(correccion.despues['monto'], '0.10')

    def test_el_concepto_se_normaliza(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, concepto='  Venta   con    descuento ')
        ingreso.refresh_from_db()
        self.assertEqual(ingreso.concepto, 'Venta con descuento')

    def test_corregir_un_gasto(self):
        gasto = self.crear_gasto()
        correccion = self.corregir(gasto, clase=GastoCorreccionForm, monto='310.00',
                                   categoria=self.transporte.pk)
        gasto.refresh_from_db()
        self.assertEqual((gasto.monto, gasto.categoria, gasto.version),
                         (Decimal('310.00'), self.transporte, 2))
        self.assertEqual(correccion.cambios()[1], ('Categoría', 'Alquiler', 'Transporte'))


# ---------------------------------------------------------------------------
# Validaciones (RN01 / RN02 / RN03 se revisan de nuevo al corregir)
# ---------------------------------------------------------------------------
class ValidacionCorreccionTests(CorreccionTestCase):

    def assertRechazada(self, ingreso, campo=None, **cambios):
        form = self.formulario(ingreso, **cambios)
        self.assertFalse(form.is_valid())
        if campo:
            self.assertIn(campo, form.errors)
        # Rechazar no cambia nada: ni el registro ni el historial
        ingreso.refresh_from_db()
        self.assertEqual(ingreso.version, 1)
        self.assertEqual(CorreccionMovimiento.objects.count(), 0)
        return form

    def test_el_motivo_es_obligatorio(self):
        ingreso = self.crear_ingreso()
        for motivo in ('', '    '):
            with self.subTest(motivo=repr(motivo)):
                form = self.assertRechazada(ingreso, 'motivo', motivo=motivo, monto='150.00')
                self.assertEqual(form.errors['motivo'], ['Indica el motivo de la corrección.'])

    def test_el_motivo_no_pasa_de_250_caracteres(self):
        self.assertRechazada(self.crear_ingreso(), 'motivo', motivo='x' * 251, monto='150.00')

    def test_sin_cambios_no_se_guarda(self):
        ingreso = self.crear_ingreso()
        form = self.assertRechazada(ingreso)
        self.assertIn('No hay cambios que guardar', form.non_field_errors()[0])

    def test_cambiar_solo_espacios_cuenta_como_sin_cambios(self):
        ingreso = self.crear_ingreso(concepto='Venta de contado')
        form = self.assertRechazada(ingreso, concepto='  Venta   de contado ')
        self.assertIn('No hay cambios que guardar', form.non_field_errors()[0])

    def test_monto_cero_o_negativo_se_rechaza(self):
        ingreso = self.crear_ingreso()
        for monto in ('0', '0.00', '-5.00'):
            with self.subTest(monto=monto):
                self.assertRechazada(ingreso, 'monto', monto=monto)

    def test_monto_con_tres_decimales_se_rechaza(self):
        self.assertRechazada(self.crear_ingreso(), 'monto', monto='10.125')

    def test_fecha_futura_se_rechaza(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        self.assertRechazada(self.crear_ingreso(), 'fecha', fecha=manana)

    def test_categoria_de_otro_tipo_se_rechaza(self):
        self.assertRechazada(self.crear_ingreso(), 'categoria', categoria=self.alquiler.pk)

    def test_una_categoria_inactiva_no_se_puede_asignar(self):
        self.assertRechazada(self.crear_ingreso(), 'categoria', categoria=self.antigua.pk)

    def test_la_categoria_inactiva_actual_se_conserva(self):
        # Un registro historico con categoria desactivada se puede corregir sin cambiarla
        ingreso = self.crear_ingreso(categoria=self.antigua)
        form = self.formulario(ingreso, monto='55.00')
        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.guardar_correccion(self.admin)
        ingreso.refresh_from_db()
        self.assertEqual((ingreso.categoria, ingreso.monto), (self.antigua, Decimal('55.00')))

    def test_la_version_es_obligatoria(self):
        ingreso = self.crear_ingreso()
        self.assertRechazada(ingreso, 'version_esperada', version='', monto='150.00')

    def test_el_formulario_ofrece_la_categoria_actual_aunque_este_inactiva(self):
        ingreso = self.crear_ingreso(categoria=self.antigua)
        form = IngresoCorreccionForm(instance=ingreso)
        nombres = list(form.fields['categoria'].queryset.values_list('nombre', flat=True))
        self.assertIn('Antigua', nombres)
        self.assertNotIn('Alquiler', nombres)  # las de gasto nunca se ofrecen
        self.assertEqual(form.fields['version_esperada'].initial, 1)


# ---------------------------------------------------------------------------
# Cambios concurrentes (RNF09 / T09) y atomicidad (RN11 / T10)
# ---------------------------------------------------------------------------
class ConcurrenciaYAtomicidadTests(CorreccionTestCase):

    def test_la_segunda_correccion_con_la_misma_version_recibe_conflicto(self):
        # T09: dos administradores abren la version 1; el segundo confirma despues
        ingreso = self.crear_ingreso()
        form_primero = self.formulario(ingreso, monto='150.00', motivo='Primero')
        form_segundo = self.formulario(ingreso, monto='999.00', motivo='Segundo')
        self.assertTrue(form_primero.is_valid())
        self.assertTrue(form_segundo.is_valid())

        form_primero.guardar_correccion(self.admin)
        with self.assertRaises(ConflictoDeVersion):
            form_segundo.guardar_correccion(self.otro_admin)

        ingreso.refresh_from_db()
        self.assertEqual(ingreso.monto, Decimal('150.00'))   # no se sobrescribio en silencio
        self.assertEqual(ingreso.version, 2)
        self.assertEqual(ingreso.correcciones.count(), 1)
        self.assertEqual(ingreso.correcciones.get().motivo, 'Primero')

    def test_una_version_manipulada_o_vieja_recibe_conflicto(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, monto='110.00')  # ahora esta en version 2
        for version in (1, 5):
            with self.subTest(version=version):
                form = self.formulario(ingreso, version=version, monto='777.00')
                self.assertTrue(form.is_valid())
                with self.assertRaises(ConflictoDeVersion):
                    form.guardar_correccion(self.admin)
        ingreso.refresh_from_db()
        self.assertEqual((ingreso.monto, ingreso.version), (Decimal('110.00'), 2))

    def test_si_falla_el_historial_no_se_confirma_el_cambio(self):
        # T10: sin historial no hay cambio
        ingreso = self.crear_ingreso()
        form = self.formulario(ingreso, monto='500.00')
        self.assertTrue(form.is_valid())

        with mock.patch.object(CorreccionMovimiento, 'save', side_effect=RuntimeError('fallo')):
            with self.assertRaises(RuntimeError):
                form.guardar_correccion(self.admin)

        ingreso.refresh_from_db()
        self.assertEqual((ingreso.monto, ingreso.version), (Decimal('100.00'), 1))
        self.assertEqual(CorreccionMovimiento.objects.count(), 0)

    def test_el_historial_no_registra_secretos(self):
        ingreso = self.crear_ingreso()
        correccion = self.corregir(ingreso, monto='101.00')
        self.assertEqual(set(correccion.antes), {'concepto', 'monto', 'fecha', 'categoria'})
        self.assertEqual(set(correccion.despues), {'concepto', 'monto', 'fecha', 'categoria'})


# ---------------------------------------------------------------------------
# Integridad: el historial protege sus referencias
# ---------------------------------------------------------------------------
class IntegridadHistorialTests(CorreccionTestCase):

    def test_no_se_puede_borrar_un_movimiento_con_correcciones(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, monto='110.00')
        with self.assertRaises(ProtectedError):
            MovimientoFinanciero.objects.get(pk=ingreso.pk).delete()

    def test_no_se_puede_borrar_a_quien_corrigio(self):
        ingreso = self.crear_ingreso()
        self.corregir(ingreso, usuario=self.admin, monto='110.00')
        with self.assertRaises(ProtectedError):
            self.admin.delete()

    def test_la_correccion_no_cambia_la_fecha_de_creacion_del_movimiento(self):
        ingreso = self.crear_ingreso()
        creacion = ingreso.fecha_creacion
        self.corregir(ingreso, monto='110.00')
        ingreso.refresh_from_db()
        self.assertEqual(ingreso.fecha_creacion, creacion)
        self.assertGreaterEqual(ingreso.fecha_modificacion, creacion)