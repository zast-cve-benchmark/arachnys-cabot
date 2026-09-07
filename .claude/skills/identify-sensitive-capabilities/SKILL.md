---
name: identify-sensitive-capabilities
description: |
  For a given endpoint, identify which SensitiveCapability values its handler
  exposes. Output a JSON array of matching capability ids. Use as the capability
  triage front end for the audit-endpoint skill, or standalone to understand any
  endpoint's security surface.
---

# identify-sensitive-capabilities

## Inputs

The invoking prompt contains two lines:

- `ENDPOINT: <METHOD path>` — the one handler you are triaging.
- `SNIPPETS_FILE: <absolute path>` — Read this first; it is the handler + first-level
  callees (each chunk headed by `// <file>#L..`). Treat it as the primary evidence pool.
  Grep/Glob/Read beyond it only when a stored-sink or sibling handler (Route B) needs it.

Emit your answer for `ENDPOINT` as the single JSON array described under "Output".

## Capability taxonomy

```python
from enum import StrEnum


class SensitiveCapability(StrEnum):
    """Security-sensitive capability exposed by a function.

    A capability describes a function's security-relevant action surface — what
    it does at the system level that warrants audit attention. It is a property
    of the function itself, independent of whether the function is currently
    being analyzed as a sink, source, or sanitizer.

    Naming convention:
      *_EVAL       — interpret a string as code/expression in the current runtime
      *_EXEC       — hand control to a new OS process (or shell)
      *_PARSE / *_DESERIALIZE — turn external data into in-process objects
      *_QUERY      — issue a query against a data store
      *_LOOKUP     — resolve a name through an external naming service
      FILE_*       — filesystem operations on a single path
    """

    CODE_EVAL = "code-eval"
    SHELL_EXEC = "shell-exec"
    PROCESS_SPAWN = "process-spawn"
    EXPRESSION_EVAL = "expression-eval"
    XPATH_EVAL = "xpath-eval"
    BINARY_DESERIALIZE = "binary-deserialize"
    STRING_DESERIALIZE = "string-deserialize"
    XML_PARSE = "xml-parse"
    TEMPLATE_RENDER = "template-render"
    SQL_QUERY = "sql-query"
    NOSQL_QUERY = "nosql-query"
    LDAP_QUERY = "ldap-query"
    FILE_READ = "file-read"
    FILE_WRITE = "file-write"
    FILE_RENAME = "file-rename"
    FILE_DELETE = "file-delete"
    ARCHIVE_EXTRACT = "archive-extract"
    URL_ACCESS = "url-access"
    JNDI_LOOKUP = "jndi-lookup"
    LOGGING_SINK = "logging-sink"
    URL_REDIRECT = "url-redirect"
    XSLT_TRANSFORM = "xslt-transform"
    LLM_INVOKE = "llm-invoke"
```

## Inclusion rule (READ THIS BEFORE DECIDING)

For each capability, emit it if the endpoint exposes it via **any** of these
three routes. Do **not** require a direct call inside the handler.

### Route A — Direct invocation

