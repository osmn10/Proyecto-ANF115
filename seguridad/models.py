from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Usuario(AbstractUser):
    """
    Modelo de usuario del sistema. Extiende AbstractUser de Django,
    que ya provee: username, password, email, first_name, last_name,
    is_active, date_joined, last_login, groups y permissions.

    No hereda ModeloBase porque AbstractUser ya cubre esos campos.
    """

    debe_cambiar_password = models.BooleanField(default=False)
    # Eliminacion logica: la fila nunca se borra para conservar la integridad
    # de ingresos, gastos y bitacora. Si tiene fecha, el usuario esta eliminado.
    fecha_eliminacion = models.DateTimeField('fecha de eliminación', null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    @property
    def eliminado(self):
        return self.fecha_eliminacion is not None

    def eliminar(self):
        """
        Eliminacion logica: bloquea el acceso, registra la fecha y quita sus roles.
        Conserva la fila, su nombre de usuario (queda reservado) y todo lo que registro.
        """
        self.is_active = False
        self.fecha_eliminacion = timezone.now()
        self.save(update_fields=['is_active', 'fecha_eliminacion'])
        self.groups.clear()