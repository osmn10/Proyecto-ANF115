from django.urls import path

from . import views

app_name = 'bitacora'

urlpatterns = [
    path('', views.lista_eventos, name='lista_eventos'),
]
