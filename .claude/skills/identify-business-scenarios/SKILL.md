---
name: identify-business-scenarios
description: |
  For a given endpoint, identify which SensitiveScenario values its handler
  exposes. Output a JSON array of matching scenario ids. Use as the business-
  scenario triage front end for the audit-endpoint skill, alongside
  identify-sensitive-capabilities.
---

# identify-business-scenarios

## Inputs

The invoking prompt contains two lines:

- `ENDPOINT: <METHOD path>` — the one handler you are triaging.
- `SNIPPETS_FILE: <absolute path>` — Read this first; it is the handler + first-level
  callees (each chunk headed by `// <file>#L..`). Treat it as the primary evidence pool.
  Grep/Glob/Read beyond it only when a sibling/stored-render handler needs it.

Emit your answer for `ENDPOINT` as the single JSON array described under "Output".

## Scenario taxonomy

```python
from enum import StrEnum


class SensitiveScenario(StrEnum):
    """Web-application-bound security-sensitive scenarios an endpoint participates in.

    Scenarios describe *what the handler is doing as a web-app behavior pattern*,
    independent of whether attacker-controlled input is involved. The "user
    input is dangerous" judgment is left to the corresponding audit skill.
    """

    LOGIN                      = "login"
    REGISTER                   = "register"
    PASSWORD_RESET             = "password-reset"
    PROFILE_UPDATE             = "profile-update"
    PAYMENT                    = "payment"
    FILE_UPLOAD                = "file-upload"
    CRUD                       = "crud"
    DATA_PERSISTENCE           = "data-persistence"
    RESPONSE_RENDERING         = "response-rendering"
    SECURITY_RANDOM_GENERATION = "security-random-generation"
```

## Match criteria (hit conditions per scenario)

### `login`
Path / handler name / handler behavior points to a user authentication login flow:
- Path contains `login` / `signin` / `auth`
- Handler invokes password comparison, JWT issuance, session creation
- Failure-count tracking, verify-code checking

### `register`
New user registration:
- Path contains `register` / `signup`
- Handler creates a user record, writing username / email / password hash
- Emit `register` even when the endpoint looks like it "shouldn't" accept public
  signups — whether registration **should be restricted** is itself part of the
  audit. In an authentication-gated back-office / admin / internal system, an
  anonymous-reachable registration endpoint is a broken-access-control flaw, and
  audit-register is what judges that. Do not skip it because "this is an admin
  app so registration must be intentional."

### `password-reset`
Password reset flow:
- Path contains `reset-password` / `forgot-password`
- Handler validates a reset token, updates the password field

### `profile-update`
An authenticated user updates their own profile:
- Handler accepts a user-id and runs an UPDATE on the user record
- Typically PUT/PATCH to `/users/me` / `/profile/{id}`

### `payment`
Payment / refund / order amount changes:
- Path contains `pay` / `order` / `charge` / `refund`
- Handler writes an amount / calls a payment gateway

### `file-upload`
File upload:
- Handler accepts multipart/form-data
- Calls `MultipartFile.transferTo()` / `request.files` etc.
- Path commonly contains `upload`

### `crud`
Generic create/read/update/delete endpoint **OR any privileged / state-changing
action that needs an authorization gate** (this scenario owns the
access-control / missing-authorization audit, so cast it wide):
- RESTful URL (`/api/<resource>/{id}`)
- Handler directly calls ORM `.save()` / `.delete()` or raw `INSERT|UPDATE|DELETE`
- **Reads or returns data that is not the caller's own** — a list/search/detail
  endpoint that returns resources, service/user/tenant listings, internal
  topology, or config (e.g. `/.../list`, `/.../search`, `/.../{id}`)
- **Privileged or maintenance action**, even when the URL is an action verb
  rather than a REST resource and even when it touches no ORM — cache
  reset/flush, config reload, shutdown/restart, enable/disable, trigger/run a
  job, import/export, clear/purge, user or permission management. These are the
  classic broken-access-control surface; emit `crud` so the access-control
  specialist runs and checks whether the caller is authorized (e.g. does this
  handler carry the authz annotation/guard its sibling handlers have?).
- Often **hits together** with data-persistence (do not dedupe)

When unsure whether an endpoint "counts" as crud, **emit it** — broken access
control is the most commonly-missed vulnerability class precisely because it is
about an *absent* guard, not a visible sink, so the recall cost of skipping it
is high.

