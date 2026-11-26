from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('seguridad/', include('seguridad.urls')),
    path('categorias/', include('categorias.urls')),
    path('ingresos/', include('ingresos.urls')),
    path('gastos/', include('gastos.urls')),
    path('finanzas/', include('finanzas.urls')),
    path('bitacora/', include('bitacora.urls')),
]
