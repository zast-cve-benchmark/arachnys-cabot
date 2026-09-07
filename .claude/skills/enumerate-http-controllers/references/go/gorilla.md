# gorilla/mux Endpoint Enumeration Reference

`gorilla/mux` is a Go HTTP request router and dispatcher. Routes are registered on
a `*mux.Router` (which implements `http.Handler`). Prefixes compose through
**subrouters**, and — unlike Gin/Echo — a route's HTTP method is **not** part of
the registration call; it is attached separately via a `.Methods(...)` matcher.

Routing here is **per-root, pre-composed by the main agent**: each subrouter binds
a `PathPrefix` to a handler list, so the main agent composes L1 + the `PathPrefix`
chain and hands the whole segment down; the worker enumerates that subrouter's
handlers and resolves each handler's method and path.

---

## 1. Identify

- **Dependency** — `github.com/gorilla/mux` in `go.mod` / the import block.
- **Router creation** — `mux.NewRouter()`.
- **Prefix root** — `r.PathPrefix("/x").Subrouter()`.
- **Method matcher** — a `.Methods("GET")` chained onto a registration.

---

## 2. Structural traversal — main agent

The main agent finds the router, lists the subrouters (the registration roots),
and composes the prefix each one applies. It stops there — it does **not** read
the individual handlers (that is the worker's job, §3).

- **L1 Deployment** — gorilla/mux has no framework base path of its own; it usually
  mounts at `/`. Any prefix comes from a reverse proxy / context-path in config, or
  from the `PathPrefix` chain below.
- **L3 Registration root** — each `r.PathPrefix("/x").Subrouter()` is a root: every
  route registered on that subrouter inherits its prefix. **Each `Subrouter()` is
  its own root.** The base router (`mux.NewRouter()`) is itself a root for any
  routes registered directly on it. Nested subrouters compose:
  `api := r.PathPrefix("/api").Subrouter()` then
  `admin := api.PathPrefix("/admin").Subrouter()` → `admin`'s prefix is `/api/admin`.

  The chained `.Methods(...)` matcher restricts a route to those methods — it does
  **not** create a root. Grep for the roots:

  ```bash
  grep -rnE '\.Subrouter\s*\(|\.PathPrefix\s*\(' --include='*.go' .
  grep -rnE 'mux\.NewRouter\s*\(' --include='*.go' .
  ```

- **Prefix composition — MAIN PRE-COMPOSES L1 + PathPrefix.** Read each
  `PathPrefix` chain leading to a subrouter, compose it (nested prefixes
  concatenate), prepend any L1 deployment prefix, and hand the **already-composed**
  whole segment to the worker:

  ```go
  api := r.PathPrefix("/api/v1").Subrouter()   // prefix handed to worker = L1 + "/api/v1"
  admin := api.PathPrefix("/admin").Subrouter() // prefix handed to worker = L1 + "/api/admin"
  ```

### Dispatch contract

- One worklist entry = one `Subrouter()` (or the base router for routes registered
  directly on `mux.NewRouter()`).
- Hand each worker: `framework=gorilla`,
  `prefix=<pre-composed L1 deployment + the PathPrefix chain leading to this
  subrouter>` (e.g. `/api/v1`), `location=<file:line of the `Subrouter()` call>`,
  `scope=<the handler files registered on that subrouter>`.
- Split / merge: one entry per subrouter; compose nested `PathPrefix`es into the
  child subrouter's prefix rather than emitting a separate entry per level. Do NOT
  over-split one subrouter's handler list into many tiny scopes.

---

## 3. Handler enumeration — worker

Given one subrouter's scope and the prefix the main agent handed you, enumerate
every routed handler and compose the final endpoint (apply the prefix!).

### Routed handler — what to record

| Function | Description |
|----------|-------------|
| `r.HandleFunc(path, handlerFunc)` | Register a path with an `http.HandlerFunc` |
| `r.Handle(path, handler)` | Register a path with an `http.Handler` |
| `r.Path(path)` | Build a route, path only — chain matchers/handler after |
| `r.PathPrefix(prefix)` | Match all paths starting with `prefix` |
| `r.NewRoute()` | Empty route configured entirely via chained matchers |

Registration alone records *all* HTTP methods; the actual method is set by chaining
`.Methods(...)`.

```go
func main() {
    r := mux.NewRouter()

    // Method attached via .Methods() — endpoint = "/users", method = "GET"
    r.HandleFunc("/users", listUsers).Methods("GET")
    r.HandleFunc("/users", createUser).Methods("POST")
    r.HandleFunc("/users/{id}", getUser).Methods("GET")
    r.HandleFunc("/users/{id}", updateUser).Methods("PUT", "PATCH") // comma-separated -> "PUT,PATCH"
    r.HandleFunc("/users/{id}", deleteUser).Methods("DELETE")

    // No .Methods() -> matches ALL methods -> record method as "*"
    r.HandleFunc("/health", healthCheck)

    // Path() builder form, handler attached last
    r.Path("/search").HandlerFunc(searchHandler).Methods("GET")

    http.ListenAndServe(":8080", r)
}
```

### Custom registration wrappers — trace the helper, enumerate its call sites

Large projects rarely call `r.HandleFunc` directly at every route. They wrap it in
a **project-local helper** and register routes through that — a `routes.go` /
route-table full of calls like `addRoute(r, "users/{id}", []string{"PUT"}, handler)`
with **few or no** direct `r.HandleFunc` in sight. If you only grep for `HandleFunc`
you will record a handful of routes and silently miss the whole table.

When the scope's registrations don't look like the direct forms above, find the
wrapper and follow it:

1. **Confirm it registers a route.** Open the helper definition; a registration
   wrapper bottoms out in a `r.HandleFunc` / `r.Handle` / `r.Path(...).Handler(...)`
   call (possibly via `.Methods(...)`). Identify which parameter is the **path**,
   which is the **method(s)**, and which is the **handler**.

   ```go
   // helper definition — bottoms out in HandleFunc, so each call site is a route
   func addRoute(r *mux.Router, path string, methods []string, h http.HandlerFunc) {
       r.HandleFunc("/api/"+path, h).Methods(methods...)   // note the "/api/" mount prefix
   }
   ```

2. **Enumerate every call site as a routed handler.** The path argument is the
   route (compose any prefix the helper hard-codes, like the `"/api/"` above, plus
   the worklist prefix), the methods argument is the method list, the handler
   argument's func is the `region`.

   ```go
   addRoute(r, "search",            []string{"POST"},      document.SearchDocuments) // -> POST   /api/search
   addRoute(r, "category/{id}/perm", []string{"GET","PUT"}, perm.CategoryPerms)       // -> GET,PUT /api/category/{id}/perm
   ```

This generalizes to any custom abstraction over the router (`AddPrivate`/`AddPublic`,
`register(...)`, a `[]Route{{path, method, handler}}` slice iterated in a loop).
The rule: **if a project routes through its own helper, enumerate the helper's call
sites, not just direct `HandleFunc`.** A route table iterated in a loop is the same
idea — each table entry is one routed handler.

### Method — from `.Methods(...)`, else `"*"`

The handler's `method` field is whatever is passed to `.Methods(...)`:

- `.Methods("GET")` → `"GET"`
- `.Methods("GET", "POST")` → `"GET,POST"` (comma-separated)
- no `.Methods()` call → `"*"` (matches every HTTP method)

`.Methods(...)` may appear before or after the handler in the chain — both
`r.HandleFunc(p, h).Methods("GET")` and `r.Methods("GET").Path(p).HandlerFunc(h)`
are valid. Match on the whole chained statement, not just the `HandleFunc` call.

### Path — prefix + route

The endpoint path is the prefix the main agent handed you (the composed
`PathPrefix` chain + L1) concatenated with the route's own path argument.

```go
api := r.PathPrefix("/api/v1").Subrouter()           // prefix handed to worker = "/api/v1"
api.HandleFunc("/users", listUsers).Methods("GET")    // -> /api/v1/users
api.HandleFunc("/users/{id}", getUser).Methods("GET") // -> /api/v1/users/{id}
```

**Path parameters — record as written** (the auditor matches the registered
template):

```go
r.HandleFunc("/users/{id}", getUser).Methods("GET")                  // single variable
r.HandleFunc("/users/{userId}/posts/{postId}", getPost).Methods("GET") // multiple
r.HandleFunc("/users/{id:[0-9]+}", getUser).Methods("GET")           // regex constraint after colon
r.HandleFunc("/articles/{category}/{slug:[a-z-]+}", getArticle).Methods("GET")
r.HandleFunc("/files/{path:.*}", serveFile).Methods("GET")           // {name:.*} catch-all, incl. slashes
```

Inside the handler, variables are read with `mux.Vars(r)`.

**Catch-all (not a prefix root).** A `PathPrefix(...).Handler(...)` /
`.HandlerFunc(...)` *without* `.Subrouter()` is itself an endpoint — a catch-all
matching `prefix + anything`. Record it with endpoint = the prefix (or
`prefix + "*"`):

```go
r.PathPrefix("/static/").Handler(http.FileServer(http.Dir("./static")))
```

**Not endpoints — matchers / middleware.** Do not record these on their own:

```go
r.Host("api.example.com").HandleFunc("/users", listUsers).Methods("GET") // Host: ignore for path
r.HandleFunc("/articles", listArticles).Queries("category", "{category}").Methods("GET") // Queries: matcher
r.Use(loggingMiddleware)                                                  // Use: middleware, not a route
```

`.Use(...)`, `.Host(...)`, `.Queries(...)` are matchers/middleware — never
endpoints on their own. Host does not affect the URL path.

### `region` — at the handler func

Handlers are standard `net/http` handlers; mux adds no special signature. Anchor
the `region` at the handler function's body (where the request is processed), not
at the registration line:

```go
// http.HandlerFunc form (most common)
func getUsers(w http.ResponseWriter, r *http.Request) {
    vars := mux.Vars(r)        // path variables
    q := r.URL.Query()         // query parameters
    // ... decode r.Body, write to w
}

// http.Handler interface form — region at the ServeHTTP method body
type UserHandler struct{}
func (h UserHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) { ... }
r.Handle("/users", UserHandler{}).Methods("GET")
```

### AST / regex search patterns

```go
// Route registration
ast_grep_search(pattern='$R.HandleFunc($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='$R.Handle($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='$R.Path($PATH)', lang='go')

// Subrouter (prefix root)
ast_grep_search(pattern='$R.PathPrefix($PREFIX).Subrouter()', lang='go')

// Router creation
ast_grep_search(pattern='mux.NewRouter()', lang='go')
```

```regex
\.(HandleFunc|Handle)\s*\(
\.PathPrefix\s*\(
\.Subrouter\s*\(
\.Methods\s*\(
mux\.NewRouter\s*\(
mux\.Vars\s*\(
```

**If these direct-form greps return far fewer routes than the project clearly has**
(a big `routes.go`/route table but only a handful of `HandleFunc` hits), the project
registers through a custom wrapper — find it (it bottoms out in `HandleFunc`) and
enumerate its call sites instead (see "Custom registration wrappers" above). Grep the
wrapper name once you know it (e.g. `\bAddRoute\s*\(`), or the route-table literal.

Files to check: `main.go` (entry, router setup), `routes/` (route definitions),
`handlers/` / `controllers/` (handler functions), `api/` (API endpoints).

### Enumeration checklist

- A route's method comes from `.Methods(...)`, **not** the registration call. No
  `.Methods()` → `"*"`; `.Methods("A", "B")` → comma-separated `"A,B"`.
- Compose the prefix the main agent handed you (L1 + `PathPrefix` chain) onto every
  route's path argument.
- `PathPrefix(...).Handler(...)` *without* `.Subrouter()` is a catch-all endpoint,
  not a prefix root.
- `.Use(...)`, `.Host(...)`, `.Queries(...)` are matchers/middleware — never
  endpoints on their own.
- Record the path **as written** (`{id}`, `{id:[0-9]+}`, `{path:.*}`) — do not
  normalize.
- `region` at the handler func body, never the registration line.
