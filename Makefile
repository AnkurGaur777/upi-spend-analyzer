# Makefile for UPI / Bank Statement Spend Analyzer

.PHONY: setup data run test evaluate render memo help

help:
	@echo "Available commands:"
	@echo "  make setup     Install dependencies from requirements.txt"
	@echo "  make data      Generate synthetic statements (HDFC and ICICI formats)"
	@echo "  make run       Execute pipeline on synthetic statement"
	@echo "  make test      Run pytest suite"
	@echo "  make evaluate  Run categorizer accuracy evaluation"
	@echo "  make render    Render dashboard preview PNGs and demo GIF"
	@echo "  make memo      Generate insights memo PDF"

setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

data:
	python scripts/generate_synthetic.py

run:
	python -m spend_analyzer.pipeline data/raw/synthetic/statement_synthetic.csv

test:
	pytest -q

evaluate:
	python scripts/evaluate_categorizer.py --final

render:
	python scripts/render_dashboard.py
	python scripts/build_demo_gif.py

memo:
	python scripts/compute_memo_numbers.py
	python scripts/build_insights_memo.py
