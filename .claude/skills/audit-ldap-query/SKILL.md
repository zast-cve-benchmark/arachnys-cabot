---
name: audit-ldap-query
description: Audit endpoints with ldap-query capability. Produces ldap-injection findings.
---

# Role

Specialist for **ldap-injection**. Produces findings with `category_id` = `ldap-injection`, aligned with the
audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `ldap-query`.

# SINK patterns

| Language | SINK |
|---|---|
| Java   | `DirContext.search(name, filter_concat, ...)`, `LdapContext.search(name, filter_concat, ...)` where `filter_concat` is string concatenation |
| Python | `ldap3.Connection.search(search_filter=concat)`, `python-ldap`'s `Connection.search_s(base, scope, filterstr=concat)` |
| Node   | `ldapjs.Client.search(base, {filter: concat}, ...)` |
| PHP    | `ldap_search($ldap, $base, $filter)` where `$filter` contains user input |
| Go     | `ldap.SearchRequest{Filter: concat}` |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param /
header / body / path param, or data carried via state (DB / session / file). If the source is a constant or
system-controlled value, do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- Filters built with proper escape helpers such as `LdapEncoder.filterEncode(user)` /
  `ldap3.utils.conv.escape_filter_chars(user)` / equivalent per-language filter-escaping APIs
- LDAP filters that are entirely static constants
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories belong to other audit skills — JNDI lookup (LDAP URL controllable) -> `audit-jndi-lookup`. If you
spot them, mention them in your report and let the orchestrator dispatch the right specialist; do not file them
yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
