# Proyecto ANF115 — Sistema de control de ingresos y gastos

Aplicación web para registrar los ingresos y gastos de una pequeña empresa, consultar sus movimientos y mostrar resultados financieros básicos por período (diario, mensual y anual).

Proyecto académico de la asignatura ANF115 (2026), desarrollado por un equipo de tres integrantes.

> **Estado:** base inicial del proyecto. Incluye las apps `core` y `seguridad` (login, usuarios, roles y contraseñas). Los módulos financieros están por implementar.

---

## 🎯 Objetivo

Centralizar los registros de ingresos y gastos para evitar errores, pérdida de información y consultas difíciles cuando los datos están dispersos. El sistema valida, guarda y calcula; **no** ejecuta cobros ni pagos reales.

## 🧩 Módulos

| Módulo | Responsabilidad | Estado |
|--------|-----------------|--------|
| M1 Usuarios | Crear, consultar, modificar y desactivar cuentas. | Base en app `seguridad` |
| M2 Ingresos | Registrar y consultar entradas; corregirlas con autorización. | Disponible |
| M3 Gastos | Registrar y consultar salidas; corregirlas con autorización. | Disponible |
| M4 Categorías | Clasificar los movimientos en categorías de ingreso o de gasto. | Disponible |
| M5 Panel financiero | Totales, resultado y comparación gráfica del período. | Pendiente |
| M6 Reportes | Reportes diarios, mensuales y anuales con filtros por fecha y categoría. | Pendiente |
| M7 Seguridad y bitácora | Control de acceso y registro de las acciones relevantes. | Acceso en `seguridad`; bitácora pendiente |

## 👥 Roles

- **Administrador:** gestiona usuarios y categorías, consulta toda la información, corrige movimientos y revisa la bitácora.
- **Empleado:** registra ingresos y gastos y consulta sus propios movimientos.

Los roles se manejan con los `Group` de Django (se muestran como "Roles" en la interfaz). El detalle de permisos del empleado aún está pendiente de validar con el equipo.

## 📐 Reglas principales

**Cálculos del período**

```
Ingresos totales     = suma de ingresos del período
Gastos totales       = suma de gastos del período
Resultado financiero = ingresos totales − gastos totales
Porcentaje de gastos = gastos totales ÷ ingresos totales × 100
```

- Si no hay ingresos, el porcentaje se muestra como **"N/D — Sin ingresos"** (nunca 0 % ni división por cero).
- Ejemplo: ingresos 1 000 y gastos 400 → resultado 600 y porcentaje 40 %.
- El porcentaje de varios meses se calcula con los totales del rango, sin promediar porcentajes mensuales.
- Los totales incluyen todos los registros del filtro, no solo la página visible de la lista.
- El resultado no equivale a utilidad contable ni al dinero disponible en caja o banco.

**Registros**

- Cada movimiento tiene concepto, monto, fecha, categoría y usuario creador.
- El monto debe ser mayor que cero y se guarda como decimal exacto (`DecimalField`, 2 decimales).
- La categoría debe ser del mismo tipo que el movimiento (ingreso o gasto) y estar activa.
- Las correcciones requieren motivo y conservan los valores anteriores en la bitácora; el autor y el tipo no cambian.
- Desactivar un usuario o una categoría no borra sus movimientos históricos.
- Reenviar el mismo formulario no debe duplicar un movimiento.

**Datos persistentes:** `Usuario`, `Categoria`, `MovimientoFinanciero` y `EventoBitacora`. Los reportes se calculan a partir de estos datos; no se guardan totales por separado.

## 🚫 Fuera del alcance

Conexiones bancarias, transferencias reales, facturación electrónica, contabilidad completa, inventarios, nómina, impuestos, préstamos, múltiples empresas y múltiples monedas.

Opcionales: exportación de reportes a PDF o Excel y anulación de movimientos con motivo.

## 🛠️ Tecnologías

| Componente | Elección |
|------------|----------|
| Lenguaje | Python 3.12 |
| Framework | Django 6 |
| Frontend | Templates de Django + JavaScript vanilla |
| UI/CSS | Bootstrap 5 + Bootstrap Icons vía CDN |
| Base de datos | SQLite (relacional) |
| Variables de entorno | `django-environ` + archivo `.env` |

## 📁 Estructura

```
proyecto-anf115/
├── core/               ← layout base, sidebar, home, ModeloBase, página 403
├── seguridad/          ← modelo Usuario, login/logout, usuarios, roles, contraseñas
├── proyecto_anf115/    ← configuración del proyecto (settings, urls, wsgi, asgi)
├── manage.py
├── requirements.txt
├── .env.example        ← ejemplo de variables de entorno
└── .gitignore
```

## 🚀 Instalación

```bash
git clone https://github.com/osmn10/Proyecto-ANF115.git
cd Proyecto-ANF115
```

```bash
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copia el archivo de variables de entorno y genera una `SECRET_KEY`:

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Pega la clave generada en `SECRET_KEY` dentro de `.env`. Luego:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000`.

> ⚠️ El archivo `.env` contiene datos sensibles y está excluido en `.gitignore`. **Nunca lo subas al repositorio.** Solo se versiona `.env.example`.

## 🤝 Forma de trabajo

- No trabajar directamente en `main`: crear una rama por funcionalidad y abrir un *pull request*.
- Mensajes de commit en español, modo imperativo: `tipo: descripción` (`feat`, `fix`, `docs`, `refactor`, `style`, `test`, `chore`).
- Código en español sin tildes (`Categoria`, `fecha_creacion`); interfaz en español con tildes.
- Todo modelo nuevo hereda de `core.models.ModeloBase`, excepto `Usuario`.
- Las vistas protegidas usan `@login_required` y `@permission_required`.
- Usar solo datos ficticios en pruebas y demostraciones.

## 📦 Entregables del proyecto

- Software funcional con base de datos relacional.
- Informe en Word de 30–40 páginas con formato APA 7.
- Manual de usuario y documentación técnica.
- Videoexposición de 20 minutos con los tres integrantes.
- Fecha de entrega: 10 de noviembre, 23:59.

