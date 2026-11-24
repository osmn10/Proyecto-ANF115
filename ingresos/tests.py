"""
Pruebas de las vistas del modulo de Ingresos (M2).

Ejecutar:  python manage.py test ingresos
Cubre: RF04 (registro), RF06 (consulta segun alcance), RF08 (filtros),
       RF11 (total del conjunto filtrado), RF12 (permisos) y los escenarios
       T02, T04, T05 (parcial) y T08 del plan de pruebas.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from movimientos.models import MovimientoFinanciero
from seguridad.models import Usuario

from .models import Ingreso

CLAVE = 'Clave.Segura.123'
URL_LISTA = reverse('ingresos:lista_ingresos')
URL_REGISTRAR = reverse('ingresos:registrar_ingreso')


def url_detalle(ingreso):
    return reverse('ingresos:detalle_ingreso', args=[ingreso.pk])


class IngresosTestCase(TestCase):
    """Datos comunes: dos empleados, un administrador y categorías de ambos tipos."""

    @classmethod
    def setUpTestData(cls):
        rol_empleado = Group.objects.create(name='Empleado prueba')
        rol_empleado.permissions.set(Permission.objects.filter(
            content_type__app_label='ingresos', codename__in=['add_ingreso', 'view_ingreso']))
        rol_admin = Group.objects.create(name='Administrador prueba')
        rol_admin.permissions.set(Permission.objects.filter(
            content_type__app_label__in=['ingresos', 'categorias']))

        cls.ana = Usuario.objects.create_user('ana', password=CLAVE)
        cls.ana.groups.add(rol_empleado)
        cls.beto = Usuario.objects.create_user('beto', password=CLAVE)
        cls.beto.groups.add(rol_empleado)
        cls.admin = Usuario.objects.create_user('jefa', password=CLAVE)
        cls.admin.groups.add(rol_admin)
        cls.sin_permisos = Usuario.objects.create_user('visitante', password=CLAVE)

        cls.ventas = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        cls.servicios = Categoria.objects.create(nombre='Servicios', tipo=TipoMovimiento.INGRESO)
        cls.inactiva = Categoria.objects.create(nombre='Antigua', tipo=TipoMovimiento.INGRESO, activo=False)
        cls.alquiler = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)
        cls.hoy = timezone.localdate()

    def crear_ingreso(self, autor, monto='100.00', fecha=None, categoria=None, concepto='Venta'):
        return Ingreso.objects.create(
            concepto=concepto, monto=Decimal(monto), fecha=fecha or self.hoy,
            categoria=categoria or self.ventas, creado_por=autor,
        )

    def datos_validos(self, **cambios):
        datos = {
            'concepto': 'Venta de contado',
            'monto': '1500.50',
            'fecha': self.hoy.isoformat(),
            'categoria': self.ventas.pk,
        }
        datos.update(cambios)
        return datos

    def entrar_como(self, usuario):
        self.client.force_login(usuario)


# ---------------------------------------------------------------------------
# Permisos (RF12 / T08)
# ---------------------------------------------------------------------------
class PermisosIngresosTests(IngresosTestCase):

    def test_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get(URL_LISTA)
        self.assertRedirects(respuesta, f'/seguridad/login/?next={URL_LISTA}')

    def test_usuario_sin_permisos_recibe_403(self):
        ingreso = self.crear_ingreso(self.ana)
        self.entrar_como(self.sin_permisos)
        for url in (URL_LISTA, URL_REGISTRAR, url_detalle(ingreso)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        respuesta = self.client.post(URL_REGISTRAR, self.datos_validos())
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Ingreso.objects.count(), 1)

    def test_menu_muestra_ingresos_segun_permiso(self):
        self.entrar_como(self.sin_permisos)
        self.assertNotContains(self.client.get(reverse('core:home')), URL_LISTA)
        self.entrar_como(self.ana)
        self.assertContains(self.client.get(reverse('core:home')), URL_LISTA)


# ---------------------------------------------------------------------------
# Registro (RF04 / T02)
# ---------------------------------------------------------------------------
class RegistroIngresoTests(IngresosTestCase):

    def test_formulario_propone_la_fecha_de_hoy_y_solo_categorias_validas(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_REGISTRAR)
        self.assertContains(respuesta, f'value="{self.hoy.isoformat()}"')
        opciones = list(respuesta.context['form'].fields['categoria'].queryset)
        self.assertEqual(opciones, [self.servicios, self.ventas])  # sin inactiva ni de gasto

    def test_registro_valido(self):
        self.entrar_como(self.ana)
        respuesta = self.client.post(URL_REGISTRAR, self.datos_validos(concepto='  Venta   de contado '))
        ingreso = Ingreso.objects.get()
        self.assertRedirects(respuesta, url_detalle(ingreso))
        self.assertEqual(ingreso.concepto, 'Venta de contado')
        self.assertEqual(ingreso.monto, Decimal('1500.50'))
        self.assertEqual(ingreso.tipo, TipoMovimiento.INGRESO)
        self.assertEqual(ingreso.creado_por, self.ana)
        self.assertEqual(ingreso.version, 1)

    def test_detalle_muestra_confirmacion_y_monto_con_formato(self):
        self.entrar_como(self.ana)
        respuesta = self.client.post(URL_REGISTRAR, self.datos_validos(), follow=True)
        ingreso = Ingreso.objects.get()
        self.assertContains(respuesta, f'Ingreso #{ingreso.pk} registrado correctamente.')
        self.assertContains(respuesta, '$1,500.50')

    def test_no_se_puede_manipular_autor_tipo_ni_version(self):
        self.entrar_como(self.ana)
        self.client.post(URL_REGISTRAR, self.datos_validos(
            creado_por=self.admin.pk, tipo='GASTO', version=99))
        ingreso = MovimientoFinanciero.objects.get()
        self.assertEqual(ingreso.creado_por, self.ana)
        self.assertEqual(ingreso.tipo, TipoMovimiento.INGRESO)
        self.assertEqual(ingreso.version, 1)

    def test_datos_invalidos_no_se_guardan(self):
        manana = (self.hoy + timedelta(days=1)).isoformat()
        casos = {
            'monto cero': ({'monto': '0'}, 'monto'),
            'monto negativo': ({'monto': '-10'}, 'monto'),
            'tres decimales': ({'monto': '10.555'}, 'monto'),
            'fecha futura': ({'fecha': manana}, 'fecha'),
            'categoria de gasto': ({'categoria': self.alquiler.pk}, 'categoria'),
            'categoria inactiva': ({'categoria': self.inactiva.pk}, 'categoria'),
            'concepto vacio': ({'concepto': '   '}, 'concepto'),
        }
        self.entrar_como(self.ana)
        for nombre, (cambios, campo) in casos.items():
            with self.subTest(caso=nombre):
                respuesta = self.client.post(URL_REGISTRAR, self.datos_validos(**cambios))
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertEqual(Ingreso.objects.count(), 0)

    def test_sin_categorias_activas_muestra_aviso(self):
        Categoria.objects.filter(tipo=TipoMovimiento.INGRESO).update(activo=False)
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_REGISTRAR)
        self.assertContains(respuesta, 'No hay categorías de ingreso activas')
        self.assertContains(respuesta, 'Solicita a un administrador')

    def test_empleado_solo_con_ver_no_puede_registrar(self):
        solo_ver = Usuario.objects.create_user('lector', password=CLAVE)
        solo_ver.user_permissions.add(Permission.objects.get(codename='view_ingreso'))
        self.entrar_como(solo_ver)
        self.assertEqual(self.client.get(URL_REGISTRAR).status_code, 403)
        self.assertNotContains(self.client.get(URL_LISTA), 'Registrar ingreso')


# ---------------------------------------------------------------------------
# Consulta segun alcance (RF06 / RN13 / T08)
# ---------------------------------------------------------------------------
class AlcanceIngresosTests(IngresosTestCase):

    def setUp(self):
        self.de_ana = self.crear_ingreso(self.ana, concepto='Venta de Ana')
        self.de_beto = self.crear_ingreso(self.beto, concepto='Venta de Beto')

    def test_empleado_solo_ve_sus_ingresos(self):
        self.entrar_como(self.ana)
        respuesta = self.client.get(URL_LISTA)
        self.assertEqual(list(respuesta.context['pagina']), [self.de_ana])
        self.assertContains(respuesta, 'Mis ingresos')
        self.assertNotContains(respuesta, 'Registrado por')

    def test_empleado_no_abre_el_detalle_de_otro(self):
        self.entrar_como(self.ana)
        self.assertEqual(self.client.get(url_detalle(self.de_ana)).status_code, 200)
        self.assertEqual(self.client.get(url_detalle(self.de_beto)).status_code, 404)

    def test_administrador_ve_todos(self):
        self.entrar_como(self.admin)
        respuesta = self.client.get(URL_LISTA)
        self.assertEqual(set(respuesta.context['pagina']), {self.de_ana, self.de_beto})
        self.assertContains(respuesta, 'Registrado por')
        self.assertEqual(self.client.get(url_detalle(self.de_beto)).status_code, 200)

    def test_un_gasto_no_se_abre_desde_ingresos(self):
        gasto = MovimientoFinanciero.objects.create(
            tipo=TipoMovimiento.GASTO, concepto='Pago local', monto=Decimal('50'),
            fecha=self.hoy, categoria=self.alquiler, creado_por=self.admin,
        )
        self.entrar_como(self.admin)
        respuesta = self.client.get(reverse('ingresos:detalle_ingreso', args=[gasto.pk]))
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn(gasto.pk, [i.pk for i in self.client.get(URL_LISTA).context['pagina']])


# ---------------------------------------------------------------------------
# Filtros y total (RF08 / RF11 / T04 / T05)
# ---------------------------------------------------------------------------
class FiltrosIngresosTests(IngresosTestCase):

    def setUp(self):
        self.d1 = self.crear_ingreso(self.ana, '100.00', date(2026, 10, 1), self.ventas)
        self.d5 = self.crear_ingreso(self.ana, '200.00', date(2026, 10, 5), self.servicios)
        self.d10 = self.crear_ingreso(self.ana, '300.00', date(2026, 10, 10), self.ventas)
        self.d15 = self.crear_ingreso(self.ana, '400.00', date(2026, 10, 15), self.ventas)
        self.ajeno = self.crear_ingreso(self.beto, '999.00', date(2026, 10, 5), self.ventas)
        self.entrar_como(self.ana)

    def consultar(self, **filtros):
        return self.client.get(URL_LISTA, filtros)

    def test_rango_de_fechas_inclusivo(self):
        respuesta = self.consultar(desde='2026-10-05', hasta='2026-10-10')
        self.assertEqual(set(respuesta.context['pagina']), {self.d5, self.d10})
        self.assertEqual(respuesta.context['resumen']['total'], Decimal('500.00'))

    def test_filtro_por_categoria(self):
        respuesta = self.consultar(categoria=self.ventas.pk)
        self.assertEqual(set(respuesta.context['pagina']), {self.d1, self.d10, self.d15})

    def test_filtros_combinados_respetan_el_alcance(self):
        # El ingreso de Beto del 05/10 cumple los filtros, pero no es de Ana
        respuesta = self.consultar(desde='2026-10-05', hasta='2026-10-05')
        self.assertEqual(list(respuesta.context['pagina']), [self.d5])
        self.assertEqual(respuesta.context['resumen'], {'total': Decimal('200.00'), 'cantidad': 1})

    def test_rango_invertido_muestra_error_sin_cifras(self):
        respuesta = self.consultar(desde='2026-10-10', hasta='2026-10-01')
        self.assertContains(respuesta, 'no puede ser posterior')
        self.assertNotIn('resumen', respuesta.context)
        self.assertNotIn('pagina', respuesta.context)

    def test_categoria_de_otro_tipo_es_invalida(self):
        respuesta = self.consultar(categoria=self.alquiler.pk)
        self.assertIn('categoria', respuesta.context['filtros'].errors)
        self.assertNotIn('resumen', respuesta.context)

    def test_sin_coincidencias_total_cero(self):
        respuesta = self.consultar(desde='2027-01-01')
        self.assertContains(respuesta, 'No hay ingresos que coincidan')
        self.assertEqual(respuesta.context['resumen'], {'total': Decimal('0.00'), 'cantidad': 0})

    def test_categoria_inactiva_disponible_para_consultar_historicos(self):
        antiguo = self.crear_ingreso(self.ana, '50.00', date(2026, 9, 1), self.inactiva)
        respuesta = self.consultar(categoria=self.inactiva.pk)
        self.assertEqual(list(respuesta.context['pagina']), [antiguo])
        self.assertContains(respuesta, 'Antigua (inactiva)')


# ---------------------------------------------------------------------------
# Paginacion (el total no depende de la pagina visible)
# ---------------------------------------------------------------------------
class PaginacionIngresosTests(IngresosTestCase):

    def setUp(self):
        inicio = date(2026, 9, 1)
        for n in range(25):  # 25 x 10.10 = 252.50
            self.crear_ingreso(self.ana, '10.10', inicio + timedelta(days=n), concepto=f'Ingreso {n}')
        self.entrar_como(self.ana)

    def test_veinte_por_pagina_y_total_del_conjunto_completo(self):
        pagina_1 = self.client.get(URL_LISTA)
        pagina_2 = self.client.get(URL_LISTA, {'pagina': 2})
        self.assertEqual(len(pagina_1.context['pagina'].object_list), 20)
        self.assertEqual(len(pagina_2.context['pagina'].object_list), 5)
        for respuesta in (pagina_1, pagina_2):
            self.assertEqual(respuesta.context['resumen']['total'], Decimal('252.50'))
            self.assertEqual(respuesta.context['resumen']['cantidad'], 25)

    def test_ordenados_del_mas_reciente_al_mas_antiguo(self):
        fechas = [i.fecha for i in self.client.get(URL_LISTA).context['pagina']]
        self.assertEqual(fechas, sorted(fechas, reverse=True))

    def test_enlaces_de_pagina_conservan_los_filtros(self):
        respuesta = self.client.get(URL_LISTA, {'desde': '2026-09-01', 'categoria': self.ventas.pk})
        self.assertContains(respuesta, f'?desde=2026-09-01&amp;categoria={self.ventas.pk}&amp;pagina=2')

    def test_pagina_invalida_no_genera_error(self):
        self.assertEqual(self.client.get(URL_LISTA, {'pagina': 999}).context['pagina'].number, 2)
        self.assertEqual(self.client.get(URL_LISTA, {'pagina': 'abc'}).context['pagina'].number, 1)