### `data-persistence`
Handler writes **user input** (whether attacker-controllable is for the audit skill to judge) into a persistent store — provides entry points for downstream second-order / stored vuln audits:
- Writes into an in-memory datastore that gets serialized to disk (typical shape: `global_store[<key>] = <user-data>` + periodic/exit-time dump to disk)
- ORM persistence: `.save()` / `Model.objects.create()` / `session.add()` / `session.commit()`
- Raw SQL `INSERT` / `UPDATE`
- File writes, persistent cache writes
- Writes to global config / global settings objects
- **Persist-verb delegation (emit deterministically — do NOT require seeing the
  actual ORM call):** the handler passes a user-supplied object/DTO to a
  service / mapper / repository / DAO method whose name begins with
  `insert` / `add` / `save` / `create` / `update` / `persist` / `store` /
  `register` / `import` / `batch*` (e.g. `jobService.insertJob(job)`,
  `userMapper.batchInsert(list)`, `xxxRepository.save(dto)`). The `.save()` /
  `INSERT` lives one or two layers down (service impl → mapper XML) and is **not
  in your snippet** — the persist-verb + user object IS the signal. This is the
  #1 cause of a flaky/missed `data-persistence` dispatch (and therefore of
  silently-dropped stored / second-order findings like the Quartz `invokeTarget`
  reflection chain and stored XSS via bulk-import). When a handler calls such a
  method with request-derived data, **always emit `data-persistence`.**

**Not mutually exclusive with crud** — CRUD endpoints often persist data simultaneously; both scenarios hit and each dispatches its own audit skill.

### `response-rendering`
The handler's return value is consumed by the frontend for rendering:
- Any response that returns HTML (`Content-Type: text/html`, including Flask bare-string return / Servlet writer / Express `res.send(string)`)
- Responses rendered via a template engine (Jinja2 / Thymeleaf / FreeMarker / EJS etc.)
- Endpoints returning JSON / XML / RSS for frontend parsing (surface the signal here; audit-response-rendering decides internally whether escaping is sufficient)

### `security-random-generation`
The handler invokes a RNG and the result is used in a security-sensitive context:
- RNG primitives: `Math.random` / `random.*` / `rand()` / `mt_rand()` / `uuid.*` / `System.currentTimeMillis()` etc.
- **And** the result is assigned to / used as: `session` / `token` / `cookie` / `nonce` / `OTP` / `salt` / `password` / `key` / `verification_code` / `reset_token` etc. naming context

If it is merely a security-irrelevant UUID (e.g. request id, ad rotation selection), do not hit.

## Systematically under-emitted scenarios (check before finalizing)

- **Access control** — if the handler performs a privileged or state-changing action, or
  reads/returns data that is not the caller's own (resource/service/user/tenant listings,
  admin/maintenance actions like cache reset, config reload, shutdown, enable/disable,
  trigger-job, import/export — even when the URL is an action verb and no ORM is touched),
  emit `crud` so the access-control specialist runs. Tell: this handler lacks an
  authorization annotation/guard that a sibling handler in the same controller carries.
- **Stored / second-order render (stored XSS)** — if the handler persists or bulk-imports
  user-supplied **free-text display fields** (name, title, nickname, content, remark,
  description, comment, message, label, address — anything later shown in a UI), emit
  **both** `data-persistence` **and** `response-rendering`. The dangerous render usually
  happens on a *different* endpoint (a list/detail/admin view), so a handler-local view
  misses it; bulk-import/batch-save endpoints are the highest-yield case.

## Favor recall over precision

Same as `identify-sensitive-capabilities`: prefer over-inclusion over missed reports. Missing a scenario = missing the dispatch of an entire audit skill = missing a whole class of potential findings. Dispatching one extra audit skill = it finishes with 0 findings and exits, costing only one extra dispatch.

On easy-to-overlap boundaries like `crud` ↔ `data-persistence`, **emit both**.

## Workflow

1. **Read the code.** Snippets-file path, source file path, or inline snippets.
2. **Walk through the taxonomy scenario by scenario**, deciding include / exclude for each.
3. **When in doubt, lean toward include.**

## Output

The final assistant message must be a single ```json fenced block containing a
flat array of `SensitiveScenario` enum values — no surrounding prose, no object
wrapper.

```json
["login", "data-persistence", "response-rendering"]
```

Empty hit → `[]`.

Each element must be one of:

```
login, register, password-reset, profile-update, payment, file-upload, crud,
data-persistence, response-rendering, security-random-generation,
scheduled-task, configuration-management, file-download, outbound-request, search
```

Output schema (generated from `RootModel[list[SensitiveScenario]]`):

```
{"$defs": {"SensitiveScenario": {"enum": ["login", "register", "password-reset", "profile-update", "payment", "file-upload", "crud", "data-persistence", "response-rendering", "security-random-generation", "scheduled-task", "configuration-management", "file-download", "outbound-request", "search"], "type": "string"}}, "items": {"$ref": "#/$defs/SensitiveScenario"}}
```
