from django.urls import path

from . import views

app_name = 'finanzas'

urlpatterns = [
    path('panel/', views.panel_financiero, name='panel_financiero'),
    path('reportes/', views.reportes, name='reportes'),
]
