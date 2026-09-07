# chi Endpoint Enumeration Reference

`go-chi/chi` is a lightweight, idiomatic Go router built entirely on the standard
`net/http` interfaces. Routes are registered on a `chi.Router` (`chi.NewRouter()`
returns a `*chi.Mux`). chi's distinguishing feature is **`Route`/`Mount`/`Group`**
for composing sub-routers and prefixes.

Routing here is **per-root, pre-composed by the main agent**: each `Route`/`Mount`
subtree binds a prefix to a set of handlers, so the main agent composes the
deployment base + the `Route`/`Mount` prefix chain and hands the whole segment
down; the worker enumerates that subtree's handlers and resolves each handler's
path from the route literal at its call site.

---

## 1. Identify

- **Dependency** — `github.com/go-chi/chi` (often `/v5`) in `go.mod` /
  `import` blocks.
- **Router creation** — `chi.NewRouter()` (returns a `*chi.Mux`).
- **Composition markers** — `r.Route("/x", ...)`, `r.Mount("/x", sub)`,
  `r.Group(func(r chi.Router){ ... })`.

Any of these confirms chi is the router in use.

---

## 2. Structural traversal — main agent

The main agent finds the base router, lists the `Route`/`Mount` subtrees, and
composes the prefix prepended at registration. It stops there — it does **not**
read handler bodies (that is the worker's job, §3).

- **L1 Deployment** — chi mounts at `/` in most apps; there is usually no
  framework base path. A reverse-proxy prefix, if any, lives in deploy config,
  not the Go source.
- **L3 Registration root** — the base `chi.NewRouter()` and each `Route`/`Mount`
  subtree. **`r.Route("/x", fn)` and `r.Mount("/x", sub)` each ADD a prefix**;
  **`r.Group(fn)` does NOT add a prefix** — it scopes middleware only, and its
  routes keep the prefix of the enclosing `Route`/`Mount`. This `Route`/`Mount`-adds
  / `Group`-doesn't distinction is the chi gotcha; preserve it.

  Find the roots with:

  ```bash
  grep -rnE '\.(Route|Mount|Group)\s*\(' --include='*.go' .
  grep -rnE 'chi\.NewRouter\s*\(' --include='*.go' .
  ```

  ```go
  ast_grep_search(pattern='$R.Route($PATH, $FN)', lang='go')
  ast_grep_search(pattern='$R.Mount($PATH, $SUB)', lang='go')
  ```

- **Prefix composition — MAIN PRE-COMPOSES.** The main agent composes L1 + the
  `Route`/`Mount` prefix chain (composing nested ones) and hands the whole
  segment to the worker. `Mount` is the cross-file case: the sub-router is often
  built in another function or file, with the mount path as its composed prefix.

  ```go
  r := chi.NewRouter()
  r.Route("/api/v1", func(r chi.Router) {        // prefix "/api/v1"
      r.Route("/users/{id}", func(r chi.Router) {// nested -> "/api/v1/users/{id}"
          r.Get("/posts", getUserPosts)          // -> /api/v1/users/{id}/posts
      })
  })
  r.Mount("/users", userRouter())                // prefix "/users", sub-router is the scope

  r.Group(func(r chi.Router) {
      r.Use(AuthMiddleware)
      r.Get("/profile", profileHandler)          // -> /profile  (Group adds NO prefix)
  })
  ```

### Dispatch contract

- One worklist entry = one `Route`/`Mount` subtree (or the base router for
  routes registered directly on it).
- Hand each worker: `framework=chi`,
  `prefix=<pre-composed L1 deployment + the Route/Mount prefix chain>`,
  `location=<the Route/Mount call site or base-router decl, file:line>`,
  `scope=<the handler files for this subtree — for a Mount, the file(s) building
  the sub-router>`.
- Split / merge: one entry per `Route`/`Mount` (compose nested `Route`/`Mount`
  prefixes into the parent's segment). A `Group` adds no prefix, so its routes
  stay in their enclosing `Route`/`Mount` entry — do not give a `Group` its own
  entry. Do NOT over-split one subtree's handler list into many tiny scopes
  (each worker is one round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you): `path = prefix + the
route literal at the call site`, method from the verb in the call.

### Routed handlers — method from the verb

| Method | HTTP Method | Notes |
|--------|-------------|-------|
| `r.Get()` | GET | |
| `r.Post()` | POST | |
| `r.Put()` | PUT | |
| `r.Delete()` | DELETE | |
| `r.Patch()` | PATCH | |
| `r.Options()` | OPTIONS | CORS preflight |
| `r.Head()` | HEAD | |
| `r.Connect()` / `r.Trace()` | CONNECT / TRACE | Rare verbs |
| `r.HandleFunc()` | `"*"` | Matches all methods — record method `"*"` |
| `r.Method(method, path, h)` | the literal method string | Explicit verb, e.g. `"PURGE"` |
| `r.MethodFunc(method, path, h)` | the literal method string | Same, with `http.HandlerFunc` |

```go
r.Get("/users", listUsers)                     // GET    /users
r.Post("/users", createUser)                   // POST   /users
r.Get("/users/{id}", getUser)                  // GET    /users/{id}
r.HandleFunc("/health", healthCheck)           // *      /health
r.Method("PURGE", "/cache", purgeHandler)      // PURGE  /cache
```

**`r.With(mw).Get(path, h)` registers a real route** — record the route at
`path`; the `.With(...)` part is just middleware. `r.Use(...)` attaches global
middleware and is not itself a route.

```go
r.With(AuthMiddleware).Get("/protected", protectedHandler)   // endpoint = /protected
```

### Path syntax — record as written

| Syntax | Example |
|--------|---------|
| `{name}` | `/users/{id}` |
| `{name:regex}` | `/users/{id:[0-9]+}` (regex after the colon) |
| `*` / `/*` | `/files/*`, `/static/*` (trailing wildcard, `chi.URLParam(r, "*")`) |

Multiple parameters compose normally: `/users/{userID}/posts/{postID}`. Query
parameters use standard `net/http` access (`r.URL.Query().Get("name")`) and are
not part of the registered path.

**`r.Handle(prefix+"*", http.FileServer(http.Dir(root)))` (and the related
`http.StripPrefix(...)` wrap) is itself an endpoint** — do NOT skip these
because the handler "looks like a library call". Record one `GET <prefix>/*`
endpoint with `root` recorded as the served origin; these mounts are a classic
location for path-traversal CVEs when the root is a relative path or
attacker-controllable prefix.

```go
r.Get("/files/*", serveFile)
r.Handle("/static/*", http.FileServer(http.Dir("./public")))
```

### Handler signatures

chi handlers are plain `net/http` handlers — no special signature.

```go
func getUsers(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "id")
    // ... decode r.Body, write to w
}

r.Handle("/metrics", promhttp.Handler())       // http.Handler interface form
```

### `region` — anchor at the handler body

Record the `region` at the handler function's body, not the registration line.
For a named handler or method-reference (`r.Get("/x", getUser)`), open `getUser`
and span its `func` body. For an inline closure
(`r.Get("/x", func(w, r){ ... })`), the body is at the registration site, so
recording there is correct only because the body is there.

### Enumeration checklist

- `path = prefix + route literal`; method = the verb in the call.
- `HandleFunc` with no method → `"*"`; `Method("X", ...)` → explicit `"X"`.
- `r.With(mw).Get(path, h)` registers a real route at `path`.
- `r.Handle(prefix+"*", http.FileServer(...))` is an endpoint — record it.
- Record the path **as written** (`{id}`, `{id:[0-9]+}`, `*`) — do not normalize.
- `region` = the handler function's body span, never the registration line.
