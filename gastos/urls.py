from django.urls import path

from . import views

app_name = 'gastos'

urlpatterns = [
    path('', views.lista_gastos, name='lista_gastos'),
    path('registrar/', views.registrar_gasto, name='registrar_gasto'),
    path('<int:id>/', views.detalle_gasto, name='detalle_gasto'),
    path('<int:id>/corregir/', views.corregir_gasto, name='corregir_gasto'),
]