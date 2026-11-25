from django.urls import path

from . import views

app_name = 'ingresos'

urlpatterns = [
    path('', views.lista_ingresos, name='lista_ingresos'),
    path('registrar/', views.registrar_ingreso, name='registrar_ingreso'),
    path('<int:id>/', views.detalle_ingreso, name='detalle_ingreso'),
    path('<int:id>/corregir/', views.corregir_ingreso, name='corregir_ingreso'),
]