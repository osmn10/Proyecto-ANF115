"""
Logica compartida de la correccion de movimientos (CU08), usada por ingresos y gastos.
"""
from django.db import transaction

from bitacora.models import EventoBitacora
from bitacora.servicios import registrar_evento
from .models import CorreccionMovimiento, MovimientoFinanciero


class ConflictoDeVersion(Exception):
    """Otra persona modifico el movimiento despues de abrir la correccion (RNF09)."""


def tomar_instantanea(movimiento):
    """Valores corregibles del movimiento, en un formato que se puede guardar como JSON."""
    return {
        'concepto': movimiento.concepto,
        'monto': f'{movimiento.monto:.2f}',
        'fecha': movimiento.fecha.isoformat(),
        'categoria': {'id': movimiento.categoria_id, 'nombre': movimiento.categoria.nombre},
    }


def aplicar_correccion(movimiento, *, antes, motivo, version_esperada, usuario):
    """
    Guarda un movimiento ya validado y registra la correccion en el historial.

    - `movimiento`: la instancia del formulario, con los valores nuevos.
    - `antes`: instantanea tomada ANTES de validar el formulario.
    - `version_esperada`: la version que la persona tenia en pantalla al abrir la correccion.

    Todo ocurre en una sola transaccion (RN11): o se guardan el cambio y su historial,
    o no se guarda nada. Si alguien cambio el registro mientras tanto, la version ya no
    coincide y se lanza ConflictoDeVersion sin tocar nada (RNF09).
    """
    despues = tomar_instantanea(movimiento)
    with transaction.atomic():
        # La version solo avanza si sigue siendo la que la persona vio.
        # Es un "compare-and-swap": la base de datos lo decide en una sola instruccion.
        actualizados = MovimientoFinanciero.objects.filter(
            pk=movimiento.pk, version=version_esperada,
        ).update(version=version_esperada + 1)
        if not actualizados:
            raise ConflictoDeVersion()

        movimiento.version = version_esperada + 1
        movimiento.save()
        correccion = CorreccionMovimiento.objects.create(
            movimiento=movimiento,
            version_anterior=version_esperada,
            version_nueva=movimiento.version,
            motivo=motivo,
            antes=antes,
            despues=despues,
            realizado_por=usuario,
        )
        registrar_evento(
            usuario=usuario,
            accion=EventoBitacora.Accion.MOVIMIENTO_CORREGIDO,
            resumen=f'{movimiento.get_tipo_display()} #{movimiento.pk} corregido',
            entidad='Movimiento financiero',
            entidad_id=movimiento.pk,
            detalles={
                'motivo': motivo,
                'antes': antes,
                'despues': despues,
                'version_anterior': version_esperada,
                'version_nueva': movimiento.version,
            },
        )
        return correccion
