---
name: record-vulnerabilities
description: |
  Canonical write protocol for audit-* skills. Tells worker the SimpleVulnInfo
  schema, where/how to Write the OUTPUT_FILE, and how to run validate_vulns.py
  to confirm the schema in one go. All audit-* skills MUST follow this protocol;
  bypassing it causes findings to be dropped at orchestrator load time.
---

# record-vulnerabilities

This skill defines the **only** legal way to record a worker's vulns. Audit-`<X>`
skills must invoke this skill at write time.

## Step 1 — Write the OUTPUT_FILE

One file per worker. Format: **flat JSON array** of `SimpleVulnInfo` items.
Zero vulns → write `[]` (do NOT skip the file).

### Schema

Each item must match this model (validated by `validate_vulns.py`):

```python
class CodeLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_path: str                 # relative to project root
    line: int | None = None        # 1-based; null if not resolvable (ge=1)

class SimpleExploitStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    todo: str                      # concrete attacker payload, e.g. "cmd=ls;id"

class SimpleVulnInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")   # ANY extra field → record REJECTED
    category_id: str                             # a valid VulnCategoryId (see list below)
    description: str
    exploit_steps: list[SimpleExploitStep] = []
    data_flow: list[CodeLine] = []               # ordered taint path; node lines MUST be real executable statements (see "data_flow precision")
    capabilities: list[str] = []                 # SensitiveCapability values: the sink(s) reached
    scenarios: list[str] = []                    # SensitiveScenario values: the endpoint's business flow
    endpoint: str = ""
    static_key: str = ""                         # field for static-key-leak
    static_key_type: str = ""                    # field for static-key-leak
    resource_name: str = ""                      # field for idor
    resource_operation: str = ""                 # field for idor
    scope_kind: str = ""                         # "" | "endpoint-set" | "application"
    scope_endpoints: list[str] = []              # used when scope_kind="endpoint-set"
    scope_mechanisms: list[str] = []             # used when scope_kind="application"
    root_cause_kind: str = ""                    # "injection" | "missing-control" | "misconfiguration" | "logic-flaw"
    root_cause_file: str = ""                    # file where the root cause lives
    root_cause_line: int | None = None           # line number (1-based)
```

### Required fields

| Field | Notes |
|---|---|
| `category_id` | Must be a valid VulnCategoryId (see list below) |
| `description` | One paragraph, 3-4 sentences, in the order below — see **description shape** |

### Optional fields

| Field | Default | Notes |
|---|---|---|
| `exploit_steps` | `[]` | Strongly recommended |
| `data_flow` | `[]` | Strongly recommended — orchestrator uses it for verify AND extracts the source/sink method snippets from it. **First node = where input enters; last node = the sink.** Every node line must be a real executable statement — see **data_flow precision** below. |
| `capabilities` | `[]` | The dangerous sink capability/ies this finding reaches (e.g. `sql-query`, `file-read`). Valid: see capability list below. |
| `scenarios` | `[]` | The endpoint's business scenario/s (e.g. `login`, `file-upload`). Valid: see scenario list below. |
| `endpoint` | `""` | The vulnerable HTTP endpoint |
| `static_key` | `""` | **`static-key-leak` only** — the leaked key's literal value (e.g. `"s3cr3t-k3y"`); lets the orchestrator build a `StaticKeyTarget` |
| `static_key_type` | `""` | `static-key-leak` only — what the key is for (e.g. `"Spring Security remember-me signing key"`) |
| `resource_name` | `""` | **`idor` only** — the resource the endpoint exposes (e.g. `"order"`); lets the orchestrator build an `IdorTarget` |
| `resource_operation` | `""` | `idor` only — the operation (e.g. `"read"`, `"delete"`) |
| `scope_kind` | `""` | Scope type. Empty = single endpoint (default). `"endpoint-set"` = a set of enumerable endpoints; `"application"` = a cross-cutting mechanism class (endpoints not enumerable). |
| `scope_endpoints` | `[]` | When `scope_kind="endpoint-set"`, list the concrete endpoints or a `/x/**` prefix wildcard. |
| `scope_mechanisms` | `[]` | When `scope_kind="application"`, list the affected subsystems, chosen from: `authentication` `authorization` `session-management` `cors` `csrf-protection` `cryptography` `transport-security`. |
| `root_cause_kind` | `""` | Nature of the flaw. One of: `injection` (has a taint flow) / `missing-control` (missing authn/authz/CSRF, no taint flow) / `misconfiguration` (key/weak config/exposure) / `logic-flaw` (business logic). **A source→sink taint flow means `injection`**; no taint flow but a missing check means `missing-control`. One kind per finding; split two root causes into two findings. |
| `root_cause_file` | `""` | File where the flaw lives (omittable for mechanism-level findings). |
| `root_cause_line` | `null` | Line where the flaw lives (1-based; omittable for mechanism-level findings). |

