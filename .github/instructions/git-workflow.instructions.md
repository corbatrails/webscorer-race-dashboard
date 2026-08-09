---
description: "Enforce feature branch workflow and conventional commit format"
alwaysApply: true
---

# Git Workflow Rules

## Feature Branches

All development work MUST happen on feature branches, never directly on `main`. Branch naming: `feat/`, `fix/`, `docs/`, `chore/`, `refactor/` prefix matching the commit type.

## Conventional Commits

All commit messages and PR titles MUST use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>: <short description>
```

Types: `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, `perf`

Breaking changes: append `!` after type (e.g., `feat!: remove legacy config`)

## Pull Requests

- Every merge to `main` goes through a PR
- PR title must be conventional commit format (used for release changelog)
