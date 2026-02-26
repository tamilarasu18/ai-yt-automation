.PHONY: install install-dev install-all test lint format type-check run run-test clean docker-build docker-up docker-down help

PYTHON ?= python
PIP ?= pip

# ── Default ──────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────
install: ## Install production dependencies
	$(PIP) install -e .

install-dev: ## Install development dependencies
	$(PIP) install -e ".[dev]"

install-all: ## Install all dependencies (production + GPU + dev)
	$(PIP) install -e ".[all]"

# ── Quality ──────────────────────────────────────────────
test: ## Run unit tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ -v --cov=ai_shorts --cov-report=html --cov-report=term-missing

lint: ## Lint code with ruff
	$(PYTHON) -m ruff check src/ tests/

format: ## Auto-format code with ruff
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

type-check: ## Run mypy type checking
	$(PYTHON) -m mypy src/ai_shorts/

check: lint type-check test ## Run all quality checks

# ── Run ──────────────────────────────────────────────────
run: ## Run the full pipeline
	$(PYTHON) -m ai_shorts run

run-test: ## Run the simplified test pipeline
	$(PYTHON) -m ai_shorts run --mode test

# ── Docker ───────────────────────────────────────────────
docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start services (app + ollama)
	docker compose up -d

docker-down: ## Stop services
	docker compose down

# ── Cleanup ──────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
