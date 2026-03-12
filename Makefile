install:
	pip install -r requirements-dev.txt
	python manage.py tailwind install

dev:
	python manage.py migrate
	python manage.py tailwind start &
	python manage.py runserver

tailwind:
	python manage.py tailwind start

migrate:
	python manage.py migrate

migrations:
	python manage.py makemigrations

shell:
	python manage.py shell

superuser:
	python manage.py createsuperuser

collect:
	python manage.py collectstatic --noinput

deploy:
	bash deploy.sh

logs:
	docker compose logs -f django

down:
	docker compose down

.PHONY: install dev tailwind migrate migrations shell superuser collect deploy logs down
