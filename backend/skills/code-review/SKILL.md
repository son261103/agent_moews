---
name: code-review
description: Review code systematically for correctness, security, and maintainability before reporting findings.
---

# Code Review Skill

Follow these steps when the user asks for a code review:

1. Read the file(s) under review.
2. Check for: correctness bugs, security issues (injection, secrets, auth), maintainability (dead code, unclear names).
3. List findings as `[severity] file:line — issue` (severity: HIGH/MED/LOW).
4. For each HIGH finding, propose a concrete fix.
5. End with an overall verdict (Approved / Needs changes).
