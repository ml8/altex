.PHONY: install install-node run serve demo demo-speech demo-alt demo-all \
       docker docker-run clean help

VENV   := .venv
PIP    := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python3
FLASK  := $(VENV)/bin/flask
PORT   := 5001

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────

install: $(VENV)/bin/activate ## Install Python dependencies
$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -q -r requirements.txt flask
	@echo "✓ Python deps installed"

install-node: package.json ## Install Node.js dependencies
	npm install --production
	@echo "✓ Node deps installed"

setup: install install-node ## Install all dependencies

# ── Run ────────────────────────────────────────────────────────────────

run: install ## Start Flask dev server (port $(PORT))
	FLASK_APP=web.app $(FLASK) run --host=0.0.0.0 --port=$(PORT)

serve: run ## Alias for run

# ── CLI shortcuts ──────────────────────────────────────────────────────

tag: install ## Tag a PDF: make tag TEX=source.tex PDF=input.pdf OUT=output.pdf
	$(PYTHON) -m altex $(TEX) $(PDF) -o $(OUT)

dump-tree: install ## Dump parse tree: make dump-tree TEX=source.tex
	$(PYTHON) -m altex $(TEX) --dump-tree

# ── Docker ─────────────────────────────────────────────────────────────

docker: ## Build Docker image
	docker build -t altex .

docker-run: docker ## Build and run Docker container
	docker run --rm -p 5000:5000 altex

# ── Demos ──────────────────────────────────────────────────────────────

demo: demo-all ## Run all demos

demo-all: install ## Batch-tag all test documents
	./demos/demo_tag_all.sh

demo-compare: install ## Before/after comparison: make demo-compare TEX=... PDF=...
	./demos/demo_compare.sh $(TEX) $(PDF)

demo-speech: install install-node ## Math-to-speech engine comparison
	./demos/demo_math_speech.sh

demo-alt: install install-node ## Embedded alternative HTML demo
	./demos/demo_alt_document.sh

demo-math: install ## Math formula alt-text showcase
	./demos/demo_math_alttext.sh

# ── Benchmarks ─────────────────────────────────────────────────────────

benchmark: install ## Run PDF/UA-1 benchmarks on existing tagged PDFs
	./scripts/benchmark.sh

benchmark-full: install ## Regenerate all tagged PDFs and benchmark
	./scripts/benchmark.sh --tag-first

# ── Clean ──────────────────────────────────────────────────────────────

clean: ## Remove demo output and temp files
	rm -rf demos/output/
	rm -rf /tmp/altex_*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"

distclean: clean ## Remove venv, node_modules, and all generated files
	rm -rf $(VENV) node_modules/
	@echo "✓ Distclean complete"
