.PHONY: install dev-install download-data generate-data train evaluate serve test lint docker-up docker-down setup-db clean

install:
	pip install -e .

dev-install:
	pip install -e ".[dev,notebook]"

download-data:
	python scripts/download_data.py

generate-data:
	python scripts/generate_data.py

train:
	python scripts/train.py

evaluate:
	python scripts/evaluate.py

serve:
	python scripts/serve.py

test:
	pytest tests/ -v --cov=credit_scoring --cov-report=term-missing

lint:
	ruff check src/ tests/

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

setup-db:
	python scripts/setup_db.py

clean:
	rm -rf data/*.parquet data/*.csv models/*.joblib models/*.json models/tf_*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
