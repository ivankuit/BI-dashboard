# BI-dashboard
A Django, PostgreSQL, Celery BI tool for banking data ingestion and summarisation

# To run this locally:
1. run `make setup` - this will set up the super user for you to log in with: username: admin, password: 12345. This will also set up initial data
2. run `docker compose exec django python manage.py simulate_integration`. This will run a single post transaction to generate some data for the application
3. run `docker compose exec django python manage.py simulate_integration --all`. This will run 10k transactions for data ingestion.
2. Access localhost:8000 and log in with the super user credentials, and view the account summary analytics dashboard if you wish to do so. 