The handler (or any function it calls in this request) directly invokes an API
that matches the capability. Examples:
- `subprocess.run([...])` or `Runtime.exec(...)` → `shell-exec` / `process-spawn`
- a SQL/query string handed to a **database driver or ORM for execution** → `sql-query` (language/driver-agnostic — judge by "a query string reaches a DB execute call", not by a specific API name): `cursor.execute(sql)` / `entityManager.createQuery(...)` / Go `db.Query(q)`·`db.QueryContext(ctx, q)`·`db.Exec(q)`·`db.QueryRow(q)` / `sqlx.Get/Select(q)` / GORM `.Raw(q)`·`.Exec(q)` / MyBatis `${}` mapper / any driver `query/execute/run` taking a SQL string. **The query being built by string concatenation / `fmt.Sprintf` / f-string / `+` / interpolation is the injection signal** — emit `sql-query` whenever a built or interpolated query reaches any such execute call, even when the driver isn't one named above.
- `template.render(...)` / `Jinja2 from_string(user)` → `template-render`
- `pickle.loads(...)` / `ObjectInputStream.readObject()` → `binary-deserialize`
- `requests.get(url)` / `urllib.request.urlopen(url)` / `URL(url).openStream()` / `file_get_contents(url)` → `url-access`. Note these APIs accept beyond `http(s)://` — `file://` / `ftp://` / `ws(s)://` / `php://filter` / `gopher://` etc., so the attack surface spans SSRF + local file disclosure + internal port scanning + JNDI lookup chains via the same capability.
- `logger.info(x)` / `log.error(x)` / `LOG.debug("..." + x)` / `logger.warn("{}", x)` where `x` is user-controlled → `logging-sink`. A logged user input is a sink because the logging framework may interpolate it: on **log4j2 < 2.17** (or any vulnerable version per CLAUDE.md Stack / dependency manifest), a logged `${jndi:ldap://...}` payload triggers a Log4Shell RCE — so `logging-sink` routes to the `audit-jndi-lookup` worker. Emit it whenever user input reaches any logging call and the project depends on a vulnerable log4j2; if the version is unknown, favor recall and emit it.
- A user-supplied **file path / resource locator** handed to a framework or library that locates, loads, reads, or distributes that file → `file-read` (and `archive-extract` if the resource is an archive). The literal `open()`/read happens **inside the framework**, not in the handler, so judge by the parameter's *role* — it names a file the system will load — not by a visible `open()`. This is the standard shape of job / session / plugin / driver submission: params like `file` / `appResource` / `mainJar` / `jars` / `pyFiles` / `archives` / `classpath` / `lib` / `path` / `resource` / `driverPath` fed to a job-or-session builder (Spark/Livy/Flink/Hadoop/Beam, Quartz/job runners), a plugin/extension loader, or `ClassLoader`/`URLClassLoader` / `addFile` / `addJar`. Such a path is attacker-controllable → path-traversal / arbitrary-file-read (and remote-jar load if a URL scheme is accepted). Emit `file-read` so audit-file-ops checks the traversal; if the same value can be a URL, also emit `url-access`.

### Route B — Stored-sink (cross-handler, second-order)

The handler **persists user-controlled data** into a shared store (DB, file,
in-process datastore, global config) such that **another code path** in this
project later passes that stored value to a capability API. The capability is
exposed by this endpoint, even though this endpoint itself only writes.

Common pattern: an endpoint accepts a string field (an expression, URL,
filename, template, query, header, etc.) from the user, persists it, and a
background worker / scheduled task / sibling endpoint later **evaluates /
fetches / reads / renders** it.

Patterns to recognize (by the *shape* of the persisted field, regardless of
field name):

| Source (persisted in this handler) | Downstream sink (elsewhere) | Capability(ies) to emit |
|---|---|---|
| URL string | outbound HTTP call (`requests.get`, `URL.openStream`, `http.Get`, ...) | `url-access` |
| filter / selector expression (XPath family) | `xpath()` / `select()` / `evaluate()` | `xpath-eval` |
| expression / query string for a general-purpose evaluator (jq, JSONPath, SpEL, OGNL, MVEL, JEXL, JSP EL, ...) | `<engine>.compile(stored).run(...)` / `<engine>.eval(stored)` | `expression-eval` |
| template / message body string | template-engine render of the stored string | `template-render` |
| raw query / SQL fragment | string-concatenated into a SQL/NoSQL query | `sql-query` / `nosql-query` |
| file path / filename | file open / move / read / write on the stored path | `file-read` / `file-write` |
| serialized blob (yaml / json / pickle / java serialized) | `yaml.load` / `pickle.loads` / `ObjectInputStream` | `string-deserialize` / `binary-deserialize` |
| **method / bean / class reference string** (`beanName.method('arg')`, a `invokeTarget` / `jobClass` / `handler` / `className` / `methodName` / `target` field) | reflective dispatch elsewhere — `getBean(name)` + `Method.invoke(...)`, `Class.forName(s).newInstance()`, scheduler/Quartz `JobInvokeUtil.invokeMethod`, `ScriptEngine.eval` | `code-eval` (also `jndi-lookup` / `binary-deserialize` if the invoked target can reach those) |
| LDAP filter fragment | `ctx.search(stored, ...)` | `ldap-query` |
| XML body | unsafe XML parser without disabled DTD/entity | `xml-parse` |

