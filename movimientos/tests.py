"""
Pruebas del modelo MovimientoFinanciero y del proxy Ingreso.

Ejecutar:  python manage.py test movimientos
Cubre: RN01 (monto), RN02 (categoria compatible y activa), RN03 (fecha),
       RN07/T14 (exactitud decimal), integridad referencial (PROTECT) y
       el bloqueo del tipo de categoria en uso (RN09) con datos reales.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Sum
from django.test import TestCase
from django.utils import timezone

from categorias.forms import CategoriaForm
from categorias.models import Categoria, TipoMovimiento
from ingresos.models import Ingreso
from seguridad.models import Usuario
from seguridad.views import _permisos_agrupados

from .models import MovimientoFinanciero


class MovimientoBaseTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user('autor_prueba', password='Clave.Segura.123')
        cls.ventas = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        cls.alquiler = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)
        cls.hoy = timezone.localdate()

    def nuevo_ingreso(self, **cambios):
        datos = {
            'concepto': 'Venta de mostrador',
            'monto': Decimal('100.00'),
            'fecha': self.hoy,
            'categoria': self.ventas,
            'creado_por': self.usuario,
        }
        datos.update(cambios)
        return Ingreso(**datos)

    def errores(self, movimiento):
        try:
            movimiento.full_clean()
        except ValidationError as error:
            return error.message_dict
        return {}


class ProxyIngresoTests(MovimientoBaseTestCase):

    def test_el_proxy_asigna_el_tipo_automaticamente(self):
        ingreso = self.nuevo_ingreso()
        ingreso.save()
        self.assertEqual(ingreso.tipo, TipoMovimiento.INGRESO)
        self.assertEqual(ingreso.version, 1)
        self.assertTrue(ingreso.activo)

    def test_el_proxy_solo_ve_movimientos_de_su_tipo(self):
        self.nuevo_ingreso().save()
        gasto = MovimientoFinanciero.objects.create(
            tipo=TipoMovimiento.GASTO, concepto='Pago de local', monto=Decimal('400'),
            fecha=self.hoy, categoria=self.alquiler, creado_por=self.usuario,
        )
        self.assertEqual(MovimientoFinanciero.objects.count(), 2)  # la tabla tiene ambos
        self.assertEqual(Ingreso.objects.count(), 1)               # el proxy solo ve ingresos
        self.assertFalse(Ingreso.objects.filter(pk=gasto.pk).exists())

    def test_permisos_del_proxy(self):
        rol = dict(_permisos_agrupados())['ingresos']
        etiquetas = {item['label'] for item in rol}
        self.assertEqual(etiquetas, {
            'Agregar ingreso', 'Modificar ingreso', 'Ver ingreso',
            'Ver ingresos de todos los usuarios',
        })


class ValidacionesMovimientoTests(MovimientoBaseTestCase):

    def test_movimiento_valido(self):
        self.assertEqual(self.errores(self.nuevo_ingreso()), {})

    def test_monto_cero_o_negativo(self):
        for monto in (Decimal('0'), Decimal('-5')):
            with self.subTest(monto=monto):
                self.assertIn('monto', self.errores(self.nuevo_ingreso(monto=monto)))

    def test_monto_con_mas_de_dos_decimales(self):
        self.assertIn('monto', self.errores(self.nuevo_ingreso(monto=Decimal('10.555'))))

    def test_fecha_futura(self):
        manana = self.hoy + timedelta(days=1)
        self.assertIn('fecha', self.errores(self.nuevo_ingreso(fecha=manana)))

    def test_fecha_anterior_permitida(self):
        hace_un_anio = self.hoy - timedelta(days=365)
        self.assertEqual(self.errores(self.nuevo_ingreso(fecha=hace_un_anio)), {})

    def test_categoria_de_otro_tipo(self):
        errores = self.errores(self.nuevo_ingreso(categoria=self.alquiler))
        self.assertEqual(errores['categoria'], ['La categoría no corresponde a este tipo de movimiento.'])

    def test_categoria_inactiva_en_registro_nuevo(self):
        inactiva = Categoria.objects.create(nombre='Antigua', tipo=TipoMovimiento.INGRESO, activo=False)
        errores = self.errores(self.nuevo_ingreso(categoria=inactiva))
        self.assertEqual(errores['categoria'], ['Selecciona una categoría activa.'])

    def test_registro_existente_conserva_categoria_desactivada_despues(self):
        categoria = Categoria.objects.create(nombre='Temporal', tipo=TipoMovimiento.INGRESO)
        ingreso = self.nuevo_ingreso(categoria=categoria)
        ingreso.save()
        categoria.activo = False
        categoria.save()
        ingreso.concepto = 'Concepto corregido'
        self.assertEqual(self.errores(ingreso), {})


class IntegridadMovimientoTests(MovimientoBaseTestCase):

    def test_suma_exacta_de_decimales(self):
        # T14: 0.10 + 0.20 debe dar exactamente 0.30 (sin errores de coma flotante)
        self.nuevo_ingreso(monto=Decimal('0.10')).save()
        self.nuevo_ingreso(monto=Decimal('0.20')).save()
        total = Ingreso.objects.aggregate(total=Sum('monto'))['total']
        self.assertEqual(total, Decimal('0.30'))

    def test_la_base_de_datos_rechaza_monto_no_positivo(self):
        ingreso = self.nuevo_ingreso()
        ingreso.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ingreso.objects.filter(pk=ingreso.pk).update(monto=0)

    def test_no_se_puede_borrar_categoria_ni_usuario_con_movimientos(self):
        self.nuevo_ingreso().save()
        with self.assertRaises(ProtectedError):
            self.ventas.delete()
        with self.assertRaises(ProtectedError):
            self.usuario.delete()

    def test_categoria_en_uso_bloquea_el_tipo(self):
        # Completa la prueba simulada de categorias/tests.py, ahora con un movimiento real
        self.assertFalse(self.ventas.esta_en_uso())
        self.nuevo_ingreso().save()
        self.assertTrue(self.ventas.esta_en_uso())
        form = CategoriaForm(data={'nombre': 'Ventas', 'tipo': 'GASTO'}, instance=self.ventas)
        self.assertTrue(form.tipo_bloqueado)
        form.is_valid()
        form.save()
        self.ventas.refresh_from_db()
        self.assertEqual(self.ventas.tipo, TipoMovimiento.INGRESO)