"""
Catalogo de categorias predeterminadas para una pequena empresa.

Se crean al ejecutar las migraciones (categorias/migrations/0002) y las usan los
comandos de datos de prueba. Son genericas a proposito: cada empresa puede
desactivar las que no use y crear las suyas desde el modulo de Categorias.
"""

INGRESO = 'INGRESO'
GASTO = 'GASTO'

CATEGORIAS_PREDETERMINADAS = [
    # Ingresos
    (INGRESO, 'Ventas de productos'),
    (INGRESO, 'Ventas de servicios'),
    (INGRESO, 'Cobro de cuentas por cobrar'),
    (INGRESO, 'Comisiones recibidas'),
    (INGRESO, 'Alquileres cobrados'),
    (INGRESO, 'Intereses ganados'),
    (INGRESO, 'Préstamos y aportes recibidos'),
    (INGRESO, 'Otros ingresos'),
    # Gastos
    (GASTO, 'Alquiler de local'),
    (GASTO, 'Servicios básicos'),
    (GASTO, 'Transporte y combustible'),
    (GASTO, 'Suministros y papelería'),
    (GASTO, 'Compra de mercadería o materia prima'),
    (GASTO, 'Salarios y prestaciones'),
    (GASTO, 'Impuestos y tasas'),
    (GASTO, 'Publicidad y marketing'),
    (GASTO, 'Mantenimiento y reparaciones'),
    (GASTO, 'Seguros'),
    (GASTO, 'Honorarios profesionales'),
    (GASTO, 'Comisiones y cargos bancarios'),
    (GASTO, 'Equipo y mobiliario'),
    (GASTO, 'Capacitación'),
    (GASTO, 'Pago de préstamos e intereses'),
    (GASTO, 'Otros gastos operativos'),
]


def crear_predeterminadas(modelo_categoria):
    """
    Crea las categorias que falten. Es idempotente: si ya existe una con el mismo
    nombre y tipo (aunque este desactivada o con otras mayusculas) no la toca.
    Devuelve cuantas creo.

    La comparacion se hace en Python y no en la base de datos porque SQLite solo
    ignora mayusculas en letras ASCII (no distinguiria "Capacitación" de "CAPACITACIÓN").
    """
    existentes = {(c.tipo, c.nombre.strip().casefold()) for c in modelo_categoria.objects.all()}
    creadas = 0
    for tipo, nombre in CATEGORIAS_PREDETERMINADAS:
        if (tipo, nombre.casefold()) not in existentes:
            modelo_categoria.objects.create(nombre=nombre, tipo=tipo)
            creadas += 1
    return creadas