To detect Route B, **scan the handler for write-into-persistent-store calls** —
`datastore[...] = ...`, `.save()`, `Model.objects.create()`, `session.add()`,
`INSERT`/`UPDATE`, file writes, global-config writes — then ask: "what consumes
this stored data later in this project?" Use Grep on the field name to find the
downstream reader before deciding.

If you can confirm the downstream sink with a Grep, emit the capability.
If you cannot confirm but the field's *shape* (URL / expression / template /
path / serialized blob / query string) matches one of the rows above, **emit
it anyway** — false-negatives are catastrophic, see below.

### Route C — Multi-engine dispatch on a single field

Some fields accept expressions that get dispatched to different evaluators by
prefix or type tag. Each engine is its own capability — emit one per engine.

Common dispatcher shapes you must recognize:

- `value.startswith("<engine-name>:")` / regex `^([a-z]+):(.*)$` on the stored
  field, with an `if/elif` chain mapping each prefix to a different evaluator.
- A `Map<String, Engine>` lookup keyed by the prefix.
- A type-tag field on the surrounding record (`type: "xpath"` / `type: "jq"`)
  selecting an engine.

Each branch reachable from such a dispatcher contributes its evaluator's
capability:

| Evaluator family | Capability |
|---|---|
| XPath / XQuery (any prefix or tag selecting an XPath evaluator) | `xpath-eval` |
| jq / JSONPath / SpEL / OGNL / MVEL / JEXL / JSP EL / any general-purpose expression engine | `expression-eval` |
| Template engine (Jinja2 / Freemarker / Velocity / Twig / ...) | `template-render` |
| SQL / NoSQL evaluator | `sql-query` / `nosql-query` |
| CSS selector (HTML extraction) | not security-relevant alone; usually safe |

If you see a prefix-or-tag dispatcher with **two or more** branches reaching
evaluators in the table, **emit one capability per branch**, even if the
visible validator name only hints at one of them. (Validator names lag behind
implementation.)

### Route D — one sink, multiple capabilities

A single sink frequently exposes **more than one** capability. Do not stop at
the first/most-obvious one — emit every capability the sink enables. The
endpoint will otherwise score a partial miss (the audit reports one CVE class
and silently drops the co-located others). Known multi-capability sinks:

| Sink | Capabilities to emit (all of them) |
|---|---|
| SnakeYAML `Yaml.load(user)` / `yaml.load` | `binary-deserialize` **+** `url-access` (SnakeYAML tags can fetch remote URLs / construct arbitrary objects → both deserialization RCE and SSRF) |
| Generic expression evaluator on user input (SpEL / OGNL / MVEL / JEXL / Groovy `evaluate`/`GroovyShell`) | `code-eval` **+** `expression-eval` |
| Reflective / dynamic invocation of a user-named target (e.g. a quartz/scheduler `invokeTarget`, `Method.invoke(beanName,...)`, `Class.forName(user)`) | `code-eval` (the invoked target may itself reach deserialize / jndi / sql sinks — if you can see that downstream, emit those too) |
| User-controlled **filename** written to disk (upload) | `file-write` **+** `file-read`/`file-delete` if the same name is later read/removed; the path-traversal risk is covered by the `file-*` capabilities |
| Object deserializer fed a gadget-bearing payload (`ObjectInputStream`, fastjson `parseObject` with autotype, XMLDecoder) | `binary-deserialize`/`string-deserialize` **+** `url-access` (gadget chains commonly trigger JNDI/HTTP fetches) |
| `InitialContext.lookup(user)` or a logged user value on vulnerable log4j2 | `jndi-lookup` **+** `logging-sink` |

