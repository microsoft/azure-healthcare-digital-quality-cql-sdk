.PHONY: help sync lint type test test-spark build fabric-package clean fmt

help:
	@echo "Common targets:"
	@echo "  sync             uv sync --extra dev --extra test"
	@echo "  lint             ruff check ."
	@echo "  fmt              ruff format ."
	@echo "  type             mypy"
	@echo "  test             pytest -m 'not spark'"
	@echo "  test-spark       pytest -m spark"
	@echo "  build            python -m build"
	@echo "  fabric-package   build wheel + Fabric upload bundle in dist/fabric/"
	@echo "  clean            remove build / cache artifacts"

sync:
	uv sync --extra dev --extra test

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

type:
	uv run mypy

test:
	uv run pytest -m "not spark"

test-spark:
	uv run pytest -m spark

build:
	uv build

fabric-package:
	bash scripts/build-fabric-package.sh

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
