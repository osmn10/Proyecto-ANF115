import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Crea el administrador inicial (superusuario) a partir de las variables de entorno '
        'ADMIN_USERNAME, ADMIN_PASSWORD y, opcionalmente, ADMIN_EMAIL. '
        'No hace nada si ya existe un superusuario o si faltan las variables. '
        'Sirve para servidores sin consola, como el plan gratuito de Render.'
    )

    def handle(self, *args, **opciones):
        Usuario = get_user_model()
        if Usuario.objects.filter(is_superuser=True).exists():
            self.stdout.write('Ya existe un superusuario: no se crea otro.')
            return

        nombre = os.environ.get('ADMIN_USERNAME', '').strip()
        clave = os.environ.get('ADMIN_PASSWORD', '')
        correo = os.environ.get('ADMIN_EMAIL', '').strip()
        if not nombre or not clave:
            self.stdout.write(self.style.WARNING(
                'No se creó ningún administrador: define ADMIN_USERNAME y ADMIN_PASSWORD '
                'o crea uno con "python manage.py createsuperuser".'))
            return

        try:
            validate_password(clave, Usuario(username=nombre, email=correo))
        except ValidationError as error:
            # Se falla a proposito: un administrador con clave debil en internet es un riesgo
            raise CommandError('ADMIN_PASSWORD no es segura: ' + ' '.join(error.messages))

        Usuario.objects.create_superuser(username=nombre, email=correo, password=clave)
        self.stdout.write(self.style.SUCCESS(f'Administrador "{nombre}" creado.'))