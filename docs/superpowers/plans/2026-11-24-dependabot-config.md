# Dependabot Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weekly Dependabot updates for Python packages and GitHub Actions, and pin existing workflow actions to immutable commit SHAs.

**Architecture:** Add a Dependabot v2 config with separate `pip` and `github-actions` update entries. Group minor and patch updates within each ecosystem while leaving major updates ungrouped; replace all action tags in the existing workflows with their verified full commit SHAs and retain version comments.

**Tech Stack:** YAML, Dependabot, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-11-24-dependabot-config-design.md`

## Global Constraints

- Run weekly updates for `pip` and `github-actions`.
- Group `minor` and `patch` updates by ecosystem; major updates remain individual per dependency.
- Every workflow action reference uses its verified full commit SHA and retains the corresponding release tag as a comment.
- Preserve existing workflow behavior, triggers, and permissions.

## Review Focus

- A mismatched SHA or tag comment could pin an action to a different release than the existing workflow used; verify each SHA against its referenced release tag before editing.
- A malformed Dependabot group could prevent updates or accidentally group majors; validate parsed config and inspect both group `update-types` lists.
- A missed `uses:` reference would leave an action tag unpinned; verify every action reference in both workflow files matches a 40-character lowercase hexadecimal SHA.

---

### Task 1: Configure dependency updates and pin workflow actions

**Files:**
- Create: `.github/dependabot.yml`
- Modify: `.github/workflows/test.yml`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: Existing action references and Python dependency manifest at `requirements.txt`.
- Produces: Weekly grouped minor/patch updates for `pip` and GitHub Actions; individually proposed major updates; SHA-pinned workflow action references with version comments.

- [ ] **Step 1: Pin existing workflow actions**

  For each `uses:` entry in `.github/workflows/test.yml` and `.github/workflows/release.yml`, resolve the existing tag to its current full commit SHA, replace the tag reference with that 40-character SHA, and keep the original action ref as an adjacent comment. Confirm every resolved SHA belongs to the intended action and tag before applying it.

- [ ] **Step 2: Add `.github/dependabot.yml`**

  Set `version: 2` and add weekly update entries for `pip` and `github-actions`, each with `directory: "/"`. In each ecosystem, add a group matching `"*"` with `update-types: ["minor", "patch"]`. Do not group major updates.

- [ ] **Step 3: Validate configuration and action pins**

  Run: `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml', encoding='utf-8'))"`

  Expected: exits successfully with valid YAML.

  Check all `uses:` entries in both workflows: each reference must contain exactly 40 lowercase hexadecimal characters after `@`, and each must retain a release-tag comment. Verify the SHA/tag pairs against their upstream release refs.

- [ ] **Step 4: Check the final diff**

  Run: `git diff --check`

  Expected: no whitespace errors; only `.github/dependabot.yml` and the two workflow files contain implementation changes.
