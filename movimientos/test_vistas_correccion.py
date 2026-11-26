"""
Pruebas de las vistas de correccion de Ingresos y Gastos (CU08).

Ejecutar:  python manage.py test movimientos.test_vistas_correccion
Las mismas pruebas se ejecutan para Ingresos y para Gastos (una clase por modulo),
asi se garantiza que ambos modulos se comportan igual.
Cubre: RF07 (correccion con motivo), RF12 (permisos), RN10 (autor y tipo inmutables),
       RN13 (alcance segun "ver todos"), RNF09 (cambios concurrentes) y los
       escenarios T09 y T10 del plan de pruebas a nivel de pantalla.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from gastos.models import Gasto
from ingresos.models import Ingreso
from seguridad.models import Usuario

from .models import CorreccionMovimiento, MovimientoFinanciero

CLAVE = 'Clave.Segura.123'


class VistasCorreccionMixin:
    """
    Pruebas comunes. Cada modulo define: app, singular, modelo, tipo, modelo_otro y etiqueta.
    No hereda de TestCase para que Django no la ejecute por si sola.
    """

    app = singular = modelo = tipo = modelo_otro = tipo_otro = etiqueta = None

    @classmethod
    def setUpTestData(cls):
        def rol(nombre, codigos):
            grupo = Group.objects.create(name=f'{nombre} {cls.app}')
            grupo.permissions.set(Permission.objects.filter(
                content_type__app_label=cls.app, codename__in=codigos))
            return grupo

        s = cls.singular
        rol_empleado = rol('Empleado', [f'add_{s}', f'view_{s}'])
        rol_admin = rol('Administrador', [f'add_{s}', f'view_{s}', f'change_{s}', f'ver_todos_{cls.app}'])
        rol_editor = rol('Editor propio', [f'view_{s}', f'change_{s}'])  # corrige, pero sin "ver todos"

        cls.empleado = Usuario.objects.create_user('ana', password=CLAVE)
        cls.empleado.groups.add(rol_empleado)
        cls.admin = Usuario.objects.create_user('jefa', password=CLAVE)
        cls.admin.groups.add(rol_admin)
        cls.otro_admin = Usuario.objects.create_user('jefe', password=CLAVE)
        cls.otro_admin.groups.add(rol_admin)
        cls.editor = Usuario.objects.create_user('editor', password=CLAVE)
        cls.editor.groups.add(rol_editor)
        cls.sin_permisos = Usuario.objects.create_user('visitante', password=CLAVE)

        cls.cat = Categoria.objects.create(nombre='Categoria A', tipo=cls.tipo)
        cls.cat2 = Categoria.objects.create(nombre='Categoria B', tipo=cls.tipo)
        cls.cat_inactiva = Categoria.objects.create(nombre='Categoria vieja', tipo=cls.tipo, activo=False)
        cls.cat_otro_tipo = Categoria.objects.create(nombre='Categoria del otro tipo', tipo=cls.tipo_otro)
        cls.hoy = timezone.localdate()

    # -- ayudas -------------------------------------------------------------
    def crear(self, autor, monto='100.00', concepto='Movimiento base', categoria=None):
        return self.modelo.objects.create(
            concepto=concepto, monto=Decimal(monto), fecha=self.hoy,
            categoria=categoria or self.cat, creado_por=autor,
        )

    def crear_otro_tipo(self, autor):
        categoria = Categoria.objects.get_or_create(
            nombre='Cat del otro tipo (movimiento)', tipo=self.tipo_otro)[0]
        return self.modelo_otro.objects.create(
            concepto='Del otro tipo', monto=Decimal('9.00'), fecha=self.hoy,
            categoria=categoria, creado_por=autor,
        )

    def url_corregir(self, movimiento):
        return reverse(f'{self.app}:corregir_{self.singular}', args=[movimiento.pk])

    def url_detalle(self, movimiento):
        return reverse(f'{self.app}:detalle_{self.singular}', args=[movimiento.pk])

    def url_lista(self):
        return reverse(f'{self.app}:lista_{self.app}')

    def datos(self, movimiento, **cambios):
        """Lo que enviaria el formulario: valores actuales + los cambios indicados."""
        datos = {
            'concepto': movimiento.concepto,
            'monto': str(movimiento.monto),
            'fecha': movimiento.fecha.isoformat(),
            'categoria': movimiento.categoria_id,
            'motivo': 'Error de captura',
            'version_esperada': movimiento.version,
        }
        datos.update(cambios)
        return datos

    def entrar(self, usuario, cliente=None):
        (cliente or self.client).force_login(usuario)

    def assertSinCambios(self, movimiento, monto='100.00', version=1):
        movimiento.refresh_from_db()
        self.assertEqual((movimiento.monto, movimiento.version), (Decimal(monto), version))
        self.assertEqual(CorreccionMovimiento.objects.filter(movimiento=movimiento).count(), version - 1)

    # -- acceso y alcance ---------------------------------------------------
    def test_sin_sesion_redirige_al_login(self):
        movimiento = self.crear(self.empleado)
        url = self.url_corregir(movimiento)
        for respuesta in (self.client.get(url), self.client.post(url, self.datos(movimiento, monto='1.00'))):
            self.assertRedirects(respuesta, f'{settings.LOGIN_URL}?next={url}', fetch_redirect_response=False)
        self.assertSinCambios(movimiento)

    def test_sin_permiso_de_correccion_recibe_403(self):
        movimiento = self.crear(self.empleado)
        for usuario in (self.empleado, self.sin_permisos):
            with self.subTest(usuario=usuario.username):
                self.entrar(usuario)
                self.assertEqual(self.client.get(self.url_corregir(movimiento)).status_code, 403)
                respuesta = self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='1.00'))
                self.assertEqual(respuesta.status_code, 403)
        self.assertSinCambios(movimiento)

    def test_con_permiso_muestra_el_formulario_con_los_valores_actuales(self):
        movimiento = self.crear(self.empleado, concepto='Concepto actual')
        self.entrar(self.admin)
        respuesta = self.client.get(self.url_corregir(movimiento))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Concepto actual')
        self.assertContains(respuesta, 'name="version_esperada"')
        self.assertContains(respuesta, 'Guardar corrección')
        form = respuesta.context['form']
        self.assertEqual(form.fields['version_esperada'].initial, 1)
        categorias = set(form.fields['categoria'].queryset.values_list('nombre', flat=True))
        self.assertIn('Categoria A', categorias)
        self.assertNotIn('Categoria del otro tipo', categorias)  # solo categorias del mismo tipo

    def test_un_id_inexistente_responde_404(self):
        self.entrar(self.admin)
        url = reverse(f'{self.app}:corregir_{self.singular}', args=[99999])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'motivo': 'x'}).status_code, 404)

    def test_sin_ver_todos_solo_se_corrige_lo_propio(self):
        propio = self.crear(self.editor, concepto='Propio')
        ajeno = self.crear(self.empleado, concepto='Ajeno')
        self.entrar(self.editor)
        self.assertEqual(self.client.get(self.url_corregir(propio)).status_code, 200)
        self.assertEqual(self.client.get(self.url_corregir(ajeno)).status_code, 404)
        respuesta = self.client.post(self.url_corregir(ajeno), self.datos(ajeno, monto='1.00'))
        self.assertEqual(respuesta.status_code, 404)
        self.assertSinCambios(ajeno)

    def test_con_ver_todos_se_corrigen_movimientos_de_otros(self):
        ajeno = self.crear(self.empleado)
        self.entrar(self.admin)
        respuesta = self.client.post(self.url_corregir(ajeno), self.datos(ajeno, monto='125.00'))
        self.assertRedirects(respuesta, self.url_detalle(ajeno))
        self.assertSinCambios(ajeno, monto='125.00', version=2)

    def test_un_movimiento_del_otro_tipo_responde_404(self):
        # Un ingreso no se corrige desde la pantalla de gastos (ni al reves)
        del_otro_tipo = self.crear_otro_tipo(self.empleado)
        self.entrar(self.admin)
        self.assertEqual(self.client.get(self.url_corregir(del_otro_tipo)).status_code, 404)
        datos = self.datos(del_otro_tipo, categoria=self.cat.pk, monto='1.00')
        self.assertEqual(self.client.post(self.url_corregir(del_otro_tipo), datos).status_code, 404)
        del_otro_tipo.refresh_from_db()
        self.assertEqual((del_otro_tipo.monto, del_otro_tipo.version), (Decimal('9.00'), 1))

    def test_el_formulario_exige_token_csrf(self):
        movimiento = self.crear(self.empleado)
        cliente = Client(enforce_csrf_checks=True)
        self.entrar(self.admin, cliente)
        respuesta = cliente.post(self.url_corregir(movimiento), self.datos(movimiento, monto='1.00'))
        self.assertEqual(respuesta.status_code, 403)
        self.assertSinCambios(movimiento)

    # -- correccion valida --------------------------------------------------
    def test_correccion_valida_guarda_redirige_y_registra_el_historial(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        datos = self.datos(movimiento, concepto='Concepto corregido', monto='250.50',
                           categoria=self.cat2.pk, motivo='El comprobante decía 250.50')
        respuesta = self.client.post(self.url_corregir(movimiento), datos, follow=True)

        self.assertRedirects(respuesta, self.url_detalle(movimiento))
        self.assertContains(respuesta, f'{self.etiqueta} #{movimiento.pk} corregido correctamente.')
        movimiento.refresh_from_db()
        self.assertEqual(movimiento.concepto, 'Concepto corregido')
        self.assertEqual(movimiento.monto, Decimal('250.50'))
        self.assertEqual(movimiento.categoria, self.cat2)
        self.assertEqual(movimiento.version, 2)

        correccion = CorreccionMovimiento.objects.get(movimiento=movimiento)
        self.assertEqual(correccion.realizado_por, self.admin)   # quien corrige sale de la sesion
        self.assertEqual(correccion.motivo, 'El comprobante decía 250.50')
        self.assertEqual((correccion.antes['monto'], correccion.despues['monto']), ('100.00', '250.50'))

    def test_autor_tipo_y_fecha_de_registro_no_cambian(self):
        movimiento = self.crear(self.empleado)
        creacion = movimiento.fecha_creacion
        self.entrar(self.admin)
        datos = self.datos(movimiento, monto='90.00', creado_por=self.admin.pk, tipo=self.tipo_otro)
        self.client.post(self.url_corregir(movimiento), datos)

        base = MovimientoFinanciero.objects.get(pk=movimiento.pk)
        self.assertEqual(base.monto, Decimal('90.00'))
        self.assertEqual(base.creado_por, self.empleado)
        self.assertEqual(base.tipo, self.tipo)
        self.assertEqual(base.fecha_creacion, creacion)

    def test_solo_cambia_el_movimiento_corregido(self):
        corregido = self.crear(self.empleado, concepto='Uno')
        intacto = self.crear(self.empleado, concepto='Dos')
        self.entrar(self.admin)
        self.client.post(self.url_corregir(corregido), self.datos(corregido, monto='77.00'))
        self.assertSinCambios(intacto)

    def test_la_correccion_actualiza_el_total_de_la_lista(self):
        movimiento = self.crear(self.empleado, monto='100.00')
        self.crear(self.empleado, monto='50.00')
        self.entrar(self.admin)
        self.assertEqual(self.client.get(self.url_lista()).context['resumen']['total'], Decimal('150.00'))

        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='300.00'))
        self.assertEqual(self.client.get(self.url_lista()).context['resumen']['total'], Decimal('350.00'))

    def test_cambiar_la_categoria_mueve_el_registro_en_el_filtro(self):
        movimiento = self.crear(self.empleado, concepto='Cambia de categoria', categoria=self.cat)
        self.entrar(self.admin)
        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, categoria=self.cat2.pk))

        en_a = self.client.get(self.url_lista(), {'categoria': self.cat.pk})
        en_b = self.client.get(self.url_lista(), {'categoria': self.cat2.pk})
        self.assertNotContains(en_a, 'Cambia de categoria')
        self.assertContains(en_b, 'Cambia de categoria')

    def test_se_puede_corregir_un_registro_de_un_usuario_eliminado(self):
        movimiento = self.crear(self.empleado)
        self.empleado.eliminar()
        self.entrar(self.admin)
        respuesta = self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='88.00'), follow=True)
        self.assertRedirects(respuesta, self.url_detalle(movimiento))
        self.assertContains(respuesta, 'Eliminado')  # el detalle sigue marcando al autor
        self.assertSinCambios(movimiento, monto='88.00', version=2)

    # -- errores de validacion ----------------------------------------------
    def test_sin_motivo_muestra_el_error_y_no_guarda(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        respuesta = self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='120.00', motivo='  '))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Indica el motivo de la corrección.')
        self.assertSinCambios(movimiento)

    def test_sin_cambios_muestra_el_aviso_y_no_guarda(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        respuesta = self.client.post(self.url_corregir(movimiento), self.datos(movimiento))
        self.assertContains(respuesta, 'No hay cambios que guardar')
        self.assertSinCambios(movimiento)

    def test_datos_invalidos_no_se_guardan(self):
        movimiento = self.crear(self.empleado)
        manana = (self.hoy + timedelta(days=1)).isoformat()
        casos = {
            'monto cero': {'monto': '0'},
            'monto negativo': {'monto': '-5.00'},
            'monto con 3 decimales': {'monto': '10.125'},
            'monto no numerico': {'monto': 'abc'},
            'fecha futura': {'fecha': manana},
            'fecha invalida': {'fecha': '31/02/2026'},
            'concepto vacio': {'concepto': '   '},
            'categoria del otro tipo': {'categoria': self.cat_otro_tipo.pk},
            'categoria inactiva': {'categoria': self.cat_inactiva.pk},
            'categoria inexistente': {'categoria': 99999},
        }
        self.entrar(self.admin)
        for nombre, cambios in casos.items():
            with self.subTest(caso=nombre):
                respuesta = self.client.post(self.url_corregir(movimiento), self.datos(movimiento, **cambios))
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, 'is-invalid')
                self.assertSinCambios(movimiento)

    def test_version_ausente_o_invalida_no_se_guarda(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        for version in ('', 'abc', '0', '-1'):
            with self.subTest(version=version):
                respuesta = self.client.post(
                    self.url_corregir(movimiento), self.datos(movimiento, monto='120.00', version_esperada=version))
                self.assertEqual(respuesta.status_code, 200)
                self.assertSinCambios(movimiento)

    def test_con_error_el_formulario_conserva_lo_escrito_y_la_version(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        respuesta = self.client.post(
            self.url_corregir(movimiento), self.datos(movimiento, concepto='Lo que escribi', motivo=''))
        self.assertContains(respuesta, 'Lo que escribi')
        self.assertContains(respuesta, 'name="version_esperada" value="1"')

    # -- cambios concurrentes (T09) -----------------------------------------
    def test_el_segundo_administrador_recibe_aviso_de_conflicto(self):
        movimiento = self.crear(self.empleado)
        primero, segundo = self.client, Client()
        self.entrar(self.admin, primero)
        self.entrar(self.otro_admin, segundo)
        # Los dos abren la pantalla con la version 1
        datos_primero = self.datos(movimiento, monto='150.00', motivo='Primero')
        datos_segundo = self.datos(movimiento, monto='999.00', motivo='Segundo')
        self.assertEqual(primero.get(self.url_corregir(movimiento)).status_code, 200)
        self.assertEqual(segundo.get(self.url_corregir(movimiento)).status_code, 200)

        primero.post(self.url_corregir(movimiento), datos_primero)
        respuesta = segundo.post(self.url_corregir(movimiento), datos_segundo, follow=True)

        # El segundo vuelve a la pantalla de correccion, con el aviso y los valores ya actualizados
        self.assertRedirects(respuesta, self.url_corregir(movimiento))
        self.assertContains(respuesta, 'El registro cambió. Recarga antes de guardar')
        self.assertEqual(respuesta.context['form'].fields['version_esperada'].initial, 2)
        self.assertContains(respuesta, '150.00')
        self.assertSinCambios(movimiento, monto='150.00', version=2)
        self.assertEqual(CorreccionMovimiento.objects.get(movimiento=movimiento).motivo, 'Primero')

        # Con la version nueva ya puede aplicar su correccion
        movimiento.refresh_from_db()
        respuesta = segundo.post(
            self.url_corregir(movimiento), self.datos(movimiento, monto='160.00', motivo='Segundo, ya actualizado'))
        self.assertRedirects(respuesta, self.url_detalle(movimiento))
        self.assertSinCambios(movimiento, monto='160.00', version=3)

    def test_reenviar_el_mismo_formulario_no_duplica_la_correccion(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        datos = self.datos(movimiento, monto='130.00')
        self.client.post(self.url_corregir(movimiento), datos)
        respuesta = self.client.post(self.url_corregir(movimiento), datos, follow=True)  # doble envio
        # El registro ya tiene esos valores: se avisa que no hay nada que guardar
        self.assertContains(respuesta, 'No hay cambios que guardar')
        self.assertSinCambios(movimiento, monto='130.00', version=2)

    # -- detalle, historial y botones ---------------------------------------
    def test_el_administrador_ve_el_historial_con_antes_y_despues(self):
        movimiento = self.crear(self.empleado, monto='100.00')
        self.entrar(self.admin)
        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='150.00', motivo='Primera'))
        movimiento.refresh_from_db()
        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='175.50', motivo='Segunda'))

        respuesta = self.client.get(self.url_detalle(movimiento))
        self.assertContains(respuesta, 'Historial de correcciones')
        for texto in ('Primera', 'Segunda', '$100.00', '$150.00', '$175.50', 'jefa'):
            self.assertContains(respuesta, texto)
        html = respuesta.content.decode()
        self.assertLess(html.index('Versión 2 → 3'), html.index('Versión 1 → 2'))  # la mas reciente primero

    def test_sin_correcciones_el_historial_lo_indica(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        respuesta = self.client.get(self.url_detalle(movimiento))
        self.assertContains(respuesta, 'no ha sido corregido')

    def test_el_historial_marca_al_usuario_eliminado(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.otro_admin)
        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='140.00'))
        self.otro_admin.eliminar()
        self.entrar(self.admin)
        self.assertContains(self.client.get(self.url_detalle(movimiento)), 'Usuario eliminado')

    def test_sin_permiso_no_se_ve_el_historial_ni_los_botones(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        self.client.post(self.url_corregir(movimiento), self.datos(movimiento, monto='150.00'))

        self.entrar(self.empleado)
        detalle = self.client.get(self.url_detalle(movimiento))
        self.assertNotContains(detalle, 'Historial de correcciones')
        self.assertNotContains(detalle, self.url_corregir(movimiento))
        self.assertContains(detalle, 'corregido el')  # la version si es visible para quien consulta
        self.assertNotContains(self.client.get(self.url_lista()), self.url_corregir(movimiento))

    def test_con_permiso_se_ven_el_boton_y_el_lapiz(self):
        movimiento = self.crear(self.empleado)
        self.entrar(self.admin)
        self.assertContains(self.client.get(self.url_detalle(movimiento)), self.url_corregir(movimiento))
        self.assertContains(self.client.get(self.url_lista()), self.url_corregir(movimiento))


class VistasCorreccionIngresosTests(VistasCorreccionMixin, TestCase):
    app, singular, etiqueta = 'ingresos', 'ingreso', 'Ingreso'
    modelo, tipo = Ingreso, TipoMovimiento.INGRESO
    modelo_otro, tipo_otro = Gasto, TipoMovimiento.GASTO


class VistasCorreccionGastosTests(VistasCorreccionMixin, TestCase):
    app, singular, etiqueta = 'gastos', 'gasto', 'Gasto'
    modelo, tipo = Gasto, TipoMovimiento.GASTO
    modelo_otro, tipo_otro = Ingreso, TipoMovimiento.INGRESO