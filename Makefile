.PHONY: requirements build migrate shell test up down restart logs clean help

# Compile requirements.txt from requirements.in using uv in Docker
requirements:
	@echo "Compiling requirements.txt from requirements.in..."
	docker run --rm -v $(CURDIR):/workspace -w /workspace \
		bi-dashboard-django \
		uv pip compile /workspace/requirements.in -o /workspace/requirements.txt
	@echo "✓ requirements.txt generated successfully"

# Build Django container without cache
build:
	docker compose build django

build-no-cache:
	docker compose build --no-cache django

migrate:
	docker compose exec django python manage.py migrate

makemigrations:
	docker compose exec django python manage.py makemigrations

setup:
	$(MAKE) migrate
	docker compose exec django python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); u, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com', 'is_staff': True, 'is_superuser': True}); u.set_password('12345'); u.save(); print(f'Admin user {\"created\" if created else \"updated\"}')"
	docker compose exec django python manage.py seed_categories
	docker compose exec django python manage.py generate_data




