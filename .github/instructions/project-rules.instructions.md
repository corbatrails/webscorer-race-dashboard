---
description: "Project-specific rules and conventions that must always be followed"
alwaysApply: true
---

# Project Rules

<!-- Add project rules below. Each rule should be a single bullet point. -->

- `.env.example` lists secrets only (`WEBSCORER_API_ID`, `WEBSCORER_API_TOKEN`); every non-secret option lives in `config.yaml`, which must list all supported options with their defaults (enforced by `tests/test_config.py`).
- All agentic development must occur in a git worktree so multiple agents can run concurrently without conflicts.
- Create Git worktrees as sibling directories outside the repository, named `<repo-name>-<worktree-name>` (for example, `C:\git\folder-name-work-tree-name`).
- Before creating a new worktree, check whether existing worktrees are associated with merged PRs and remove those worktree directories; preserve worktrees with unmerged or unverified PRs.
- Configuration output must always include the full universe of supported configuration options.
- Adding a non-secret option means updating `OPTIONS` in `config.py`, `config.yaml`, the README options table, and `_format_config_lines` in `app.py` (tests enforce the first, second, and last).
