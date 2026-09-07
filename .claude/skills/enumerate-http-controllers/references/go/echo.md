# Echo Endpoint Enumeration Reference

Echo is a high-performance Go web framework. Routes are registered on the
`echo.Echo` instance or on an `echo.Group`. Echo is a **router-group framework**:
a group binds a prefix to a set of handlers, and groups nest/compose. The prefix
is therefore **per-root** — the main agent pre-composes **L1 + group prefix** and
hands the whole segment to the worker, which enumerates that group's handlers.

---

## 1. Identify

How to confirm Echo is in use — one grep-able signal each:

- **Dependency** — `github.com/labstack/echo` in `go.mod` / imports
  (e.g. `github.com/labstack/echo/v5`).
- **Instance construction** — `echo.New()` builds the `echo.Echo` root.
- **Route / group registration** — `e.GET(...)` / `e.POST(...)` (and the other
  verb methods) register handlers; `e.Group("/x")` opens a router group.

---

## 2. Structural traversal — main agent

The main agent finds the echo instance and its groups, composes each group's full
prefix (L1 + group prefix), and dispatches one worker per top-level group. It does
**not** read handler bodies (that is the worker's job, §3).

**L1 Deployment.** Echo has no framework-level base path of its own — it usually
mounts at `/`. The only L1 segment is whatever the deployment puts in front (a
reverse-proxy prefix); absent that, L1 is `/`.

**L3 Registration root.** A root is either:
- each **router group** `g := e.Group("/x")` — the group's prefix `/x` binds the
  handlers registered on `g`; or
- the **echo instance root** itself, for handlers registered directly on `e`
  (e.g. `e.GET("/users", ...)`) with no group — its prefix is just L1.

Groups **nest and compose**: `admin := e.Group("/admin")` then
`users := admin.Group("/users")` yields prefix `/admin/users` for handlers on
`users`.

**The same variable name often holds several different groups.** A registration
function commonly opens an authenticated group, registers its routes, then opens a
**second group on the same variable** for the public/unauthenticated surface:

```go
g := e.Group("", authMiddleware)   // authenticated API group
g.GET("/api/private/x", ...)
// ... later in the same function ...
g = e.Group("")                    // PUBLIC group — same var, no auth, different routes
g.GET("/", ...); g.GET("/public/static/*", ...); g.GET("/subscription/:id", ...)
```

Each `:=` **or** `=` to `.Group(...)` is a **separate registration root**, even when
the variable name is identical and the prefix is `""`. Scan the WHOLE function for
**every** assignment to `.Group(...)`; stopping at the first silently drops the
re-assigned group's entire route set — often the public surface. Find the roots by
grepping for the instance, **all** group assignments (`:=` and `=`), and the
registrations:

```bash
grep -rnE 'echo\.New\(\)|:?= *\w+\.Group\(|\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|Any|Match|Static|StaticFS|File|FileFS)\s*\(' --include='*.go' .
```

```go
// ast-grep equivalents
ast_grep_search(pattern='$VAR := e.Group($PATH)', lang='go')
ast_grep_search(pattern='e.GET($PATH, $HANDLER)', lang='go')
```

**Prefix composition.** Echo is a router-group framework, so the main agent
**pre-composes L1 + the group prefix** and hands the whole segment down. Compose
nested group prefixes before handing them off:

```
L1 "/"  +  group "/api/v1"                  -> prefix "/api/v1"
L1 "/"  +  group "/admin" + nested "/users" -> prefix "/admin/users"
```

The worker then appends only each handler's own route path to this prefix.

### Dispatch contract

- One worklist entry = **one top-level group / registration block** (an
  `e.Group("/x")` and everything registered on it, including its nested
  sub-groups; or the echo-instance root for ungrouped handlers).
- Hand each worker: `framework=echo`,
  `prefix=<pre-composed L1 + group prefix>` (nested prefixes already composed),
  `location=<the group/registration declaration site, file:line>`,
  `scope=<the handler files for that group>`.
- Split / merge: one entry per **top-level** group; compose nested group prefixes
  into the parent's worker rather than splitting each nested group into its own
  entry. Do **not** over-split one group's handler list into many tiny scopes
  (each worker is one round-trip).

---

## 3. Handler enumeration — worker

Given one group's scope and its pre-composed prefix, enumerate every routed
handler and compose the final endpoint: **path = prefix + the handler's route
path**, **method = the registration verb**, **region = the handler function body**.

### 3.1 Route-registration methods

| Method | HTTP Method | Description |
|--------|-------------|-------------|
| `e.GET()` | GET | Retrieve data |
| `e.POST()` | POST | Create resource |
| `e.PUT()` | PUT | Replace resource |
| `e.DELETE()` | DELETE | Delete resource |
| `e.PATCH()` | PATCH | Partial update |
| `e.OPTIONS()` | OPTIONS | CORS preflight |
| `e.HEAD()` | HEAD | Headers only |
| `e.Match()` | Multiple | Match specified methods |
| `e.Any()` | All | Match all methods |
| `e.Static()` | GET | Mount a directory as a catch-all file-serving endpoint |
| `e.StaticFS()` | GET | Mount an `fs.FS` as a catch-all file-serving endpoint |
| `e.File()` | GET | Bind a single path to a single file on disk |
| `e.FileFS()` | GET | Bind a single path to a file inside an `fs.FS` |

**Enumeration rule:** the method is the verb in the call
(`GET`/`POST`/`PUT`/`DELETE`/`PATCH`/`OPTIONS`/`HEAD`); `e.Match([]string{...}, ...)`
records the listed methods; `e.Any(...)` records method `"*"` (all). The path is
the literal route argument; the final endpoint path is `prefix + route`.

```go
package main

import (
    "net/http"
    "github.com/labstack/echo/v5"
)

func main() {
    e := echo.New()

    // Basic routes
    e.GET("/users", getUsers)
    e.POST("/users", createUser)
    e.GET("/users/:id", getUser)
    e.PUT("/users/:id", updateUser)
    e.DELETE("/users/:id", deleteUser)

    // Match multiple methods
    e.Match([]string{"GET", "POST"}, "/api/data", handleData)

    // Match all methods
    e.Any("/webhook", handleWebhook)

    e.Start(":8080")
}
```

### 3.2 Routes registered on a group

Handlers registered on a group inherit that group's (already-composed) prefix; the
worker appends only the route argument. Nested groups compose:

```go
// API v1 group  -> prefix /api/v1
v1 := e.Group("/api/v1")
v1.GET("/users", listUsersV1)        // GET  /api/v1/users
v1.GET("/users/:id", getUserV1)      // GET  /api/v1/users/:id

// Group with middleware (middleware does not change the path)
v2 := e.Group("/api/v2", middleware.RequestLogger())
v2.GET("/users", listUsersV2)        // GET  /api/v2/users

// Nested group  -> prefix /admin/users
admin := e.Group("/admin", authMiddleware)
admin.GET("/stats", getStats)        // GET  /admin/stats
admin.POST("/config", updateConfig)  // POST /admin/config
users := admin.Group("/users")
users.GET("", listAllUsers)          // GET  /admin/users
users.DELETE("/:id", deleteUser)     // DELETE /admin/users/:id
```

### 3.3 Static / file-serving mounts (do NOT skip)

Echo's static and file helpers are **endpoints** even though they look like
configuration. Each one is reachable by an HTTP GET and serves data — they must be
enumerated and audited like any other handler. The common class of bug here is
**path traversal** when the served root is a relative path or attacker-controllable
prefix.

```go
// Mount the "./frontend" directory at "/" — every path on the server
// resolves to a file under "./frontend".  Record as a GET catch-all.
e.Static("/", "./frontend")

// Mount under a prefix.
e.Static("/assets", "./public")

// fs.FS variant — same shape.
e.StaticFS("/", echo.MustSubFS(content, "frontend"))

// Single-file binding — record as a GET at the exact path.
e.File("/favicon.ico", "images/favicon.ico")
e.FileFS("/version", "VERSION", echo.MustSubFS(content, ""))
```

Enumeration rules:

- `e.Static(prefix, root)` → record one endpoint `GET <prefix>` with the
  remainder of the path treated as a wildcard (e.g. `GET /` if prefix is
  `/`; `GET /assets/*` if prefix is `/assets`). The "handler" is the
  framework's static-file server; the served root (`root` argument) is the
  file_path the auditor needs to know.
- `e.StaticFS(prefix, fs)` → same as above, with `root` replaced by the
  `fs.FS` identity (note its source).
- `e.File(path, file)` → record `GET <path>`; the served target is `file`.
- `e.FileFS(path, file, fs)` → record `GET <path>`; the served target is
  `file` within `fs`.

`e.Group(prefix).Static(...)` / `.File(...)` follow the same rules with the group
prefix composed in.

### 3.4 Path parameters — record as written

Record the path **as written** (the auditor matches on the registered template):

- **Named** — `e.GET("/users/:id", ...)`; multiple, e.g.
  `/users/:userId/posts/:postId`.
- **Wildcard** — `e.GET("/files/*", ...)` captures everything after the prefix
  (`c.Param("*")`).
- **Query parameters** (`c.QueryParam("name")`, `c.QueryParamDefault("page", "1")`)
  are read inside the handler — they do not change the route path.

Echo v5 also offers type-safe extraction (`echo.PathParam[int](c, "id")`, struct
binding via `echo.BindPathValues`), but the **route template** is unchanged — record
the `:name` / `*` form from the registration call.

```go
// Single / multiple named parameters
e.GET("/users/:id", handler)
e.GET("/users/:userId/posts/:postId", handler)

// Wildcard captures everything after the prefix
e.GET("/files/*", handler)   // c.Param("*") == "images/logo.png"
```

### 3.5 Handler signatures and `region`

The `region` you record must point at the **handler function body** — where the
request is actually processed — not the registration call line. Follow the handler
passed to the route:

- **Inline lambda** (`e.GET("/x", func(c *echo.Context) error { ... })`) → the
  function literal body is at the registration site; record there.
- **Named handler / method-reference** (`e.GET("/users", getUsers)`) → open the
  `getUsers` function and record its body, not the `e.GET(...)` line.

Echo v5 handler signature (`Context` is a pointer):

```go
func getUsers(c *echo.Context) error {
    id := c.Param("id")           // path parameter
    name := c.QueryParam("name")  // query parameter

    var user User
    if err := c.Bind(&user); err != nil {  // request body
        return err
    }
    return c.JSON(http.StatusOK, map[string]interface{}{"data": users})
}
```

### 3.6 Middleware (not endpoints)

Middleware registrations are **not** endpoints — do not record them. They are noted
only so you don't mistake them for handlers:

- **Global** — `e.Pre(...)` (before routing), `e.Use(...)` (after routing).
- **Group** — `e.Group("/api", middleware.RequestID())`.
- **Route-level** — extra args after the handler:
  `e.GET("/protected", protectedHandler, authMiddleware())`.

A custom middleware has the `func(next echo.HandlerFunc) echo.HandlerFunc` shape; a
handler has the `func(c *echo.Context) error` shape — only the latter is an endpoint.

### 3.7 Locating handlers — search patterns

```go
// Route registration
ast_grep_search(pattern='e.GET($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='e.POST($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='e.PUT($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='e.DELETE($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='e.Any($PATH, $HANDLER)', lang='go')
ast_grep_search(pattern='e.Match($METHODS, $PATH, $HANDLER)', lang='go')

// Static / file mounts (record each as a GET endpoint)
ast_grep_search(pattern='e.Static($PREFIX, $ROOT)', lang='go')
ast_grep_search(pattern='e.StaticFS($PREFIX, $FS)', lang='go')
ast_grep_search(pattern='e.File($PATH, $FILE)', lang='go')
ast_grep_search(pattern='e.FileFS($PATH, $FILE, $FS)', lang='go')

// Group creation (a registration root)
ast_grep_search(pattern='$VAR := e.Group($PATH)', lang='go')

// Middleware (NOT endpoints)
ast_grep_search(pattern='e.Use($MIDDLEWARE)', lang='go')
ast_grep_search(pattern='e.Pre($MIDDLEWARE)', lang='go')
```

```regex
\.(GET|POST|PUT|DELETE|PATCH|Any|Match)\s*\(
\.(Static|StaticFS|File|FileFS)\s*\(
\.Group\s*\(
\.Use\s*\(
\.Pre\s*\(
c\.Param\s*\(
c\.QueryParam\s*\(
```

Key files to check:

| Directory | Purpose |
|-----------|---------|
| `main.go` | Application entry |
| `routes/` | Route definitions |
| `handlers/` | Handler functions |
| `controllers/` | Controller logic |
| `api/` | API endpoints |
