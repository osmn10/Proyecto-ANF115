from django.urls import path

from . import views

app_name = 'categorias'

urlpatterns = [
    path('', views.lista_categorias, name='lista_categorias'),
    path('crear/', views.crear_categoria, name='crear_categoria'),
    path('<int:id>/editar/', views.editar_categoria, name='editar_categoria'),
    path('<int:id>/desactivar/', views.cambiar_estado_categoria, {'activar': False}, name='desactivar_categoria'),
    path('<int:id>/reactivar/', views.cambiar_estado_categoria, {'activar': True}, name='reactivar_categoria'),
]