Per category: `static-key-leak` → leave `endpoint` empty, fill `static_key`
(+`static_key_type`) — it's a hardcoded/predictable key, not an endpoint.
`idor` → fill `endpoint` AND `resource_name` (+`resource_operation`).
Everything else → fill `endpoint`.

**Localization rule (every finding MUST have at least one locator, or it fails validation and cannot be scored):**
- An audit-endpoint finding **always fills `endpoint`** (it has a target).
- A global-audit target-less finding (empty `endpoint`) **must pick one of two locators**:
  - **Can pinpoint the exact vulnerable line** (framework-layer sinks like JWT/crypto/deserialization, e.g. `StatelessTokenService` using `.parse()` instead of `.parseClaimsJws()`) → fill `root_cause_file` + `root_cause_line` + `root_cause_kind` (the line number is already in your `data_flow` — promote it directly). **Do NOT** fill `scope_kind` for these.
  - **A cross-cutting gap with no single line to point at** (e.g. no global CSRF protection, CORS opened up globally) → fill `scope_kind="application"` + `scope_mechanisms` (+ optional `root_cause_*`).
- A "bare" finding with all of (`endpoint` / `static_key` / `scope_kind` / `root_cause_file`) empty is rejected by `validate_vulns.py`.

### description shape (2 sentences: where → why-not-safe)

Write `description` as ONE paragraph, 2-3 sentences, in this fixed order (English):

1. **The data flow** — In `<project>`'s `<METHOD /endpoint>`, name the tainted
   `<variable/field>`, the `<functions it passes through>`, and the
   `<sink function>` it reaches.
   Describe this as a call chain by name — no line numbers or code snippets here
2. **Why guards don't save it** (only when a guard exists) — name the guard and
   why it is bypassable (a denylist, wrong-context encoding, decode-after-check,
   a `..` that survives `resolve()`, …).

Keep it tight — one paragraph, no bullet list, no headings. Fold any extra
metadata into this prose, never into new fields (see **Forbidden fields**).

> **Example (path traversal).** In an app's file-upload endpoint `POST /upload`,
> the `Content-Disposition` filename flows unvalidated into `Path.resolve()`; a
> UUID prefix on the target dir does not stop a `..` in the filename from escaping
> after `resolve()`, and the extension allowlist check is a bypassable denylist.

### data_flow precision (every node must land on a real executable statement line)

`data_flow` is an **ordered taint path**: the **first node is where attacker input
enters this code** (the request/param read), the **last node is the sink** (the
dangerous operation), and any middle nodes are the assignments the tainted value
passes through. The host **extracts the enclosing method at the first and last
node** to fill the finding's source/sink code snippets — so an off-target line
silently empties those snippets.

Every node's `line` MUST be the exact 1-based line of a **real executable
statement inside a method/function body** — the line a debugger would stop on.
A node line must **NEVER** point at:

- a comment / javadoc / docstring (`/** … */`, a `*` continuation, `//`, `#`),
- an annotation / decorator (`@PostMapping`, `@app.route`, `@Override`),
- an `import` / `package` / `using` / `#include` line,
- a blank line, or a line that is only a brace (`}` / `{`),
- a bare method-or-class **signature** line that performs no taint operation.

Point at the line where the value is actually read, assigned, or passed into the
sink. The taint flows **inside** methods; a node that lands on the javadoc above a
method, or on a top-of-file import, is wrong even when it is "near" the right
place — move it onto the real statement.

