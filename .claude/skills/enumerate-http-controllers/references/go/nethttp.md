# Go net/http (Standard Library) Endpoint Enumeration Reference

Many Go services use **no web framework at all** — routing is the standard
library's `net/http`. Routes are registered imperatively on an `*http.ServeMux`
(or the package-level `DefaultServeMux`) by ordinary method calls at startup. A
grep for framework annotations/imports finds **nothing**, but these projects
absolutely still serve HTTP endpoints. This is the Go analogue of Java's
[imperative-routing](../java/imperative-routing.md) reference.

Routing here is **per-root, pre-composed by the main agent**: each `ServeMux` is a
registration root binding a prefix to a handler list, so the main agent composes
L1 + any `StripPrefix` mount segment and hands the whole prefix down; the worker
enumerates that mux's handlers and resolves each handler's path from where it
actually lives.

There are two eras of the standard router, and the worker must handle both:

- **Go ≤ 1.21** — `ServeMux` patterns are path/prefix only. **No method matching**:
  a single registration handles *all* HTTP methods; the method is branched inside
  the handler with `if r.Method == ...`.
- **Go ≥ 1.22** — patterns may carry a **method and host**: `"GET /users/{id}"`.
  Wildcards `{name}` and `{name...}` are supported natively.

---

## 1. Identify

No web framework is in use — routing is stdlib `net/http`. A dependency/import
grep for `gin`/`echo`/`chi`/etc. finds nothing; the signal is the stdlib mux
markers instead:

- **Mux construction** — `http.NewServeMux()`, the `http.ServeMux` type, or the
  package-level `DefaultServeMux`.
- **Route registration** — `mux.Handle(...)` / `mux.HandleFunc(...)`, or the
  package-level `http.Handle(...)` / `http.HandleFunc(...)`.
- **Prefix mounting** — `http.StripPrefix(...)`.

```regex
http\.NewServeMux\s*\(
\.(HandleFunc|Handle)\s*\(
http\.(HandleFunc|Handle)\s*\(
http\.StripPrefix\s*\(
```

---

## 2. Structural traversal — main agent

