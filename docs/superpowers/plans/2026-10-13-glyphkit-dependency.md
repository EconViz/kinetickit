# GlyphKit Dependency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GlyphKit a required KineticKit dependency while preserving the neutral, lazy core boundary.

**Architecture:** Packaging guarantees GlyphKit is installed, but only `kinetickit.integrations.glyphkit` imports it. Existing neutral typography contracts remain unchanged and tests enforce both metadata and lazy imports.

**Tech Stack:** Python 3.10–3.13, Hatchling, uv, pytest, import-linter

**Spec:** `docs/superpowers/specs/2026-10-13-glyphkit-dependency-design.md`

## Global Constraints

- Dependency must be exactly compatible with `glyphkit>=1.0.0b2,<2`.
- Top-level/core KineticKit imports must not eagerly import GlyphKit.
- GlyphKit must remain independent of KineticKit.
- Existing raster and interactive extras remain unchanged.

## Review Focus

- Base distribution metadata contains GlyphKit exactly once with the required range.
- `import kinetickit` succeeds without importing `glyphkit` into `sys.modules`.
- The GlyphKit adapter remains importable and its full integration suite passes.
- The built wheel includes no accidental source-tree or workspace dependency metadata.
- Documentation no longer describes GlyphKit as optional or separately installed.

---

### Task 1: Required dependency and boundary tests

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_distribution.py`
- Modify: `tests/integrations/test_glyphkit.py`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: published `glyphkit>=1.0.0b2,<2`
- Produces: base KineticKit metadata with a required GlyphKit dependency

- [ ] **Step 1: Add failing metadata and lazy-import assertions**

Assert `importlib.metadata.requires("kinetickit")` contains the exact GlyphKit range, importing
the KineticKit core does not populate `sys.modules["glyphkit"]`, and the integration suite no
longer skips when GlyphKit is absent.

- [ ] **Step 2: Run focused tests and verify the metadata assertion fails**

Run: `uv run pytest tests/test_distribution.py tests/integrations/test_glyphkit.py -q`

- [ ] **Step 3: Add `glyphkit>=1.0.0b2,<2` to project dependencies and refresh `uv.lock`**

- [ ] **Step 4: Re-run the focused tests**

Expected: all selected tests pass.

### Task 2: Release and migration documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/migration.md`

**Interfaces:**
- Consumes: required dependency from Task 1
- Produces: installation and architecture guidance matching package metadata

- [ ] **Step 1: Replace optional/separate-install wording**

Document that GlyphKit is installed with KineticKit, remains behind the typography integration
boundary, and owns all font processing.

- [ ] **Step 2: Run documentation/source consistency searches**

Run: `rg -n "optional.*GlyphKit|separately installed|not a dependency" README.md CHANGELOG.md docs src tests`

- [ ] **Step 3: Run all quality gates**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy && uv run lint-imports`
