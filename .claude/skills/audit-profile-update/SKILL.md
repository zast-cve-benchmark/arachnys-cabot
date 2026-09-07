---
name: audit-profile-update
description: Audit profile / account-info update endpoints. Produces idor (cross-user write) and business-logic-flaw (mass-assignment, privilege escalation via profile fields, password field smuggling, missing audit trail) findings.
---

# Role

Specialist for profile-update `idor` / `business-logic-flaw`.

# Trigger recap

Dispatched when identify-business-scenarios returns profile-update.

# SINK patterns

Key points from `logic-vuln-audit/modules/profile_update/step2_sinks.md`:

1. **Target user ID from request**: `POST /api/users/<id>/profile` does not verify `<id>` is the current user
2. **Mass-assignment**: handler feeds the whole JSON directly to the ORM update, including sensitive fields like `role` / `is_admin` / `email` / `balance`
3. **Email/phone change without re-verification**: accepts the new email directly, no verification email sent
4. **Password field silently updated**: profile update payload contains `password` and is processed as a password reset — bypassing current-password check
5. **No audit trail**: sensitive-field updates without audit log

Allowed `category_id` values for this skill: `idor`, `business-logic-flaw`.

# Safe context (false-positive prevention)

- Avatar upload / multipart file handling on the profile endpoint → handled by `audit-file-upload`, not here.
- Generic CRUD authorization on resources that happen to be owned by the user (non-profile fields, e.g. `/api/posts/{id}`) → `audit-crud`.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
