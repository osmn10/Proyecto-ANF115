"""
Pruebas automaticas del modulo de Categorias (M4).

Ejecutar:  python manage.py test categorias
Cubre: RF03, RN02 (unicidad por tipo), RN09 (tipo bloqueado en uso),
       RF12 (permisos) y los escenarios T06 / T08 del plan de pruebas.
"""
from unittest import mock

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from seguridad.models import Usuario

from .forms import CategoriaForm
from .models import Categoria, TipoMovimiento

CLAVE = 'Clave.Segura.123'


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
class CategoriaModeloTests(TestCase):

    def setUp(self):
        self.alquiler = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)

    def test_valores_por_defecto(self):
        self.assertTrue(self.alquiler.activo)
        self.assertEqual(str(self.alquiler), 'Alquiler')
        self.assertEqual(self.alquiler.get_tipo_display(), 'Gasto')

    def test_nombre_repetido_mismo_tipo_sin_importar_mayusculas(self):
        duplicada = Categoria(nombre='ALQUILER', tipo=TipoMovimiento.GASTO)
        with self.assertRaisesMessage(ValidationError, 'Ya existe una categoría con ese nombre'):
            duplicada.full_clean()

    def test_mismo_nombre_en_otro_tipo_es_valido(self):
        otra = Categoria(nombre='Alquiler', tipo=TipoMovimiento.INGRESO)
        otra.full_clean()  # no debe lanzar error
        otra.save()
        self.assertEqual(Categoria.objects.filter(nombre__iexact='alquiler').count(), 2)

    def test_la_base_de_datos_tambien_rechaza_duplicados(self):
        # Aunque se salte la validacion de Django, la restriccion UNIQUE lo impide
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(nombre='alquiler', tipo=TipoMovimiento.GASTO)

    def test_categoria_sin_movimientos_no_esta_en_uso(self):
        self.assertFalse(self.alquiler.esta_en_uso())

    def test_no_existe_permiso_de_eliminar(self):
        codenames = set(Permission.objects.filter(
            content_type__app_label='categorias').values_list('codename', flat=True))
        self.assertEqual(codenames, {'add_categoria', 'change_categoria', 'view_categoria'})


