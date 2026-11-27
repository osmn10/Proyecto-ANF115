#!/usr/bin/env bash
# Script de construccion para Render. Se ejecuta en cada despliegue.
set -o errexit  # detener todo si un comando falla

pip install -r requirements.txt

# Reunir los archivos estaticos (CSS, JS) para que WhiteNoise los sirva
python manage.py collectstatic --no-input

# Crear o actualizar las tablas en la base de datos (tambien crea las categorias predeterminadas)
python manage.py migrate --no-input

# Crear el administrador inicial si todavia no existe (usa las variables ADMIN_*)
python manage.py crear_admin_inicial