When a user-controlled value reaches one of these, emit **the full set** — the
recall cost of emitting only the headline class is exactly the co-located misses
we are trying to eliminate.

## Favor recall over precision

A missed capability silently skips an entire CVE class — Phase 4 of
audit-endpoint will never dispatch the specialist that would have caught it.

A false-positive capability costs one extra specialist dispatch that produces
no finding.

**The asymmetry is huge: prefer false positives.** When in doubt, include the
capability.

Specifically avoid these mistakes:
- "It's just a log statement, logging is harmless" — **wrong** when the stack is
  log4j2: a logged user-controlled value (`LOGGER.info("x=" + user)` **or**
  `LOGGER.info("x={}", user)`) is a Log4Shell `logging-sink`. This is the most
  overlooked sink because logging looks benign and the sink is often in a
  **callee** (a service/helper the handler calls), not the handler body — follow
  the call chain. Emit `logging-sink` whenever user input reaches any
  `logger.{info,warn,error,debug,fatal,trace,log}(...)` call and the project uses
  log4j2; if the log4j version is unknown, favor recall and emit it anyway.
- "The actual sink runs in a worker, outside this handler's scope, so I exclude
  it" — **wrong**: Route B explicitly covers this case
- "The validator only allows safe syntax, so the engine is parameterized" —
  **wrong** unless the validator restricts the evaluator's *dangerous builtins*
  (every general-purpose expression engine has them — file read, env read,
  reflection, runtime exec — that survive any "does it compile" check). Most
  validators are compile-only and accept anything the engine itself accepts.
- "Only one of the multi-engine prefixes is mentioned in the field's label /
  validator name, so I emit only that one" — **wrong**: Route C says emit all
  reachable engines

Exclude a capability only when you can point at concrete neutralizing code:
- `PreparedStatement.setString(...)` with bind variables — true parameterization
  for `sql-query`
- `subprocess.run([cmd, *argv])` with `shell=False` and a fixed `cmd` — sandboxed
  `shell-exec`
- Template engine in sandbox mode with explicit allowlist of constructs — neutralized
  `template-render`

Without one of those, do **not** exclude.

## Framework-implicit sinks

An endpoint's capabilities are not fully determined by its handler code.
Frameworks invoke security-relevant actions by convention — view resolution,
data binding, serialization — that do not appear as explicit API calls.
Identify these implicit sinks by examining the handler's signature (return
type, annotations, parameter types) against the project's Stack (from
CLAUDE.md).  Read the matching reference for framework-specific patterns:

| Stack keyword | Reference |
|---|---|
| Thymeleaf / Spring MVC | `references/thymeleaf.md` |

## Systematically under-emitted capabilities (check before finalizing)

These describe a *benign-looking* sink the routes above miss; add the id if it applies:

- **Logging sink (Log4Shell)** — any user-controlled value reaching a logger
  (`logger.{info,warn,error,debug,fatal,trace}(...)`, concatenated or `{}`-parameterized,
  including inside a callee), on a log4j2 stack → emit `logging-sink`. If the log4j
  version is unknown, emit it anyway.
- **Open redirect** — a redirect (`res.redirect(...)`, `sendRedirect(...)`, a `Location`
  header, any 3xx helper) whose target is built from a request-derived value —
  **including indirect** ones (`Host` / `X-Forwarded-Host` / `Referer`, or a
  `baseHref`/`returnTo`/`next` derived from them) → emit `url-redirect`. The taint looks
  benign (an internal-looking base href that is in fact Host/Referer-pollutable), so it
  is systematically missed.

## Workflow — follow these steps in order, do not skip

1. **Read the code.** Snippets-file path, source file path, or inline snippets.
   The header `// <file>#Lsl-Lel` of each block tells you the source file.
   Supplement with Glob/Grep if insufficient (Read ≤ 8 times, ≤ 3000 lines).

