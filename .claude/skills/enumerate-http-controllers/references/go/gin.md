# Gin Endpoint Enumeration Reference

Gin is a high-performance Go web framework. Routes are registered imperatively on
a `gin.Engine` (the root) or a `gin.RouterGroup` by verb-method calls
(`.GET/.POST/...`). It is a **router-group framework**: each `router.Group("/x")`
binds a prefix to a set of handlers, and that prefix is a literal **known at the
registration call**. So routing here is **per-root, pre-composed by the main
agent** — the main agent composes L1 + the group prefix and hands the whole
segment down; the worker enumerates that group's handler list and appends each
route's own path. This is the Go analogue of Java's
[imperative-routing](../java/imperative-routing.md) per-root style.

---

## 1. Identify

- **Dependency** — `github.com/gin-gonic/gin` in `go.mod` / `go.sum`, or the
  import in source.
- **Engine construction** — `gin.Default()` or `gin.New()` (returns the
  `*gin.Engine` root).
- **Grouping / route markers** — `router.Group("/...")`, and verb registrations
  `.GET(...)` / `.POST(...)` / `.PUT(...)` / `.DELETE(...)` / etc.

---

## 2. Structural traversal — main agent

The main agent finds the engine, lists the top-level router groups (and the engine
root itself for routes registered directly on it), and composes the prefix each
group prepends at registration. It stops there — it does **not** read individual
handler bodies (that is the worker's job, §3).

- **L1 Deployment.** Gin usually has no base path — the engine mounts at `/`
  (`r.Run(":8080")` binds a port, not a path prefix). If a reverse proxy or an
  outer mux strips/prepends a prefix before Gin sees the request, that prefix is
  L1; otherwise L1 is empty.

- **L3 Registration root.** A root is **each top-level `router.Group("/x")`**, or
  the **engine root** for routes registered directly on `r` (no group). The
  group's prefix is the literal passed to `.Group(...)`. Find them with:

  ```bash
  # Top-level groups (the registration roots) and direct engine routes.
  grep -rnE '\.Group\s*\(' --include='*.go' .
  grep -rnE '\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Any|Match)\s*\(' --include='*.go' .

  # ast-grep equivalents
  # ast_grep_search(pattern='$VAR := r.Group($PATH)', lang='go')
  # ast_grep_search(pattern='r.GET($PATH, $HANDLER)', lang='go')
  ```

- **Prefix composition.** Gin's group prefix is per-root and known at the
  `.Group(...)` call, so the main agent **pre-composes L1 + the group's composed
  prefix** and hands the whole segment down (the per-route path stays the
  worker's). **Nested groups compose their prefixes**: a child
  `parent.Group("/users")` under `parent := r.Group("/admin")` contributes the
  prefix `/admin/users`. Example: L1 `` (empty) + group `/api/v1` → segment
  `/api/v1`; the worker then appends a route's `/users` → final `/api/v1/users`.

### Dispatch contract

- One worklist entry = **one top-level router group** (or the engine-root
  registration block, for routes hung directly off `r`).
- Hand each worker: `framework=gin`, `prefix=<L1 deployment + the group's composed
  prefix, pre-composed>` (e.g. `/api/v1`; the per-route path is the worker's),
  `location=<file:line of the `.Group(...)` call or the engine-root registration
  block>`, `scope=<the handler files / package that group's routes resolve to>`.
- Split / merge: one entry per top-level group. **Compose nested-group prefixes**
  into the parent's entry (a child group is part of its parent root, not its own
  worklist entry) — hand the parent worker the full nested handler list. Do NOT
  over-split one group's handler list into many tiny scopes (each worker is one
  round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope (a top-level group's prefix + its handler files),
enumerate every routed handler and compose the final endpoint (apply the prefix
the main agent handed you).

### 3.1 What counts as a routed handler

Every verb-method call on the engine or a group registers one endpoint:

| Call | HTTP Method | Notes |
|--------|-------------|-------------|
| `.GET()` | GET | Retrieve data |
| `.POST()` | POST | Create resource |
| `.PUT()` | PUT | Replace resource |
| `.DELETE()` | DELETE | Delete resource |
| `.PATCH()` | PATCH | Partial update |
| `.OPTIONS()` | OPTIONS | CORS preflight |
| `.HEAD()` | HEAD | Headers only |
| `.Any()` | All | Match all methods → record `"*"` |
| `.Match()` | Multiple | Match specified methods |

```go
func main() {
    r := gin.Default()

    // Routes directly on the engine root (no group).
    r.GET("/users", getUsers)
    r.POST("/users", createUser)
    r.GET("/users/:id", getUser)
    r.PUT("/users/:id", updateUser)
    r.DELETE("/users/:id", deleteUser)

    // A top-level group: prefix /api/v1, one worklist entry.
    v1 := r.Group("/api/v1")
    {
        v1.GET("/users", listUsersV1)        // GET  /api/v1/users
        v1.GET("/users/:id", getUserV1)      // GET  /api/v1/users/:id
        v1.POST("/users", createUserV1)      // POST /api/v1/users
    }

    // Group with middleware (middleware does not change the endpoint).
    v2 := r.Group("/api/v2", authMiddleware())
    {
        v2.GET("/users", listUsersV2)        // GET  /api/v2/users
    }

    r.Run(":8080")
}
```

**Method** = the verb in the call (`GET`/`POST`/`PUT`/`DELETE`/`PATCH`/`OPTIONS`/
`HEAD`); `.Any()` (or a verb-agnostic registration) → record method `"*"`;
`.Match([]string{...}, ...)` → one endpoint per listed method.

### 3.2 Path = group prefix + route path

The endpoint path is the prefix the main agent handed you (L1 + the composed
group prefix, nested groups already folded in) **plus** the literal path argument
of the verb call. Record the **already-composed** full path.

**Nested groups** compose further: a route on a child group carries
parent-prefix + child-prefix + route path.

```go
func main() {
    r := gin.Default()

    admin := r.Group("/admin", authMiddleware())   // root prefix /admin
    {
        admin.GET("/stats", getStats)               // GET  /admin/stats
        admin.POST("/config", updateConfig)         // POST /admin/config

        users := admin.Group("/users")              // nested: /admin/users
        {
            users.GET("", listAllUsers)             // GET  /admin/users
            users.DELETE("/:id", deleteUser)        // DELETE /admin/users/:id
        }
    }

    r.Run(":8080")
}
```

A nested group's empty route path (`users.GET("", ...)`) maps to the group prefix
itself (`/admin/users`).

### 3.3 Static / file-serving mounts (do NOT skip)

Gin's static helpers are **endpoints**. Each is reachable by an HTTP GET and serves
data, and is a frequent location for **path traversal** when the served root is a
relative path or attacker-controllable prefix.

```go
// Mount a directory at a URL prefix — every path under the prefix
// resolves to a file under the root.  Record as a GET catch-all.
r.Static("/assets", "./public")

// http.FileSystem variant — same shape.
r.StaticFS("/more", http.Dir("./public_extra"))

// Single-file binding — record as a GET at the exact path.
r.StaticFile("/favicon.ico", "./resources/favicon.ico")
r.StaticFileFS("/version", "VERSION", http.Dir("./meta"))
```

Enumeration rules:

- `r.Static(prefix, root)` / `r.StaticFS(prefix, fs)` → record one endpoint
  `GET <prefix>/*` with the served `root` / `fs` recorded as the file-path origin.
- `r.StaticFile(path, file)` / `r.StaticFileFS(path, file, fs)` → record
  `GET <path>`; the served target is `file`.
- `group.Static(...)` / `.StaticFS(...)` / `.StaticFile(...)` compose with the
  group prefix.

### 3.4 Path-parameter syntax

Record the path **as written** (the auditor matches on the registered template,
not a normalized form):

| Syntax | Example | Meaning |
|--------|---------|---------|
| `:name` | `/users/:id` | named segment — `c.Param("id")` |
| `:a/.../:b` | `/users/:userId/posts/:postId` | multiple named segments |
| `*name` | `/files/*filepath` | trailing wildcard — captures everything after the prefix (includes leading `/`), via `c.Param("filepath")` |

Query parameters (`c.Query("name")`, `c.DefaultQuery("page", "1")`) are read inside
the handler — they are **not** part of the path template and do not change the
endpoint.

### 3.5 `region` — anchor at the handler body

The `region` you record must point at **where the request is actually handled** —
the handler function's body — not at the `.GET(...)` registration line.

- **Inline closure** (`r.GET("/x", func(c *gin.Context) { ... })`) → the closure
  body is the handler and lives at the registration site; recording there is
  correct only because the body is there.
- **Named handler** (`r.GET("/x", getUsers)`) → open `getUsers` and record its
  function body span, not the `.GET(...)` line.

A standard handler has the signature `func(c *gin.Context)` and reads input via
`c.Param`, `c.Query`, `c.ShouldBindJSON`, etc.:

```go
func getUsers(c *gin.Context) {
    id := c.Param("id")                 // path parameter
    name := c.Query("name")             // query parameter
    var user User
    if err := c.ShouldBindJSON(&user); err != nil {   // request body
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    c.JSON(http.StatusOK, gin.H{"data": users})
}
```

Record `start_line` = the handler function's signature line, `end_line` = its
closing brace.

### 3.6 Framework quirks

- **Middleware is not an endpoint.** `r.Use(gin.Logger())`, group middleware
  (`r.Group("/api", authMiddleware())`), and per-route middleware
  (`r.GET("/protected", protectedHandler, authMiddleware())`) gate or decorate
  requests — they add no URL segment and are not separate endpoints. Only the
  verb-method registrations are endpoints; the **last** handler argument is the
  route handler, any earlier ones are middleware.
- **`.Any()` / verb-agnostic** registration → method `"*"`.
- **Empty route path on a group** (`group.GET("", ...)`) → the group prefix itself.

### 3.7 Key files to check

| Directory / file | Purpose |
|-----------|---------|
| `main.go` | Application entry — engine construction + top-level groups |
| `routes/` | Route definitions |
| `handlers/` | Handler functions |
| `controllers/` | Controller logic |
| `api/` | API endpoints |

Useful regexes inside a scope:

```regex
\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Any|Match)\s*\(
\.Group\s*\(
c\.Param\s*\(
c\.Query\s*\(
```
