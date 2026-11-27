"""
Pruebas del comando `crear_admin_inicial` (administrador inicial en el despliegue).

Ejecutar:  python manage.py test core.test_admin_inicial
"""
import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from seguridad.models import Usuario

CLAVE_SEGURA = 'Clave.Muy.Segura.2026'


def ejecutar(**variables):
    """Ejecuta el comando con exactamente estas variables ADMIN_* en el entorno."""
    entorno = {k: v for k, v in os.environ.items() if not k.startswith('ADMIN_')}
    entorno.update(variables)
    salida = StringIO()
    with mock.patch.dict(os.environ, entorno, clear=True):
        call_command('crear_admin_inicial', stdout=salida)
    return salida.getvalue()


class CrearAdminInicialTests(TestCase):

    def test_crea_el_superusuario_con_la_clave_cifrada(self):
        salida = ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD=CLAVE_SEGURA, ADMIN_EMAIL='a@correo.com')
        admin = Usuario.objects.get(username='admin')
        self.assertTrue(admin.is_superuser and admin.is_staff and admin.is_active)
        self.assertEqual(admin.email, 'a@correo.com')
        self.assertTrue(admin.check_password(CLAVE_SEGURA))
        self.assertNotEqual(admin.password, CLAVE_SEGURA)       # se guarda cifrada
        self.assertIn('creado', salida)
        self.assertNotIn(CLAVE_SEGURA, salida)                  # nunca se imprime la clave

    def test_el_correo_es_opcional(self):
        ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD=CLAVE_SEGURA)
        self.assertEqual(Usuario.objects.get(username='admin').email, '')

    def test_es_idempotente_no_crea_otro_ni_cambia_la_clave(self):
        ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD=CLAVE_SEGURA)
        salida = ejecutar(ADMIN_USERNAME='otro', ADMIN_PASSWORD='Otra.Clave.Segura.99')
        self.assertIn('Ya existe un superusuario', salida)
        self.assertEqual(Usuario.objects.filter(is_superuser=True).count(), 1)
        self.assertFalse(Usuario.objects.filter(username='otro').exists())
        self.assertTrue(Usuario.objects.get(username='admin').check_password(CLAVE_SEGURA))

    def test_si_ya_hay_un_superusuario_no_hace_nada_aunque_no_haya_variables(self):
        Usuario.objects.create_superuser('existente', password=CLAVE_SEGURA)
        self.assertIn('Ya existe', ejecutar())

    def test_sin_variables_avisa_y_no_falla(self):
        for variables in ({}, {'ADMIN_USERNAME': 'admin'}, {'ADMIN_PASSWORD': CLAVE_SEGURA},
                          {'ADMIN_USERNAME': '  ', 'ADMIN_PASSWORD': CLAVE_SEGURA}):
            with self.subTest(variables=list(variables)):
                salida = ejecutar(**variables)
                self.assertIn('No se creó ningún administrador', salida)
                self.assertEqual(Usuario.objects.count(), 0)

    def test_una_clave_debil_hace_fallar_el_comando_y_no_crea_nada(self):
        for clave in ('12345678', 'password', 'corta', 'admin'):
            with self.subTest(clave=clave):
                with self.assertRaisesMessage(CommandError, 'ADMIN_PASSWORD no es segura'):
                    ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD=clave)
                self.assertEqual(Usuario.objects.count(), 0)

    def test_el_mensaje_de_error_no_revela_la_clave(self):
        with self.assertRaises(CommandError) as contexto:
            ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD='12345678')
        self.assertNotIn('12345678', str(contexto.exception))

    def test_el_administrador_creado_puede_iniciar_sesion(self):
        ejecutar(ADMIN_USERNAME='admin', ADMIN_PASSWORD=CLAVE_SEGURA)
        self.assertTrue(self.client.login(username='admin', password=CLAVE_SEGURA))