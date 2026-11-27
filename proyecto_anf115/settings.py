from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Leer variables de entorno desde .env
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

# Render define la variable RENDER=true en sus servicios
EN_RENDER = env.bool('RENDER', default=False)

# Seguridad
SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# En Render, el servicio recibe su direccion publica (xxx.onrender.com) en esta variable
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

if EN_RENDER:
    # Render termina el HTTPS en su proxy y reenvia la peticion por HTTP interno
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Apps del proyecto
    'core',
    'seguridad',
    'categorias',
    'movimientos',
    'ingresos',
    'gastos',
    'finanzas',
    'bitacora',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # sirve los archivos estaticos en produccion
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'seguridad.middleware.ForzarCambioPasswordMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proyecto_anf115.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'proyecto_anf115.wsgi.application'


# Base de datos: SQLite en local; en Render se define DATABASE_URL (PostgreSQL)
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
}
DATABASES['default']['CONN_MAX_AGE'] = 600


# Validacion de contrasenas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internacionalizacion
LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/El_Salvador'

USE_I18N = True

USE_TZ = True

# Formato numerico propio: miles con coma y decimales con punto (1,234.56)
FORMAT_MODULE_PATH = ['proyecto_anf115.formatos']


# Archivos estaticos
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # destino de "collectstatic" (ignorada en git)

if EN_RENDER:
    # Comprime y agrega un hash al nombre de cada archivo para que el navegador lo cachee bien.
    # Solo en Render: requiere haber ejecutado "collectstatic" (lo hace build.sh).
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }

    # Que los errores 500 (con su detalle) aparezcan en los logs de Render
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {'console': {'class': 'logging.StreamHandler'}},
        'root': {'handlers': ['console'], 'level': 'WARNING'},
    }


# Modelo de usuario personalizado
AUTH_USER_MODEL = 'seguridad.Usuario'

# Autenticacion
LOGIN_URL = '/seguridad/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/seguridad/login/'

# Mapeo de etiquetas de mensajes a clases de Bootstrap
from django.contrib.messages import constants as messages_const
MESSAGE_TAGS = {
    messages_const.DEBUG: 'secondary',
    messages_const.INFO: 'info',
    messages_const.SUCCESS: 'success',
    messages_const.WARNING: 'warning',
    messages_const.ERROR: 'danger',
}