# ---------------------------------------------------------------------------
# Formulario
# ---------------------------------------------------------------------------
class CategoriaFormTests(TestCase):

    def test_quita_espacios_repetidos(self):
        form = CategoriaForm(data={'nombre': '  Servicios    basicos ', 'tipo': 'GASTO'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().nombre, 'Servicios basicos')

    def test_campos_obligatorios_y_tipo_invalido(self):
        form = CategoriaForm(data={'nombre': '', 'tipo': 'OTRO'})
        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('tipo', form.errors)

    def test_tipo_editable_si_no_esta_en_uso(self):
        categoria = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        form = CategoriaForm(instance=categoria)
        self.assertFalse(form.tipo_bloqueado)
        self.assertFalse(form.fields['tipo'].disabled)

    def test_tipo_bloqueado_si_esta_en_uso(self):
        # Se simula el uso: todavia no existen movimientos (llegan en la Fase 2)
        categoria = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        with mock.patch.object(Categoria, 'esta_en_uso', return_value=True):
            form = CategoriaForm(data={'nombre': 'Ventas al contado', 'tipo': 'GASTO'}, instance=categoria)
            self.assertTrue(form.tipo_bloqueado)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
        categoria.refresh_from_db()
        self.assertEqual(categoria.nombre, 'Ventas al contado')   # el nombre si cambia
        self.assertEqual(categoria.tipo, TipoMovimiento.INGRESO)   # el tipo se ignora


# ---------------------------------------------------------------------------
# Vistas y permisos
# ---------------------------------------------------------------------------
class CategoriaVistasTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Categoria.objects.all().delete()  # estas pruebas no dependen de las categorias predeterminadas
        # Rol con los tres permisos del modulo (como se configuraria en Roles)
        rol_admin = Group.objects.create(name='Administrador prueba')
        rol_admin.permissions.set(Permission.objects.filter(content_type__app_label='categorias'))
        cls.admin = Usuario.objects.create_user('admin_prueba', password=CLAVE)
        cls.admin.groups.add(rol_admin)
        # Usuario sin ningun permiso de categorias
        cls.empleado = Usuario.objects.create_user('empleado_prueba', password=CLAVE)

    def setUp(self):
        self.gasto = Categoria.objects.create(nombre='Alquiler', tipo=TipoMovimiento.GASTO)
        self.ingreso = Categoria.objects.create(nombre='Ventas', tipo=TipoMovimiento.INGRESO)
        self.inactiva = Categoria.objects.create(nombre='Transporte', tipo=TipoMovimiento.GASTO, activo=False)
        self.url_lista = reverse('categorias:lista_categorias')
        self.url_crear = reverse('categorias:crear_categoria')

    def entrar_como(self, usuario):
        self.client.force_login(usuario)

    # --- Acceso -----------------------------------------------------------
    def test_sin_sesion_redirige_al_login(self):
        respuesta = self.client.get(self.url_lista)
        self.assertRedirects(respuesta, f'/seguridad/login/?next={self.url_lista}')

    def test_empleado_sin_permisos_recibe_403(self):
        self.entrar_como(self.empleado)
        urls = [
            self.url_lista,
            self.url_crear,
            reverse('categorias:editar_categoria', args=[self.gasto.id]),
            reverse('categorias:desactivar_categoria', args=[self.gasto.id]),
            reverse('categorias:reactivar_categoria', args=[self.inactiva.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {'nombre': 'X', 'tipo': 'GASTO'}).status_code, 403)
        # Nada cambio aunque intento enviar datos directamente
        self.assertEqual(Categoria.objects.count(), 3)
        self.gasto.refresh_from_db()
        self.assertTrue(self.gasto.activo)

    def test_menu_finanzas_segun_permiso(self):
        self.entrar_como(self.empleado)
        self.assertNotContains(self.client.get(reverse('core:home')), 'Finanzas')
        self.entrar_como(self.admin)
        self.assertContains(self.client.get(reverse('core:home')), 'Finanzas')

    # --- Lista y filtros -------------------------------------------------
    def test_lista_muestra_todas(self):
        self.entrar_como(self.admin)
        respuesta = self.client.get(self.url_lista)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['categorias']), 3)

    def test_filtros_por_tipo_y_estado(self):
        self.entrar_como(self.admin)
        casos = {
            '?tipo=INGRESO': {'Ventas'},
            '?tipo=GASTO': {'Alquiler', 'Transporte'},
            '?estado=activas': {'Alquiler', 'Ventas'},
            '?estado=inactivas': {'Transporte'},
            '?tipo=GASTO&estado=activas': {'Alquiler'},
            '?tipo=VALOR_RARO': {'Alquiler', 'Ventas', 'Transporte'},  # filtro invalido se ignora
        }
        for consulta, esperado in casos.items():
            with self.subTest(consulta=consulta):
                respuesta = self.client.get(self.url_lista + consulta)
                nombres = {c.nombre for c in respuesta.context['categorias']}
                self.assertEqual(nombres, esperado)

    # --- Crear y editar ---------------------------------------------------
    def test_crear_categoria(self):
        self.entrar_como(self.admin)
        respuesta = self.client.post(self.url_crear, {'nombre': 'Publicidad', 'tipo': 'GASTO'})
        self.assertRedirects(respuesta, self.url_lista)
        self.assertTrue(Categoria.objects.filter(nombre='Publicidad', tipo='GASTO', activo=True).exists())

    def test_crear_duplicado_muestra_error_y_no_guarda(self):
        self.entrar_como(self.admin)
        respuesta = self.client.post(self.url_crear, {'nombre': 'ALQUILER', 'tipo': 'GASTO'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Ya existe una categoría con ese nombre para este tipo.')
        self.assertEqual(Categoria.objects.count(), 3)

    def test_editar_categoria(self):
        self.entrar_como(self.admin)
        url = reverse('categorias:editar_categoria', args=[self.gasto.id])
        respuesta = self.client.post(url, {'nombre': 'Alquiler de local', 'tipo': 'GASTO'})
        self.assertRedirects(respuesta, self.url_lista)
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.nombre, 'Alquiler de local')

    def test_editar_categoria_inexistente_da_404(self):
        self.entrar_como(self.admin)
        url = reverse('categorias:editar_categoria', args=[99999])
        self.assertEqual(self.client.get(url).status_code, 404)

    # --- Desactivar / reactivar (T06) -------------------------------------
    def test_get_de_desactivar_solo_confirma(self):
        self.entrar_como(self.admin)
        url = reverse('categorias:desactivar_categoria', args=[self.gasto.id])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'Sí, desactivar')
        self.gasto.refresh_from_db()
        self.assertTrue(self.gasto.activo)  # un GET nunca cambia datos

    def test_desactivar_conserva_el_registro_y_es_idempotente(self):
        self.entrar_como(self.admin)
        url = reverse('categorias:desactivar_categoria', args=[self.gasto.id])
        self.client.post(url)
        self.client.post(url)  # doble envio: debe seguir desactivada
        self.gasto.refresh_from_db()
        self.assertFalse(self.gasto.activo)
        self.assertTrue(Categoria.objects.filter(pk=self.gasto.pk).exists())  # no se elimino

    def test_reactivar(self):
        self.entrar_como(self.admin)
        url = reverse('categorias:reactivar_categoria', args=[self.inactiva.id])
        respuesta = self.client.post(url)
        self.assertRedirects(respuesta, self.url_lista)
        self.inactiva.refresh_from_db()
        self.assertTrue(self.inactiva.activo)