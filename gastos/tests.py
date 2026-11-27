"""
Pruebas del modulo de Gastos (M3) y de la separacion entre ingresos y gastos.

Ejecutar:  python manage.py test gastos
Cubre: RF05 (registro), RF06 (consulta segun alcance), RF08 (filtros),
       RF11 (total), RF12 (permisos), RN02 (categoria del mismo tipo) y los
       escenarios T02, T04 y T08 del plan de pruebas. Las reglas comunes con
       ingresos (paginacion, decimales, fechas) ya se prueban en ingresos y movimientos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from categorias.forms import CategoriaForm
from categorias.models import Categoria, TipoMovimiento
from ingresos.models import Ingreso
from movimientos.models import MovimientoFinanciero
from seguridad.models import Usuario
from seguridad.views import _permisos_agrupados

from .models import Gasto

CLAVE = 'Clave.Segura.123'
URL_LISTA = reverse('gastos:lista_gastos')
URL_REGISTRAR = reverse('gastos:registrar_gasto')


def url_detalle(gasto):
    return reverse('gastos:detalle_gasto', args=[gasto.pk])


class GastosTestCase(TestCase):
    """Datos comunes: dos empleados, un administrador y categorías de ambos tipos."""

    @classmethod
    def setUpTestData(cls):
        Categoria.objects.all().delete()  # estas pruebas no dependen de las categorias predeterminadas
        rol_empleado = Group.objects.create(name='Empleado prueba')
        rol_empleado.permissions.set(Permission.objects.filter(
            codename__in=['add_ingreso', 'view_ingreso', 'add_gasto', 'view_gasto']))
        rol_admin = Group.objects.create(name='Administrador prueba')
        rol_admin.permissions.set(Permission.objects.filter(
            content_type__app_label__in=['ingresos', 'gastos', 'categorias']))

        cls.ana = Usuario.objects.create_user('ana', password=CLAVE)
        cls.ana.groups.add(rol_empleado)
        cls.beto = Usuario.objects.create_user('beto', password=CLAVE)
        cls.beto.groups.add(rol_empleado)
        cls.admin = Usuario.objects.create_user('jefa', password=CLAVE)
        cls.admin.groups.add(rol_admin)
        cls.sin_permisos = Usuario.objects.create_user('visitante', password=CLAVE)

        cls.alquiler = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)
        cls.energia = Categoria.objects.create(nombre='Energía', tipo=TipoMovimiento.GASTO)
        cls.inactiva = Categoria.objects.create(nombre='Antigua', tipo=TipoMovimiento.GASTO, activo=False)
        cls.ventas = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        cls.hoy = timezone.localdate()

    def crear_gasto(self, autor, monto='100.00', fecha=None, categoria=None, concepto='Pago'):
        return Gasto.objects.create(
            concepto=concepto, monto=Decimal(monto), fecha=fecha or self.hoy,
            categoria=categoria or self.alquiler, creado_por=autor,
        )

    def crear_ingreso(self, autor, monto='100.00', fecha=None, concepto='Venta'):
        return Ingreso.objects.create(
            concepto=concepto, monto=Decimal(monto), fecha=fecha or self.hoy,
            categoria=self.ventas, creado_por=autor,
        )

    def datos_validos(self, **cambios):
        datos = {
            'concepto': 'Pago de alquiler',
            'monto': '400.00',
            'fecha': self.hoy.isoformat(),
            'categoria': self.alquiler.pk,
        }
        datos.update(cambios)
        return datos

    def entrar_como(self, usuario):
        self.client.force_login(usuario)


# ---------------------------------------------------------------------------
# Permisos (RF12 / T08)
# ---------------------------------------------------------------------------
class PermisosGastosTests(GastosTestCase):

    def test_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get(URL_LISTA)
        self.assertRedirects(respuesta, f'/seguridad/login/?next={URL_LISTA}')

    def test_usuario_sin_permisos_recibe_403(self):
        gasto = self.crear_gasto(self.ana)
        self.entrar_como(self.sin_permisos)
        for url in (URL_LISTA, URL_REGISTRAR, url_detalle(gasto)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(URL_REGISTRAR, self.datos_validos()).status_code, 403)
        self.assertEqual(Gasto.objects.count(), 1)

    def test_permisos_propios_en_la_pantalla_de_roles(self):
        etiquetas = {item['label'] for item in dict(_permisos_agrupados())['gastos']}
        self.assertEqual(etiquetas, {
            'Agregar gasto', 'Modificar gasto', 'Ver gasto', 'Ver gastos de todos los usuarios',
        })

    def test_menu_muestra_gastos_segun_permiso(self):
        self.entrar_como(self.sin_permisos)
        self.assertNotContains(self.client.get(reverse('core:home')), URL_LISTA)
        self.entrar_como(self.ana)
        self.assertContains(self.client.get(reverse('core:home')), URL_LISTA)


# ---------------------------------------------------------------------------
# Registro (RF05 / T02)
# ---------------------------------------------------------------------------
class RegistroGastoTests(GastosTestCase):

    def test_solo_ofrece_categorias_activas_de_gasto(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_REGISTRAR)
        opciones = list(respuesta.context['form'].fields['categoria'].queryset)
        self.assertEqual(opciones, [self.alquiler, self.energia])
        self.assertContains(respuesta, 'Fecha del pago')

    def test_registro_valido(self):
        self.entrar_como(self.ana)
        respuesta = self.client.post(URL_REGISTRAR, self.datos_validos(), follow=True)
        gasto = Gasto.objects.get()
        self.assertRedirects(respuesta, url_detalle(gasto))
        self.assertContains(respuesta, f'Gasto #{gasto.pk} registrado correctamente.')
        self.assertContains(respuesta, '$400.00')
        self.assertEqual(gasto.tipo, TipoMovimiento.GASTO)
        self.assertEqual(gasto.creado_por, self.ana)

    def test_no_se_puede_manipular_autor_ni_tipo(self):
        self.entrar_como(self.ana)
        self.client.post(URL_REGISTRAR, self.datos_validos(creado_por=self.admin.pk, tipo='INGRESO'))
        gasto = MovimientoFinanciero.objects.get()
        self.assertEqual(gasto.tipo, TipoMovimiento.GASTO)
        self.assertEqual(gasto.creado_por, self.ana)

    def test_datos_invalidos_no_se_guardan(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        casos = {
            'monto cero': ({'monto': '0'}, 'monto'),
            'fecha futura': ({'fecha': manana}, 'fecha'),
            'categoria de ingreso': ({'categoria': self.ventas.pk}, 'categoria'),
            'categoria inactiva': ({'categoria': self.inactiva.pk}, 'categoria'),
        }
        self.entrar_como(self.ana)
        for nombre, (cambios, campo) in casos.items():
            with self.subTest(caso=nombre):
                respuesta = self.client.post(URL_REGISTRAR, self.datos_validos(**cambios))
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertEqual(Gasto.objects.count(), 0)

    def test_sin_categorias_de_gasto_muestra_aviso(self):
        Categoria.objects.filter(tipo=TipoMovimiento.GASTO).update(activo=False)
        self.entrar_como(self.admin)
        respuesta = self.client.get(URL_REGISTRAR)
        self.assertContains(respuesta, 'No hay categorías de gasto activas')
        self.assertContains(respuesta, 'Crear una categoría')  # el admin puede crearla


# ---------------------------------------------------------------------------
# Alcance y filtros (RF06 / RF08 / RF11 / T04 / T08)
# ---------------------------------------------------------------------------
class ConsultaGastosTests(GastosTestCase):

    def setUp(self):
        self.g1 = self.crear_gasto(self.ana, '400.00', date(2026, 10, 1), self.alquiler)
        self.g2 = self.crear_gasto(self.ana, '55.25', date(2026, 10, 5), self.energia)
        self.g3 = self.crear_gasto(self.ana, '60.75', date(2026, 10, 10), self.energia)
        self.de_beto = self.crear_gasto(self.beto, '999.00', date(2026, 10, 5), self.energia)

    def test_empleado_solo_ve_sus_gastos(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_LISTA)
        self.assertEqual(set(respuesta.context['pagina']), {self.g1, self.g2, self.g3})
        self.assertContains(respuesta, 'Mis gastos')
        self.assertEqual(self.client.get(url_detalle(self.de_beto)).status_code, 404)

    def test_administrador_ve_todos(self):
        self.entrar_como(self.admin)
        respuesta = self.client.get(URL_LISTA)
        self.assertEqual(respuesta.context['resumen']['cantidad'], 4)
        self.assertEqual(self.client.get(url_detalle(self.de_beto)).status_code, 200)

    def test_filtros_y_total(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_LISTA, {
            'desde': '2026-10-05', 'hasta': '2026-10-10', 'categoria': self.energia.pk})
        self.assertEqual(set(respuesta.context['pagina']), {self.g2, self.g3})
        self.assertEqual(respuesta.context['resumen'], {'total': Decimal('116.00'), 'cantidad': 2})

    def test_rango_invertido_muestra_error_sin_cifras(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_LISTA, {'desde': '2026-10-10', 'hasta': '2026-10-01'})
        self.assertContains(respuesta, 'no puede ser posterior')
        self.assertNotIn('resumen', respuesta.context)


# ---------------------------------------------------------------------------
# Separacion entre ingresos y gastos (una sola tabla, dos modulos)
# ---------------------------------------------------------------------------
class SeparacionIngresosGastosTests(GastosTestCase):

    def setUp(self):
        self.ingreso = self.crear_ingreso(self.ana, '1000.00', concepto='Venta de contado')
        self.gasto = self.crear_gasto(self.ana, '400.00', concepto='Pago de alquiler')
        self.entrar_como(self.admin)

    def test_ambos_viven_en_la_misma_tabla(self):
        self.assertEqual(MovimientoFinanciero.objects.count(), 2)
        self.assertEqual(list(Ingreso.objects.all()), [self.ingreso])
        self.assertEqual(list(Gasto.objects.all()), [self.gasto])

    def test_cada_lista_y_total_solo_incluye_su_tipo(self):
        ingresos = self.client.get(reverse('ingresos:lista_ingresos'))
        gastos = self.client.get(URL_LISTA)
        self.assertEqual([m.pk for m in ingresos.context['pagina']], [self.ingreso.pk])
        self.assertEqual([m.pk for m in gastos.context['pagina']], [self.gasto.pk])
        self.assertEqual(ingresos.context['resumen']['total'], Decimal('1000.00'))
        self.assertEqual(gastos.context['resumen']['total'], Decimal('400.00'))

    def test_un_id_del_otro_tipo_responde_404(self):
        url_gasto_como_ingreso = reverse('ingresos:detalle_ingreso', args=[self.gasto.pk])
        url_ingreso_como_gasto = reverse('gastos:detalle_gasto', args=[self.ingreso.pk])
        self.assertEqual(self.client.get(url_gasto_como_ingreso).status_code, 404)
        self.assertEqual(self.client.get(url_ingreso_como_gasto).status_code, 404)

    def test_filtro_no_acepta_categorias_del_otro_tipo(self):
        respuesta = self.client.get(URL_LISTA, {'categoria': self.ventas.pk})