2. **Enumerate every user-controlled input** that flows through the handler
   (path params, query string fields, JSON body fields, form fields, headers,
   uploaded file content). List them by name. Do this **before** thinking
   about capabilities.

3. **Trace each input through the handler.** For every input from step 2,
   classify what the code does with it:

   - **Used directly in an API call** in the handler → Route A capability
   - **Persisted to storage** (`datastore[...] = ...`, `.save()`, ORM `create()`,
     SQL `INSERT`/`UPDATE`, file write, global config set) → Route B candidate.
     **You MUST then Grep the stored field name across the project** to find
     who reads it later, using both `record["<field>"]` / `record.get("<field>")`
     ORM-attribute, and direct attribute-access shapes appropriate for the
     stack. What you find in the worker / scheduled task / sibling endpoint
     determines the capability. Do **not** skip this Grep on the grounds that
     "the sink is out of scope" — Route B explicitly puts it in scope.
   - **Dispatched on a prefix / type tag** to multiple evaluators → Route C
     (emit one capability per reachable engine)

4. **Walk through the enum exhaustively.** Go through EVERY capability in the
   taxonomy block above (~22 entries) and decide include/exclude. Do not stop
   after finding 1-2 matches. The output should reflect ALL hits, not just
   the most obvious ones.

5. **Apply the recall-over-precision rule** when in doubt. Specifically, if a
   field name or its form-definition / validator / label / docstring suggests a
   sink-class shape (URL / filter / selector / template / path / command /
   query / expression / script / regex / serialized-blob), emit the
   corresponding capability even if you could not confirm the downstream sink
   with Grep (the project may simply be too large for an exhaustive trace in
   this read budget).

6. **Output the JSON array** containing every capability that hit on any of
   routes A/B/C.

## Common failure mode to avoid

A handler that mainly **persists user input** (creates / updates a record;
saves config) often looks "boring" — no eval, no exec, no SQL string concat
visible in the handler itself. Two wrong reactions are common:

- "The handler is mostly validation + a `.save()` — so the only capability is
  `file-write` (or none)." → **wrong**. The persisted record's fields each
  unlock a Route B capability via whichever worker / scheduled task / sibling
  endpoint reads them.
- "The persisted field looks like a free-text string, no exotic shape." →
  **wrong** if any reader of that field passes it to an evaluator, fetcher,
  renderer, or path operation. Confirm by Grep, not by surface inspection.

Concretely: a handler that persists a URL + a filter expression + a body
string typically exposes at minimum three capabilities (`url-access` +
`xpath-eval` or `expression-eval` + `template-render`), depending on what
readers downstream do with each. Producing only one is almost always a recall
miss.

## Output

The final assistant message must be a single ```json fenced block containing a
flat array of `SensitiveCapability` enum values — no surrounding prose, no object
wrapper.

```json
["shell-exec", "sql-query"]
```

Empty match → `[]`.

Each element must be one of:

```
code-eval, shell-exec, process-spawn, expression-eval, xpath-eval,
binary-deserialize, string-deserialize, xml-parse, template-render,
sql-query, nosql-query, file-read, file-write, file-rename, file-delete,
archive-extract, url-access, jndi-lookup, url-redirect, xslt-transform,
ldap-query, llm-invoke
```

Output schema (generated from `RootModel[list[SensitiveCapability]]`):

```
{"$defs": {"SensitiveCapability": {"enum": ["code-eval", "shell-exec", "process-spawn", "expression-eval", "xpath-eval", "binary-deserialize", "string-deserialize", "xml-parse", "template-render", "sql-query", "nosql-query", "file-read", "file-write", "file-rename", "file-delete", "archive-extract", "url-access", "jndi-lookup", "url-redirect", "xslt-transform", "ldap-query", "llm-invoke"], "type": "string"}}, "items": {"$ref": "#/$defs/SensitiveCapability"}}
```
