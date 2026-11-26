from django.contrib import admin

from .models import EventoBitacora


@admin.register(EventoBitacora)
class EventoBitacoraAdmin(admin.ModelAdmin):
    list_display = ('fecha_creacion', 'usuario', 'accion', 'entidad', 'entidad_id')
    list_filter = ('accion', 'fecha_creacion')
    search_fields = ('resumen', 'entidad', 'entidad_id', 'usuario__username')
    readonly_fields = (
        'fecha_creacion', 'fecha_modificacion', 'activo', 'usuario', 'accion',
        'resumen', 'entidad', 'entidad_id', 'detalles',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
