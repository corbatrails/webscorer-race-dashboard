# Dependabot Configuration Design

## Intent

Automate dependency update proposals and ensure GitHub Actions workflows use immutable action references.

## Goals and non-goals

- Check Python (`pip`) and GitHub Actions dependencies weekly.
- Group minor and patch updates within each ecosystem; keep each major update in its own PR.
- Pin every workflow action to a verified full commit SHA, retaining its release tag as a comment.
- Do not change application behavior, dependency declarations, workflow triggers, or permissions.

## Constraints

- Use Dependabot configuration version 2 in `.github/dependabot.yml`.
- Keep the existing workflows’ functionality and action refs while replacing mutable tags with the verified SHAs currently resolved by those refs.

## Approaches

- Track each dependency update individually: simplest review boundaries, but creates more PRs.
- Group minor and patch updates per ecosystem while leaving major updates separate: fewer routine PRs while keeping breaking-version changes isolated. **Selected.**

## Implementation decisions

- Configure weekly updates for `pip` and `github-actions`.
- Use one minor/patch group for each ecosystem; leave major updates ungrouped so Dependabot opens one PR per dependency.
- Pin all actions in `.github/workflows/test.yml` and `.github/workflows/release.yml` to verified 40-character commit SHAs, with each original action ref in a comment for readability and Dependabot updates.
- Validate the YAML and confirm every action reference is SHA-pinned; run `git diff --check`.