```jsonc
// command injection: source = the param read, sink = the exec call — both real statements
"data_flow": [
  {"file_path": "src/main/java/.../VulnController.java", "line": 52},  // String cmd = request.getCmd();
  {"file_path": "src/main/java/.../CommandService.java", "line": 59}   // Runtime.getRuntime().exec(cmd);
]
// WRONG: line 47 (the `/**` above the method) or line 7 (an `import`) — they carry no taint
```

### Forbidden fields

`extra="forbid"` means writing ANY field not listed above makes
`validate_vulns.py` reject the whole record. Never write: `severity`, `title`,
`id`, `confidence`, `cvss`, `sink`, `source`, `parameter`, `vector`,
`remediation`, `references`, `cwe`, `cwe_id`, `cve`, `missing_defenses`,
`impact`, `notes`, any `*_aspect`. Fold rich metadata into `description` as prose.

### Examples

```json
[
  {
    "category_id": "sql-injection",
    "description": "In the app's GET /api/users, the `q` query param flows unescaped into a string-concatenated query in UserDao.search(); no parameterization or escaping is applied.",
    "exploit_steps": [{"endpoint": "/api/users", "todo": "q=1' OR '1'='1"}],
    "data_flow": [{"file_path": "app/dao/UserDao.java", "line": 42}]
  },
  {
    "category_id": "static-key-leak",
    "description": "Spring Security's remember-me signing key is hardcoded as a string literal in SecurityConfig.java, so anyone can mint valid remember-me cookies and impersonate any user.",
    "endpoint": "",
    "static_key": "super-secret-rememberme-key",
    "static_key_type": "Spring Security remember-me signing key",
    "data_flow": [{"file_path": "src/main/java/.../SecurityConfig.java", "line": 42}]
  },
  {
    "category_id": "idor",
    "description": "In the app's GET /api/orders/{id}, the order id is taken from the path and loaded in OrderController.view() with no ownership check tying the order to the caller.",
    "endpoint": "/api/orders/{id}",
    "resource_name": "order",
    "resource_operation": "read",
    "data_flow": [{"file_path": "app/order/OrderController.java", "line": 88}],
    "root_cause_kind": "missing-control",
    "root_cause_file": "app/order/OrderController.java",
    "root_cause_line": 88
  },
  {
    "category_id": "cors-misconfiguration",
    "description": "The global CORS policy in CorsConfig.java reflects any Origin back with credentials allowed, so every endpoint's data can be read from a victim's browser by an attacker-controlled page.",
    "endpoint": "",
    "scope_kind": "application",
    "scope_mechanisms": ["cors"],
    "root_cause_kind": "misconfiguration",
    "root_cause_file": "src/main/java/com/example/config/CorsConfig.java",
    "root_cause_line": 22
  }
]
```

## Step 2 — Mandatory validation

After every Write of OUTPUT_FILE, you MUST run:

```bash
python .claude/skills/record-vulnerabilities/scripts/validate_vulns.py <OUTPUT_FILE>
```

- **Exit 0**: done. Proceed to your final report-back.
- **Non-zero**: read stderr. It tells you precisely which item index, which
  field, why. Use `Edit` to fix OUTPUT_FILE accordingly, re-run validate.
  Loop until exit 0.

Do **not** call your final report-back before validate exits 0.

## Valid `category_id` values (VulnCategoryId enum)

```
business-logic-flaw       code-injection            command-injection
cors-misconfiguration     csrf                      dos
el-injection              http-response-splitting   idor
incorrect-authentication  incorrect-authorization   incorrect-signature-verification
information-disclosure    insecure-archive-extract  insecure-crypto-configuration
insecure-database-connection insecure-deserialization insecure-file-delete
insecure-file-read        insecure-file-upload      insecure-file-write
insecure-random           jndi-injection            ldap-injection
nosql-injection           open-redirection          path-traversal
prompt-injection          sql-injection             ssrf
ssti                      static-key-leak           weak-credentials
xpath-injection           xslt-injection            xss
xxe-injection
```

The list above is authoritative for what `validate_vulns.py` accepts. The script
keeps this list in sync with `vuln_spec.VulnCategoryId` via the companion
`test_validate_vulns_schema.py`.

## Valid `capabilities` values (SensitiveCapability enum)

```
code-eval          shell-exec         process-spawn      expression-eval
xpath-eval         binary-deserialize string-deserialize xml-parse
template-render    sql-query          nosql-query        file-read
file-write         file-rename        file-delete        archive-extract
url-access         jndi-lookup        url-redirect       xslt-transform
ldap-query         llm-invoke
```

## Valid `scenarios` values (SensitiveScenario enum)

```
login                      register                   password-reset
profile-update             payment                    file-upload
crud                       data-persistence           response-rendering
security-random-generation scheduled-task             configuration-management
file-download              outbound-request           search
```