The main agent finds where the process builds its mux(es), lists the registration
roots, and composes the prefix prepended at registration. It stops there — it does
**not** read handler bodies or branch logic (that is the worker's job, §3).

**L1 Deployment.** The standard library has no group/context-path primitive, so
there is usually **no L1 prefix — the mux mounts at `/`**. The only base path comes
from `StripPrefix` mounts (below) or a manual prefix constant resolved at the
handler.

**L3 Registration root = each `ServeMux`.** Each `http.NewServeMux()` (and the
`DefaultServeMux` when package-level `http.Handle`/`http.HandleFunc` are used) is
one root binding a set of patterns to handlers. Find them — and the mounts that
compose prefixes — with:

```regex
http\.NewServeMux\s*\(
http\.StripPrefix\s*\(
\.(HandleFunc|Handle)\s*\(
```

Key files to sweep: `main.go` (entry, mux setup), `routes/` / `router/` (route
registration), `server/` (mux construction), `api/` and `handlers/`.

**Prefix composition — sub-mux mounting.** The cross-file case is a sub-mux
mounted under another with `StripPrefix`:

```go
apiMux := http.NewServeMux()
apiMux.HandleFunc("GET /users", listUsers)
apiMux.HandleFunc("GET /orders", listOrders)

root := http.NewServeMux()
// Everything under apiMux is reachable under "/api/" — compose the prefix.
root.Handle("/api/", http.StripPrefix("/api", apiMux))
```

`mux.Handle("/x/", http.StripPrefix("/x", subMux))` mounts `subMux` under `/x`.
**Each sub-mux is its own registration root**; the `/x` mount prefix composes onto
every one of its patterns. **The main agent pre-composes L1 + every StripPrefix
mount segment in the chain** (mounts can nest: a sub-mux mounted under `/x` whose
own sub-mux is mounted under `/y` contributes `/x/y`) and hands the whole segment
down. A FileServer mount (`mux.Handle("/static/", http.StripPrefix("/static/",
http.FileServer(http.Dir("./public"))))`) is a real GET endpoint — record it; the
root is the served origin.

### Dispatch contract

- One worklist entry = one `ServeMux` (the root mux, and each sub-mux mounted via
  `StripPrefix`).
- Hand each worker: `framework=nethttp`,
  `prefix=<L1 deployment + the pre-composed StripPrefix mount prefixes for this mux>`
  (usually `/` for the root mux; the mount path, e.g. `/api`, for a sub-mux),
  `location=<file:line of the mux creation / its registration block>`,
  `scope=<the handler files this mux's registrations reference>`.
- Split / merge: one entry per mux / sub-mux; compose nested `StripPrefix` mounts
  into the prefix rather than splitting the chain. Do NOT over-split one mux's
  handler list into many tiny scopes (each worker is one round-trip; too many
  exhaust the message budget).

---

## 3. Handler enumeration — worker

Given one mux's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you). The standard library has
two pattern eras; **identify the era first** before reading methods.

### Routed-handler rule

A routed handler is any registration on the mux:

| Function | Description |
|----------|-------------|
| `mux.Handle(pattern, handler)` | Register an `http.Handler` on a mux |
| `mux.HandleFunc(pattern, handlerFunc)` | Register an `http.HandlerFunc` on a mux |
| `http.Handle(pattern, handler)` | Register on the package-level `DefaultServeMux` |
| `http.HandleFunc(pattern, handlerFunc)` | Same, with a function |

`http.HandleFunc` / `http.Handle` (package-level) register on `DefaultServeMux` —
still real endpoints. AST searches:

```go
ast_grep_search(pattern='$MUX.HandleFunc($PATTERN, $HANDLER)', lang='go')
ast_grep_search(pattern='$MUX.Handle($PATTERN, $HANDLER)', lang='go')
ast_grep_search(pattern='http.HandleFunc($PATTERN, $HANDLER)', lang='go')
ast_grep_search(pattern='http.Handle($PATTERN, $HANDLER)', lang='go')
```

A handler is anything satisfying `ServeHTTP(http.ResponseWriter, *http.Request)`:

```go
// http.HandlerFunc — the common form
func listUsers(w http.ResponseWriter, r *http.Request) {
    id := r.PathValue("id")             // Go >= 1.22 wildcard value
    q := r.URL.Query().Get("name")      // query parameter
    // ... decode r.Body, write to w
}

// http.Handler interface
type UsersHandler struct{}
func (h UsersHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) { ... }
mux.Handle("/users", UsersHandler{})
```

### Method — stdlib mux is method-agnostic unless the handler branches

**Go ≤ 1.21 (path-only patterns).** The pattern carries no method; one
registration receives **all** methods. Inspect the handler:

```go
mux.HandleFunc("/users", usersHandler)        // pattern is PATH ONLY

func usersHandler(w http.ResponseWriter, r *http.Request) {
    switch r.Method {                          // method branched INSIDE the handler
    case http.MethodGet:
        listUsers(w, r)
    case http.MethodPost:
        createUser(w, r)
    default:
        http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
    }
}
```

- If the handler branches on `r.Method` → record **one endpoint per branch** with
  the branched method.
- If it does not branch → record once with method `"*"`.

**Go ≥ 1.22 (method-in-pattern).** The method is the leading token of the pattern
(`"[METHOD ][HOST]/PATH"`):

```go
mux.HandleFunc("GET /users", listUsers)        // method = GET
mux.HandleFunc("POST /users", createUser)       // method = POST
mux.HandleFunc("GET /users/{id}", getUser)      // wildcard segment
mux.HandleFunc("/health", healthCheck)          // no method token -> "*"
```

The method is the leading token; **no leading method token → `"*"`**. The path is
the remainder (strip an optional host before the first `/`).

### Path = mount prefix + pattern

Compose the prefix the main agent handed you onto every pattern from this mux, and
record the **already-composed** full path. Beyond the mount prefix, the pattern
itself has stdlib semantics:

**Trailing slash = subtree (prefix) match.**

```go
mux.HandleFunc("/api/", apiHandler)     // matches /api/, /api/anything, /api/x/y ...
mux.HandleFunc("/api", exactHandler)    // matches ONLY /api exactly
```

A pattern ending in `/` is a catch-all under that prefix — record the endpoint as
the pattern path.

**Wildcards (Go ≥ 1.22).** Record the path **as written** — do not normalize:

```go
mux.HandleFunc("GET /users/{id}", getUser)           // single segment
mux.HandleFunc("GET /files/{path...}", serveFile)    // {name...} = multi-segment trailing wildcard
mux.HandleFunc("GET /items/{id}/", subtreeHandler)   // {$} or trailing / semantics
```

Read wildcard values inside the handler with `r.PathValue("id")`.

**Host in pattern.** The host prefix does not affect the URL path — record only the
path portion:

```go
mux.HandleFunc("api.example.com/users", listUsers)   // host-qualified; path is "/users"
```

**Manual prefix strings.** When patterns are built by string concatenation, resolve
the constant to compose the full endpoint:

```go
const apiV1 = "/api/v1"
mux.HandleFunc("GET "+apiV1+"/users", listUsers)     // resolve apiV1 -> /api/v1/users
```

### `region` — anchor at the handler func body

Record the `region` at the **handler function's body**, not the registration line:

- **Inline `HandlerFunc`** (`func listUsers(w, r) { ... }`) → that function's body.
- **`http.Handler` type** (`mux.Handle("/users", UsersHandler{})`) → the type's
  `ServeHTTP` method body.

Downstream auditing reads the source at `region` for vulnerabilities, so a region
on the `mux.HandleFunc(...)` registration line points the auditor at plumbing, not
logic.

### Enumeration checklist

- **No framework markers ≠ no endpoints.** Routing is stdlib `net/http` — work the
  mux the main agent handed you.
- **Identify the era first.** Method-in-pattern (`"GET /x"`) → Go ≥ 1.22.
  Path-only (`"/x"`) → must inspect the handler.
- Path-only pattern + `r.Method` switch/if → one endpoint per method branch.
- Path-only pattern + no method branching → one endpoint, method `"*"`.
- Method-in-pattern → method is the leading token; `"*"` if absent.
- Trailing `/` = subtree/prefix match — record as a catch-all under that path.
- `Handle("/p/", http.StripPrefix("/p", subMux))` composes prefix `/p` onto the
  sub-mux's patterns.
- `http.HandleFunc` / `http.Handle` (package-level) register on `DefaultServeMux` —
  still real endpoints.
- Compose the mount prefix the main agent handed you onto every path; record the
  path **as written** (`{id}`, `{path...}`, trailing `/`) — do not normalize.
- `region` = the handler func / `ServeHTTP` body, never the registration line.
