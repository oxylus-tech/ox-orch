
MODULE_DIR := ./ox
ASSETS_DIR := ./assets
APPS_STATIC := $(MODULE_DIR)/apps/*/static
POETRY := poetry
PNPM := pnpm


# Build TS/Vue assets into apps' static directories
.PHONY: assets
assets:
	@echo "Build assets..."
	cd $(ASSETS_DIR); \
		$(PNPM) install; \
		$(PNPM) build
	@echo "Assets build completed"


# Build python package
.PHONY: package
package: assets
	@echo "Build Python package..."
	$(POETRY) run ./manage.py collectassets
	$(POETRY) build
	@echo "Python package built."


# Build documentation
.PHONY: docs
docs:
	cd docs; make html

# Clean targets
.PHONY: clean
clean:
	@echo "Clean build files"
	@rm -rf $(APPS_STATIC)
	@rm dist *.egg-info
	@rm -rf docs/build
	@echo "Clean complete."
