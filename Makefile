.PHONY: help install test lint format docker-build docker-run docker-compose-up docker-compose-down setup-db migrate migrate-create migrate-rollback migrate-status k8s-deploy k8s-delete clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies (using pip/venv)
	pip install -r requirements.txt
	pip install -r requirements-dev.txt 2>/dev/null || true

install-conda: ## Install dependencies using conda
	conda env create -f environment.yml

install-conda-update: ## Update conda environment
	conda env update -f environment.yml --prune

test: ## Run tests
	pytest --cov=. --cov-report=html --cov-report=term

test-unit: ## Run unit tests only
	pytest -m unit --cov=. --cov-report=term

test-integration: ## Run integration tests only
	pytest -m integration --cov=. --cov-report=term

test-watch: ## Run tests in watch mode
	pytest-watch

lint: ## Run linter
	flake8 . --max-line-length=127 --extend-ignore=E203
	mypy . || true

format: ## Format code
	black .
	isort .

format-check: ## Check code formatting
	black --check .
	isort --check-only .

docker-build: ## Build Docker image
	docker build -t rag-llm-drive-connector:latest .

docker-run: ## Run Docker container
	docker run -d --name rag-app -p 8000:8000 -p 7860:7860 --env-file .env rag-llm-drive-connector:latest

docker-compose-up: ## Start services with docker-compose (includes PostgreSQL and MongoDB)
	docker-compose up -d

docker-compose-up-local: ## Start app and frontend, using local PostgreSQL and MongoDB
	@echo "Note: Make sure PostgreSQL and MongoDB are running on your local machine"
	@echo "The app container will connect to them via host.docker.internal"
	@if [ ! -f requirements.txt ]; then \
		echo "Error: requirements.txt not found in current directory"; \
		exit 1; \
	fi
	@if [ -f .env.development ]; then \
		echo "Loading environment from .env.development"; \
		export $$(grep -v '^#' .env.development | grep -v '^$$' | xargs) && \
		docker-compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.development build app frontend && \
		docker-compose -f docker-compose.yml -f docker-compose.local.yml --env-file .env.development up -d app frontend; \
	else \
		echo "Warning: .env.development not found, using default .env"; \
		docker-compose -f docker-compose.yml -f docker-compose.local.yml build app frontend && \
		docker-compose -f docker-compose.yml -f docker-compose.local.yml up -d app frontend; \
	fi

docker-compose-down: ## Stop docker-compose services
	docker-compose down

docker-compose-logs: ## View docker-compose logs
	docker-compose logs -f app

setup-db: ## Setup database
	python setup_db.py

migrate: ## Run database migrations (supports ENVIRONMENT variable)
	@if [ -n "$$ENVIRONMENT" ]; then \
		echo "Running migrations for environment: $$ENVIRONMENT"; \
		ENVIRONMENT=$$ENVIRONMENT alembic upgrade head; \
	else \
		echo "Running migrations (using default .env)"; \
		alembic upgrade head; \
	fi

migrate-create: ## Create a new migration (usage: make migrate-create MESSAGE="description")
	@if [ -n "$$ENVIRONMENT" ]; then \
		ENVIRONMENT=$$ENVIRONMENT alembic revision --autogenerate -m "$(MESSAGE)"; \
	else \
		alembic revision --autogenerate -m "$(MESSAGE)"; \
	fi

migrate-rollback: ## Rollback last migration
	@if [ -n "$$ENVIRONMENT" ]; then \
		ENVIRONMENT=$$ENVIRONMENT alembic downgrade -1; \
	else \
		alembic downgrade -1; \
	fi

migrate-status: ## Show migration status
	@if [ -n "$$ENVIRONMENT" ]; then \
		echo "Migration status for environment: $$ENVIRONMENT"; \
		ENVIRONMENT=$$ENVIRONMENT alembic current; \
		ENVIRONMENT=$$ENVIRONMENT alembic history; \
	else \
		alembic current; \
		alembic history; \
	fi

k8s-deploy: ## Deploy to Kubernetes
	kubectl apply -k k8s/

k8s-delete: ## Delete Kubernetes resources
	kubectl delete -k k8s/

k8s-logs: ## View Kubernetes logs
	kubectl logs -f deployment/rag-app -n rag-system

k8s-status: ## Check Kubernetes status
	kubectl get all -n rag-system

argocd-sync: ## Sync ArgoCD application
	argocd app sync rag-llm-drive-connector

clean: ## Clean up temporary files
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache

dev: install docker-compose-up setup-db ## Setup development environment

pre-commit: format lint test ## Run all pre-commit checks

