.PHONY: help install test lint format docker-build docker-run docker-compose-up docker-compose-down k8s-deploy k8s-delete clean

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

docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop docker-compose services
	docker-compose down

docker-compose-logs: ## View docker-compose logs
	docker-compose logs -f app

setup-db: ## Setup database
	python setup_db.py

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

