---
name: audit-crud
description: Audit CRUD endpoints. Produces idor / incorrect-authorization / business-logic-flaw findings related to access-control and mass-assignment.
---

# Role

Specialist for generic CRUD endpoints — `idor` and `incorrect-authorization` on resource read / update / delete paths, plus mass-assignment style `business-logic-flaw`.

# Trigger recap

Dispatched when identify-business-scenarios returns crud. NOTE: this skill is NOT mutually exclusive with audit-data-persistence — CRUD endpoints often persist data and both skills should run.

# SINK patterns

Business SINK checklist:

1. **Missing owner check**: handler takes resource_id and goes straight to DB
   read/update/delete with no `if resource.owner_id != current_user.id: forbidden`
   or equivalent
2. **Missing role gate**: admin-only / role-restricted operations have no
   `@requires_role("admin")` or equivalent guard
3. **Guessable IDs**: auto-increment integer ID + missing owner check = classic IDOR
4. **Hidden fields not gated**: DELETE / state-change endpoints check only the ID
   and not the caller's privileges
5. **Bulk-operation bypass**: `/api/users` list endpoint leaks PII for all users
6. **Nested-resource authz**: `/api/posts/<id>/comments` — checks ownership of the
   post, not of the comment
7. **Sibling-annotation asymmetry**: peer handlers in the same controller/class
   carry an authorization annotation (`@PreAuthorize`, `@Secured`, `@RolesAllowed`,
   Shiro `@RequiresPermissions` / `@RequiresRoles`, `@PermissionAllowed`, or a
   manual `checkPermission(...)` / `hasRole(...)` call) but **this** handler —
   performing a comparably sensitive or destructive operation — has none. That
   asymmetry is a strong missing-authorization signal; the absent guard is far
   more likely an oversight than a deliberate exemption. Scan the whole class
   before concluding a handler is unguarded.

Allowed `category_id` values for this skill: `idor`, `incorrect-authorization`, `business-logic-flaw`, `information-disclosure` (the last for the unauthorized-sensitive-exposure case below, where it is emitted *together with* `incorrect-authorization` — see item 8).

8. **Unauthorized sensitive/internal data exposure — emit BOTH categories.**
   When an endpoint reachable without proper authorization returns data the
   caller should not see, it is simultaneously two findings, and you must write
   **both** as separate entries:
   - `incorrect-authorization` — the missing auth gate, and
   - `information-disclosure` — the data leak itself.
   Emit both because the two are genuinely co-located facets of the same gap and
   ground-truth taxonomies label such endpoints **either** way; writing only one
   silently misses the other-labeled half. This covers: running configuration /
   environment, datasource URL / DB credentials, a built-in **SQL / DB-ops
   console** (e.g. `…/ops/derby` that executes caller-supplied SQL and echoes
   rows), **internal cluster / service / cache / session topology and
   service/tenant/user listings**, or a config/state-dump route (`…/config/dump`,
   `…/actuator/env`, `…/debugging/…`, `…/dump`). The `information-disclosure`
   facet is the per-endpoint counterpart of the file-scoped
   `global-audit-config` console/config-dump check — written HERE so the finding
   carries the **endpoint** target. Sensitivity gate still applies (see "Not a
   safe harbor" below): only when an unauthorized caller actually obtains
   sensitive / internal / cross-tenant data — do NOT emit either category for a
   genuinely public, non-sensitive, or strictly caller-scoped response.

# Not a safe harbor (do NOT suppress a real gap on these grounds)

- **"The route is public / permit-all / in the auth ignore-list."** An endpoint
  matched by `permitAll()`, `security.ignore.urls`, `@PermitAll`, a
  `SecurityFilterChain` exclusion, Shiro's `anon` filter chain, a custom auth
  filter's skip/exclude/allowlist (an explicitly-excluded URL pattern), or any
  auth-filter bypass pattern is **not** proof it is meant to be unauthenticated. If such an endpoint returns
  **sensitive** data — full resource / service / user lists, another user's or
  tenant's records, internal topology, configuration, or PII — the missing auth
  gate **is** the `incorrect-authorization` finding. Report it.
- **"Project docs / CLAUDE.md describe this path as public."** Documentation of
  the current (vulnerable) behavior is not a security decision; judge by what the
  endpoint actually exposes, not by how it is described.
- Sensitivity gate (avoids false positives): genuinely public surfaces stay
  safe — login / token endpoints, health probes returning `{status:UP}`, public
  catalogs, static assets, anything returning only non-sensitive or
  caller-scoped data. Flag only when an unauthenticated caller obtains data they
  should not be able to see.

# Safe context (false-positive prevention)

- File-upload related → `audit-file-upload`, not here.
- Downstream usage of persisted data (stored / second-order vulns where the dangerous sink fires elsewhere) → `audit-data-persistence` (often runs alongside this skill).
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
