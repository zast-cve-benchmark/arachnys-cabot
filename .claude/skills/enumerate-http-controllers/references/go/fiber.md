# Fiber Endpoint Enumeration Reference

Fiber is a high-performance Go web framework with an Express-inspired API, built
on `fasthttp`. Routes are registered **imperatively** on a `*fiber.App` or on a
route group (`fiber.Router`) by ordinary method calls at startup. Routing is
**per-root, pre-composed by the main agent**: each top-level group binds a prefix
to a set of handlers, so the main agent composes L1 + the group prefix and hands
the whole segment down; the worker enumerates that group's handlers and resolves
each one's method + path.

---

## 1. Identify

- **Dependency** — `github.com/gofiber/fiber` in `go.mod` (commonly the `/v2` or
  `/v3` major-version path).
- **App creation marker** — `fiber.New()` builds the `*fiber.App`.
- **Route-registration markers** — verb calls on the app or a group:
  `app.Get(...)`, `app.Post(...)`, `app.Put(...)`, `app.Delete(...)`, etc.
- **Grouping marker** — `app.Group("/x")` declares a route group (a registration
  root).

---

## 2. Structural traversal — main agent

Walk the layers for Fiber, list the registration roots, and compose the prefix
prepended at registration. Stop there — do **not** read handlers (worker's job, §3).

- **L1 Deployment** — Fiber has no framework-level context-path config; the app
  mounts at `/` unless a reverse proxy / `app.Mount(prefix, subApp)` adds a base.
  Usually the L1 prefix is empty (`/`).
- **L3 Registration root** — each `app.Group("/x")` is a root: it binds a prefix to
  a set of handlers. Groups **nest and compose** (`api := app.Group("/api")`, then
  `admin := api.Group("/admin")` → `/api/admin`). A `*fiber.App` mounted under a
  prefix via `app.Mount(prefix, subApp)` (v2) / `app.Use(prefix, subApp)` (v3) is
  also a root, with the mount prefix. Routes registered directly on `app` (no
  group) form the root-level `/` root. Find the roots with:

  ```bash
  grep -rnE '\.Group\s*\(' --include='*.go' .
  ```

- **Prefix composition** — the prefix is per-root, so the **main agent
  pre-composes L1 + the (possibly nested) group prefix** and hands the whole
  segment to the worker. E.g. L1 `/` + `app.Group("/api/v1")` → `/api/v1`; a nested
  `api.Group("/admin")` under `app.Group("/api")` → `/api/admin`.

### Dispatch contract

- One worklist entry = one **top-level group** (or the root-level `/`
  registration block, or one mounted sub-app).
- Hand each worker: `framework=fiber`, `prefix=<pre-composed L1 + group prefix>`,
  `location=<group declaration site, file:line>`, `scope=<the handler files for
  that group>`.
- Split / merge: one entry per top-level group; compose nested group prefixes into
  that entry rather than splitting each nested group out. Do **not** over-split one
  group's handler list into many tiny scopes (each worker is one round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you).

### 3.1 Routed handlers — method, path, region

A **routed handler** is a verb call registering a handler on the app or group. The
route path is always the **first string argument**; trailing args are
middleware/handlers.

| Method | HTTP method |
|--------|-------------|
| `app.Get()` | GET |
| `app.Post()` | POST |
| `app.Put()` | PUT |
| `app.Delete()` | DELETE |
| `app.Patch()` | PATCH |
| `app.Options()` | OPTIONS |
| `app.Head()` | HEAD |
| `app.All()` | All methods → record method `"*"` |
| `app.Add(method, ...)` | the explicit method string passed first |
| `app.Use()` | normally middleware, not an endpoint (see below) |

```go
app := fiber.New()

app.Get("/users", listUsers)            // GET    /users
app.Post("/users", createUser)          // POST   /users
app.Get("/users/:id", getUser)          // GET    /users/:id
app.All("/webhook", handleWebhook)      // *      /webhook
app.Add("PURGE", "/cache", purgeCache)  // PURGE  /cache
```

> Note: Fiber v3 lowercases the method helpers' multi-handler form and adds
> `app.Get(path, handler, ...handlers)`. The route path is always the first string
> argument regardless of version.

**Enumeration rules:**
- Method = the verb in the call. `app.All(...)` → `"*"`; `app.Add("METHOD", ...)` →
  the explicit method string.
- Path = the first string argument; full endpoint = handed prefix + that route
  path.
- `region` = the registered handler's function body. Follow the handler argument
  (lambda body, or the named function / method behind a function value) and anchor
  on its body, not on the `.Get(...)` registration line.

### 3.2 Static / file-serving mounts (do NOT skip)

Fiber's static helper is an **endpoint** — reachable by GET, serves data from a
root directory, and is a frequent location for **path traversal** when the served
root is a relative path or attacker-controllable prefix.

```go
app.Static("/", "./public")
app.Static("/assets", "./public/assets")
app.Static("/data", "./datafiles", fiber.Static{Browse: true})

// v3: app.Get("/files/*", filesystem.New(filesystem.Config{...}))
```

Rules:
- `app.Static(prefix, root, ...)` → record one endpoint `GET <prefix>/*`, with the
  served `root` recorded as the file-path origin.
- `group.Static(prefix, root, ...)` composes with the group prefix.
- v3 `filesystem.New(...)` used as a handler is equivalent — its config's `Root`
  field is the served origin; record the mount path as a GET catch-all.

### 3.3 Path parameters — record as written

Record the path **as written** (the auditor matches on the registered template):

```go
app.Get("/users/:id", getUser)                  // named parameter
app.Get("/users/:userId/posts/:postId", h)      // multiple parameters
app.Get("/users/:id?", getUserOptional)         // optional (trailing ?)
app.Get("/files/+", serveFile)                   // + required-non-empty
app.Get("/assets/*", serveAsset)                 // * greedy wildcard
app.Get("/users/:id<int>", getUser)              // constrained <int>
app.Get("/articles/:slug<regex(\\w+)>", getArt)  // constrained <regex(...)>
```

Query parameters (`c.Query("name")`) are not part of the path — do not append them.

### 3.4 Middleware vs endpoint

```go
app.Use(logger.New())              // global middleware — not an endpoint
app.Use(cors.New())
app.Use("/api", authMiddleware)    // prefix-scoped middleware
app.Get("/protected", authMiddleware, protectedHandler)  // route middleware + handler
```

`app.Use(...)` with only a handler (or a path used as a catch-all) is normally
middleware, not an endpoint. `app.Use(path, handler)` *can* act as a catch-all
route — judge by whether the handler terminates the request or calls `c.Next()`.
On a verb call (`app.Get("/x", mw, handler)`), the trailing args before the final
handler are route middleware; the endpoint is still recorded once.

### 3.5 Handler signatures

```go
// Fiber handler — single error return
func getUsers(c *fiber.Ctx) error {
    id := c.Params("id")          // path parameter
    name := c.Query("name")       // query parameter
    var user User
    if err := c.BodyParser(&user); err != nil {   // request body
        return c.Status(fiber.StatusBadRequest).JSON(fiber.Map{"error": err.Error()})
    }
    return c.JSON(fiber.Map{"data": users})
}
```

The `region` anchors at this function's body.

### 3.6 Search patterns

```go
// AST — route registration
ast_grep_search(pattern='$APP.Get($PATH, $$$)', lang='go')
ast_grep_search(pattern='$APP.Post($PATH, $$$)', lang='go')
ast_grep_search(pattern='$APP.Put($PATH, $$$)', lang='go')
ast_grep_search(pattern='$APP.Delete($PATH, $$$)', lang='go')
ast_grep_search(pattern='$APP.All($PATH, $$$)', lang='go')
ast_grep_search(pattern='$APP.Add($METHOD, $PATH, $$$)', lang='go')
// Group creation / app creation
ast_grep_search(pattern='$VAR := $APP.Group($PATH)', lang='go')
ast_grep_search(pattern='fiber.New()', lang='go')
```

```regex
\.(Get|Post|Put|Delete|Patch|Head|Options|All|Add)\s*\(
\.Group\s*\(
\.Use\s*\(
\.Mount\s*\(
fiber\.New\s*\(
c\.Params\s*\(
c\.Query\s*\(
```

Key files to check: `main.go` (entry), `routes/` (route definitions),
`handlers/` / `controllers/` (handler logic), `api/` (API endpoints).

### 3.7 Enumeration checklist

- The route path is always the first string argument; trailing args are
  middleware/handlers.
- `app.All(...)` → method `"*"`; `app.Add("METHOD", ...)` → the explicit method.
- Each `Group(...)` is a registration root; compose parent prefixes (the main agent
  already pre-composed the prefix it handed you — prepend it to every route).
- `Mount` / `Use(prefix, subApp)` mounts a sub-app — its own root with the mount
  prefix.
- `app.Static(...)` / v3 `filesystem.New(...)` is a GET catch-all endpoint, not
  middleware — record it with the served root as the file-path origin.
- `app.Use(...)` is normally middleware, not an endpoint.
- `region` anchors at the handler function body, never the `.Get(...)`
  registration line.
- Record path parameters as written (`:id`, `:id?`, `*`, `+`, `:id<int>`).
