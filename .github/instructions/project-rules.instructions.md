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
- Commit in small, progressive chunks (one logical change per commit); a PR may cover a whole phase, but its history must read as incremental steps.
- Configuration output must always include the full universe of supported configuration options.
- Adding a non-secret option means updating `OPTIONS` in `config.py`, `config.yaml`, the README options table, and `_format_config_lines` in `app.py` (tests enforce the first, second, and last).
- For UI-visible changes, run the dashboard with a temporary configuration that highlights the changed behavior and local fixture data via `DATA_FILE` where possible, then open the running app in a browser and inspect the result; do not overwrite `config.yaml` or use live credentials when fixtures suffice.
