#!/bin/sh

echo 'Esperando a que PostgreSQL esté disponible...'
while ! nc -z postgres 5432; do
  sleep 1
done
echo 'PostgreSQL está listo.'

echo 'Ejecutando migraciones...'
python manage.py migrate

echo 'Iniciando Gunicorn...'
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --access-logfile - \
    --error-logfile -
