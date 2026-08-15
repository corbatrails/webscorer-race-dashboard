---
description: "How to manage project rules when the user asks to add, remove, or update them"
alwaysApply: true
---

# Managing Project Rules

## Adding Rules

When the user says "add rule", "new rule", "remember that", "in this project we always", or otherwise asks to record a project convention or spec:

1. Append the rule as a bullet point to `.github/instructions/project-rules.instructions.md` under the `# Project Rules` heading.
2. Keep rules concise — one line per rule.
3. Prefer rules about *conventions and processes*, not specific values. If a rule is about a configurable value, reference where the value lives (e.g., "Cache TTL is defined in `config.py`") rather than hardcoding the value in the rule.
4. Do not duplicate existing rules. If a rule already exists, tell the user.
5. Confirm what was added.

## Removing Rules

When the user says "remove rule" or "delete rule", remove the matching bullet from that file and confirm.

## Auditing Rules

When the user says "audit rules", "check rules", or "are the rules still accurate":

1. Read `.github/instructions/project-rules.instructions.md`.
2. For each rule, verify it against the current codebase (check referenced files, config values, patterns).
3. Report any rules that appear outdated or contradicted by the code.
4. Suggest updates or removals, but do not modify without user confirmation.

## During Implementation

When completing any feature or fix, review the project rules list. If the change contradicts or obsoletes an existing rule, flag it to the user and suggest updating or removing the rule.
