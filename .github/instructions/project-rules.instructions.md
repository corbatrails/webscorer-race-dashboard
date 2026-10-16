---
description: "Project-specific rules and conventions that must always be followed"
alwaysApply: true
---

# Project Rules

<!-- Add project rules below. Each rule should be a single bullet point. -->

- `.env.example` must always list the same properties as `.env` (and vice-versa). The example file should show default values; `.env` holds the active/custom values.
- All agentic development must occur in a git worktree so multiple agents can run concurrently without conflicts.
- Create Git worktrees as sibling directories outside the repository, named `<repo-name>-<worktree-name>` (for example, `C:\git\folder-name-work-tree-name`).
- Before creating a new worktree, check whether existing worktrees are associated with merged PRs and remove those worktree directories; preserve worktrees with unmerged or unverified PRs.
- Configuration output must always include the full universe of supported configuration options.
