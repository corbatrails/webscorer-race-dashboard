# Config Split (`config.yaml`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all non-secret options into a committed `config.yaml`, keep only secrets in `.env`, with documented/tested precedence and legacy `.env`-only back-compat.

**Architecture:** `config.py` gains an option registry (key, env name, default, parser, reload mode). `load_config()` resolves each option as default → `config.yaml` → environment (`.env` + process env). The returned dict is unchanged, so `app.py` and views are untouched.

**Tech Stack:** Python, PyYAML, python-dotenv, pytest

## Global Constraints

- Return dict keys/types from `load_config()` must not change.
- No changes to `data_processing.py` or view building.
- `start.sh` and `start.ps1` must stay behaviorally identical.
- Never commit secrets; `.env` stays gitignored.
- Spec: `docs/superpowers/specs/2026-10-17-config-yaml-design.md`

---

### Task 1: Registry + yaml loading with precedence

**Files:**
- Modify: `config.py`, `requirements.txt`
- Create: `config.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `OPTIONS` registry, `load_config(config_path=None)`

- [ ] **Step 1: Write failing tests** for: yaml values applied; yaml beats default; env beats yaml; blank env does not override; real env beats `.env` value; missing yaml uses defaults; committed `config.yaml` keys == registry keys and values == defaults.
- [ ] **Step 2: Run** `python -m pytest tests/test_config.py -q` and confirm the new tests fail.
- [ ] **Step 3: Implement** the registry, yaml loader, and layered resolution; add `PyYAML>=6.0` to `requirements.txt`; add `config.yaml` with every option and its default.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat:`).

### Task 2: Validation, warnings, and legacy back-compat

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests** for: unknown yaml keys warn; secrets in yaml ignored with warning; malformed yaml exits; invalid int/bool exits with message naming the option; legacy `.env` with non-secret keys applies values and warns; secrets-only `.env` does not warn.
- [ ] **Step 2: Run** and confirm failures.
- [ ] **Step 3: Implement** validation (`sys.exit(1)` with `ERROR:` message) and `.env` legacy detection via `dotenv_values`.
- [ ] **Step 4: Run** the full suite; all green.
- [ ] **Step 5: Commit** (`feat:`).

### Task 3: Startup printout guard, `.env.example`, start scripts

**Files:**
- Modify: `.env.example`, `start.sh`, `start.ps1`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write failing test** that `_format_config_lines` shows every registry option.
- [ ] **Step 2: Implement** `.env.example` as secrets only; update the `.env` error message identically in both start scripts.
- [ ] **Step 3: Run** the full suite; all green.
- [ ] **Step 4: Commit** (`feat:` / `test:`).

### Task 4: Docs and project rules

**Files:**
- Modify: `README.md`, `docs/ROADMAP.md` (status note only), `.github/instructions/project-rules.instructions.md`

- [ ] **Step 1:** Rewrite the README Configuration section: precedence, full option table, migration from legacy `.env`.
- [ ] **Step 2:** Replace the `.env`/`.env.example` parity rule with the secrets-only / `config.yaml` rule.
- [ ] **Step 3: Commit** (`docs:`).

### Task 5: Verification

- [ ] Run `python -m pytest` (all green).
- [ ] Load config from `config.yaml` + secrets-only `.env`; confirm values and printout.
- [ ] Load config from a legacy `.env`-only setup (no `config.yaml`, then with `config.yaml`); confirm values and the deprecation warning.
