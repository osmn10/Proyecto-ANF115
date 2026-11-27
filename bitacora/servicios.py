from .models import EventoBitacora


def registrar_evento(*, usuario, accion, resumen, entidad, entidad_id='', detalles=None):
    """Agrega un evento de solo lectura; no guarda contraseñas ni credenciales."""
    return EventoBitacora.objects.create(
        usuario=usuario,
        accion=accion,
        resumen=resumen,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id else '',
        detalles=detalles or {},
    )
