---
description: "Project-specific rules and conventions that must always be followed"
alwaysApply: true
---

# Project Rules

<!-- Add project rules below. Each rule should be a single bullet point. -->

- `.env.example` must always list the same properties as `.env` (and vice-versa). The example file should show default values; `.env` holds the active/custom values.
- All agentic development must occur in a git worktree so multiple agents can run concurrently without conflicts.

