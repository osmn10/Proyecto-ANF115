"""
Pruebas de la eliminacion logica de usuarios.

Ejecutar:  python manage.py test seguridad
Cubre: RN08 (usuario desactivado sin acceso; relaciones historicas intactas),
       nombre de usuario reservado y protecciones de las pantallas.
"""
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from ingresos.models import Ingreso

from .forms import MENSAJE_NOMBRE_RESERVADO, UsuarioCrearForm, UsuarioEditarForm
from .models import Usuario

CLAVE = 'Clave.Segura.123'


class EliminacionLogicaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        rol_admin = Group.objects.create(name='Administrador prueba')
        rol_admin.permissions.set(Permission.objects.filter(
            content_type__app_label__in=['seguridad', 'auth']))
        cls.admin = Usuario.objects.create_user('admin_prueba', password=CLAVE)
        cls.admin.groups.add(rol_admin)
        cls.rol_empleado = Group.objects.create(name='Empleado prueba')

    def setUp(self):
        self.juan = Usuario.objects.create_user('juan', password=CLAVE)
        self.juan.groups.add(self.rol_empleado)
        ventas = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        self.ingreso = Ingreso.objects.create(
            concepto='Venta', monto=Decimal('50.00'), fecha=timezone.localdate(),
            categoria=ventas, creado_por=self.juan,
        )
        self.client.force_login(self.admin)
        self.url_eliminar = reverse('seguridad:eliminar_usuario', args=[self.juan.id])

    # --- Modelo -----------------------------------------------------------
    def test_eliminar_conserva_la_fila_y_sus_movimientos(self):
        self.juan.eliminar()
        self.juan.refresh_from_db()
        self.assertTrue(self.juan.eliminado)
        self.assertFalse(self.juan.is_active)
        self.assertIsNotNone(self.juan.fecha_eliminacion)
        self.assertFalse(self.juan.groups.exists())  # sin roles
        self.ingreso.refresh_from_db()
        self.assertEqual(self.ingreso.creado_por, self.juan)  # el historial sigue intacto

    # --- Vista de eliminar --------------------------------------------------
    def test_eliminar_desde_la_pantalla(self):
        respuesta = self.client.post(self.url_eliminar)
        self.assertRedirects(respuesta, reverse('seguridad:lista_usuarios'))
        self.assertTrue(Usuario.objects.get(pk=self.juan.pk).eliminado)

    def test_no_puede_eliminarse_a_si_mismo(self):
        url = reverse('seguridad:eliminar_usuario', args=[self.admin.id])
        self.client.post(url)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.eliminado)
        self.assertTrue(self.admin.is_active)

    def test_eliminado_no_puede_iniciar_sesion(self):
        self.juan.eliminar()
        self.client.logout()
        self.assertFalse(self.client.login(username='juan', password=CLAVE))

    def test_sesion_abierta_se_pierde_al_eliminar(self):
        otro = self.client_class()
        otro.force_login(self.juan)
        self.assertEqual(otro.get(reverse('core:home')).status_code, 200)
        self.juan.eliminar()
        respuesta = otro.get(reverse('core:home'))
        self.assertEqual(respuesta.status_code, 302)  # vuelve al login

    def test_eliminado_no_se_edita_resetea_ni_elimina_de_nuevo(self):
        self.juan.eliminar()
        urls = [
            reverse('seguridad:editar_usuario', args=[self.juan.id]),
            reverse('seguridad:resetear_password', args=[self.juan.id]),
            self.url_eliminar,
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        # Intento de reactivarlo enviando el formulario de edicion directamente
        self.client.post(urls[0], {'username': 'juan', 'is_active': 'on'})
        self.juan.refresh_from_db()
        self.assertFalse(self.juan.is_active)

    def test_eliminado_no_se_puede_agregar_a_un_rol(self):
        self.juan.eliminar()
        url = reverse('seguridad:usuarios_rol', args=[self.rol_empleado.id])
        respuesta = self.client.get(url)
        self.assertNotIn(self.juan, respuesta.context['usuarios_sin_rol'])
        self.client.post(url, {'accion': 'agregar', 'usuario_id': self.juan.id})
        self.assertFalse(self.juan.groups.exists())

    # --- Pantallas ---------------------------------------------------------
    def test_lista_y_detalle_muestran_la_marca(self):
        self.juan.eliminar()
        lista = self.client.get(reverse('seguridad:lista_usuarios'))
        self.assertContains(lista, 'Eliminado')
        self.assertEqual(list(lista.context['usuarios'])[-1], self.juan)  # al final
        detalle = self.client.get(reverse('seguridad:detalle_usuario', args=[self.juan.id]))
        self.assertContains(detalle, 'Esta cuenta fue eliminada')
        self.assertNotContains(detalle, reverse('seguridad:editar_usuario', args=[self.juan.id]))

    # --- Nombre reservado --------------------------------------------------
    def test_nombre_de_usuario_eliminado_queda_reservado(self):
        self.juan.eliminar()
        for nombre in ('juan', 'JUAN'):
            with self.subTest(nombre=nombre):
                form = UsuarioCrearForm(data={
                    'username': nombre, 'password1': CLAVE, 'password2': CLAVE, 'is_active': True,
                })
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors['username'], [MENSAJE_NOMBRE_RESERVADO])

    def test_no_se_puede_renombrar_a_un_nombre_reservado(self):
        self.juan.eliminar()
        pedro = Usuario.objects.create_user('pedro', password=CLAVE)
        form = UsuarioEditarForm(data={'username': 'Juan', 'is_active': True}, instance=pedro)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['username'], [MENSAJE_NOMBRE_RESERVADO])

    def test_editar_un_usuario_normal_sigue_funcionando(self):
        form = UsuarioEditarForm(data={'username': 'juan', 'first_name': 'Juan', 'is_active': True},
                                 instance=self.juan)
        self.assertTrue(form.is_valid(), form.errors)