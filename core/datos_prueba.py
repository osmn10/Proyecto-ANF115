"""
Utilidades para limpiar y generar datos de prueba. Solo para desarrollo.

Las usan los comandos `limpiar_datos_prueba` y `generar_datos_prueba`
(core/management/commands/).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from categorias.models import Categoria, TipoMovimiento
from categorias.predeterminadas import CATEGORIAS_PREDETERMINADAS
from gastos.forms import GastoCorreccionForm
from gastos.models import Gasto
from ingresos.forms import IngresoCorreccionForm
from ingresos.models import Ingreso
from movimientos.models import CorreccionMovimiento, MovimientoFinanciero

# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------


def _reiniciar_numeracion(modelos):
    """En SQLite, los ids vuelven a empezar en 1 al vaciar las tablas indicadas."""
    if connection.vendor != 'sqlite':
        return
    tablas = [(modelo._meta.db_table,) for modelo in modelos]
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
        if cursor.fetchone():
            cursor.executemany('DELETE FROM sqlite_sequence WHERE name = %s', tablas)


def borrar_movimientos():
    """
    Elimina TODOS los ingresos, gastos y el historial de correcciones.
    Conserva usuarios, roles y categorias. Devuelve (movimientos, correcciones) borrados.
    """
    movimientos = MovimientoFinanciero.objects.count()
    correcciones = CorreccionMovimiento.objects.count()
    with transaction.atomic():
        # Primero el historial: sus claves apuntan a los movimientos (PROTECT)
        CorreccionMovimiento.objects.all().delete()
        MovimientoFinanciero.objects.all().delete()
    _reiniciar_numeracion([CorreccionMovimiento, MovimientoFinanciero])
    return movimientos, correcciones


def _clave(tipo, nombre):
    return (tipo, nombre.strip().casefold())


def categorias_no_predeterminadas():
    """Categorias que no pertenecen al catalogo predeterminado (p. ej. las creadas en pruebas)."""
    predeterminadas = {_clave(tipo, nombre) for tipo, nombre in CATEGORIAS_PREDETERMINADAS}
    return [c for c in Categoria.objects.all() if _clave(c.tipo, c.nombre) not in predeterminadas]


def borrar_categorias_no_predeterminadas():
    """
    Elimina las categorias que no son predeterminadas y que ningun movimiento usa.
    Devuelve (borradas, conservadas_por_estar_en_uso).
    """
    borradas = conservadas = 0
    for categoria in categorias_no_predeterminadas():
        if categoria.esta_en_uso():
            conservadas += 1
        else:
            categoria.delete()
            borradas += 1
    return borradas, conservadas


# ---------------------------------------------------------------------------
# Generacion
# ---------------------------------------------------------------------------

# nombre de la categoria -> (monto minimo, monto maximo, frecuencia relativa, conceptos)
PERFILES = {
    # Ingresos
    'Ventas de productos': (15, 1200, 30, [
        'Venta de contado', 'Venta al por mayor', 'Venta en tienda', 'Venta en línea', 'Pedido de cliente frecuente']),
    'Ventas de servicios': (40, 900, 18, [
        'Servicio técnico', 'Servicio de instalación', 'Consultoría', 'Servicio a domicilio',
        'Contrato de mantenimiento mensual']),
    'Cobro de cuentas por cobrar': (100, 1500, 10, [
        'Abono de cliente', 'Pago de factura pendiente', 'Cancelación de saldo']),
    'Comisiones recibidas': (20, 300, 4, ['Comisión por venta de terceros', 'Comisión por referido']),
    'Alquileres cobrados': (150, 600, 2, ['Alquiler de bodega', 'Alquiler de espacio en local']),
    'Intereses ganados': (5, 80, 2, ['Intereses de cuenta de ahorro', 'Rendimiento de depósito']),
    'Préstamos y aportes recibidos': (500, 5000, 1, ['Aporte del propietario', 'Préstamo recibido']),
    'Otros ingresos': (10, 250, 3, ['Venta de material de desecho', 'Reintegro de proveedor']),
    # Gastos
    'Alquiler de local': (350, 900, 2, ['Pago de alquiler del local']),
    'Servicios básicos': (25, 220, 6, [
        'Recibo de energía eléctrica', 'Recibo de agua', 'Servicio de internet', 'Telefonía']),
    'Transporte y combustible': (10, 120, 8, ['Combustible', 'Transporte de mercadería', 'Pasajes y viáticos']),
    'Suministros y papelería': (8, 150, 8, ['Papelería', 'Artículos de limpieza', 'Materiales de oficina']),
    'Compra de mercadería o materia prima': (80, 1500, 16, [
        'Compra de mercadería', 'Compra de materia prima', 'Reposición de inventario']),
    'Salarios y prestaciones': (250, 1800, 4, ['Pago de planilla', 'Pago de prestaciones', 'Pago de horas extra']),
    'Impuestos y tasas': (30, 600, 3, ['Pago de impuestos', 'Tasa municipal', 'Matrícula de comercio']),
    'Publicidad y marketing': (20, 400, 4, ['Publicidad en redes sociales', 'Material impreso', 'Rotulación']),
    'Mantenimiento y reparaciones': (15, 500, 4, [
        'Reparación de equipo', 'Mantenimiento del local', 'Mantenimiento de vehículo']),
    'Seguros': (40, 300, 1, ['Prima de seguro del local', 'Seguro de vehículo']),
    'Honorarios profesionales': (60, 700, 2, ['Honorarios de contador', 'Asesoría legal']),
    'Comisiones y cargos bancarios': (2, 40, 3, ['Comisión bancaria', 'Cargo por transferencia']),
    'Equipo y mobiliario': (50, 1200, 2, ['Compra de equipo de cómputo', 'Compra de mobiliario']),
    'Capacitación': (30, 400, 1, ['Curso para el personal', 'Taller de ventas']),
    'Pago de préstamos e intereses': (100, 800, 2, ['Cuota de préstamo', 'Intereses de préstamo']),
    'Otros gastos operativos': (5, 200, 5, ['Gasto menor', 'Imprevistos de operación']),
}
PERFIL_GENERICO = (10, 300, 3, ['Movimiento registrado'])  # para categorias creadas por el usuario

MOTIVOS = [
    'Error de captura del monto',
    'El comprobante indicaba otro valor',
    'Se corrigió tras revisar el recibo',
    'Ajuste solicitado por contabilidad',
]


def usuarios_disponibles(nombres=None):
    """Usuarios activos y no eliminados, por orden de creacion. Con `nombres`, solo esos."""
    usuarios = get_user_model().objects.filter(is_active=True, fecha_eliminacion__isnull=True).order_by('pk')
    if nombres:
        usuarios = usuarios.filter(username__in=nombres)
    return list(usuarios)


def _perfil(categoria):
    return PERFILES.get(categoria.nombre, PERFIL_GENERICO)


def generar_movimientos(cantidad, meses, rng, usuarios, proporcion_ingresos=0.5):
    """
    Crea `cantidad` ingresos y gastos aleatorios (con las mismas validaciones que la
    aplicacion) en los ultimos `meses` meses. Devuelve la lista de movimientos creados.
    """
    hoy = timezone.localdate()
    desde = hoy - timedelta(days=meses * 30)
    dias = (hoy - desde).days
    categorias = list(Categoria.objects.filter(activo=True))
    por_tipo = {tipo: [c for c in categorias if c.tipo == tipo] for tipo in TipoMovimiento.values}
    tipos = [tipo for tipo in TipoMovimiento.values if por_tipo[tipo]]
    if not tipos:
        raise ValueError('No hay categorias activas para generar movimientos.')

    creados = []
    with transaction.atomic():
        for _ in range(cantidad):
            tipo = TipoMovimiento.INGRESO if rng.random() < proporcion_ingresos else TipoMovimiento.GASTO
            if tipo not in tipos:
                tipo = tipos[0]
            lista = por_tipo[tipo]
            categoria = rng.choices(lista, weights=[_perfil(c)[2] for c in lista])[0]
            minimo, maximo, _frecuencia, conceptos = _perfil(categoria)

            # Triangular: abundan los montos chicos y hay pocos grandes, como en un negocio real
            monto = Decimal(str(round(rng.triangular(minimo, maximo, minimo + (maximo - minimo) * 0.25), 2)))
            concepto = rng.choice(conceptos)
            if rng.random() < 0.35:
                concepto = f'{concepto} (ref. {rng.randint(1000, 9999)})'

            modelo = Ingreso if tipo == TipoMovimiento.INGRESO else Gasto
            creados.append(modelo.objects.create(
                concepto=concepto, monto=monto, categoria=categoria,
                fecha=desde + timedelta(days=rng.randint(0, dias)),
                creado_por=rng.choice(usuarios),
            ))
    return creados


def generar_correcciones(movimientos, cantidad, rng, usuarios):
    """Corrige `cantidad` movimientos con el mismo formulario y servicio que usa la aplicacion."""
    hechas = 0
    for movimiento in rng.sample(movimientos, min(cantidad, len(movimientos))):
        formulario = IngresoCorreccionForm if movimiento.tipo == TipoMovimiento.INGRESO else GastoCorreccionForm
        nuevo = (movimiento.monto * Decimal(str(round(rng.uniform(0.8, 1.2), 2)))).quantize(Decimal('0.01'))
        if nuevo == movimiento.monto or nuevo <= 0:
            nuevo = movimiento.monto + Decimal('1.00')
        actual = type(movimiento).objects.get(pk=movimiento.pk)
        form = formulario({
            'concepto': actual.concepto,
            'monto': str(nuevo),
            'fecha': actual.fecha.isoformat(),
            'categoria': actual.categoria_id,
            'motivo': rng.choice(MOTIVOS),
            'version_esperada': actual.version,
        }, instance=actual)
        if form.is_valid():
            form.guardar_correccion(rng.choice(usuarios))
            hechas += 1
    return hechas