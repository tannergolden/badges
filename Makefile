# SPDX-FileCopyrightText: 2026 Tanner Golden
# SPDX-License-Identifier: MIT
#
# The kit is stdlib-only Python, so every target below runs on a bare
# `python3` with nothing installed.

PYTHON ?= python3
KIT    := $(PYTHON) src/badge-kit.py
CODEMOD:= $(PYTHON) src/localize-badges.py
DATA   ?= .github/badges.yml
OUT    ?= assets/badges

.DEFAULT_GOAL := help
.PHONY: help badges render gallery localize check self-test icons palette test

## help: List the available targets
help:
	@echo "Emblems - the Badge Kit"
	@echo
	@grep -E '^## ' $(MAKEFILE_LIST) | sed -e 's/## /  /' -e 's/:/\t-/' | column -t -s $$'\t'

## badges: Localize any shields.io hotlinks, then render every badge
badges: localize render gallery

## render: Render .github/badges.yml into committed SVGs (and prune orphans)
render:
	@echo "Rendering self-hosted badges..."
	@$(KIT) --data $(DATA) --out $(OUT)

## gallery: Render every icon and color, and regenerate docs/Gallery.md
gallery:
	@echo "Rendering the gallery..."
	@$(KIT) --gallery --out $(OUT)

## localize: Rewrite shields.io hotlinks in Markdown into committed SVGs
localize:
	@echo "Localizing any shields.io doc badges..."
	@$(CODEMOD)

## check: CI gate - committed SVGs current, no shields.io hotlink remains
check: self-test
	@$(KIT) --data $(DATA) --out $(OUT) --check
	@$(KIT) --gallery --out $(OUT) --check
	@$(CODEMOD) --check

## self-test: Renderer and parser invariants (no repository needed)
self-test:
	@$(KIT) --self-test

## icons: List the icon registry
icons:
	@$(KIT) --icons

## palette: List the palette tokens
palette:
	@$(KIT) --palette

## test: Everything CI runs - the kit's gate plus the repository script tests
test: check
	@echo "Running the kit's tests..."
	@$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py'
	@echo "Running repository script tests..."
	@$(PYTHON) -m unittest discover -s .github/scripts -p 'test_*.py'
