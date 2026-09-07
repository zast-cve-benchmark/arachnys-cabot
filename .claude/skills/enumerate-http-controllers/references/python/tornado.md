# Tornado Endpoint Enumeration Reference

Tornado wires routes **imperatively**: an `Application` is built with a list of
url-spec tuples `(regex, HandlerClass)`, each binding a URL pattern to a
`RequestHandler` subclass; the HTTP verbs live as methods on the handler class.
Routing here is **per-root, pre-composed by the main agent**: the path lives at the
registration tuple (the regex), so the main agent reads the url-spec list,
pre-composes any prefix, and pairs each path with its handler class; the worker
opens each handler class for its HTTP-verb methods.

---

## 1. Identify

- **Dependency** — `tornado` in `requirements.txt` / `pyproject.toml` / imports
  (`import tornado.web`).
- **Application construction** — `tornado.web.Application([...])` built from a
  url-spec list.
- **Handler classes** — `class XxxHandler(tornado.web.RequestHandler)`.
- **Url-spec tuples** — `(r"/x", HandlerClass)` pairs in the application list, or the
  `URLSpec` / `url(r"/x", HandlerClass, ...)` form.

```regex
tornado\.web\.Application\s*\(\s*\[
class\s+\w+\(tornado\.web\.RequestHandler\)
url\s*\(
add_handlers\s*\(
```

---

## 2. Structural traversal — main agent

The main agent finds each `Application` url-spec list, composes the prefix, and
pairs each regex with its handler class. It stops there — it does **not** open the
handler classes for their verb methods (that is the worker's job, §3).

**L1 Deployment.** Tornado usually mounts at `/` — no framework base path. A
reverse-proxy prefix or an `add_handlers(host, [...])` host/mount can prepend a
segment; treat any such mount as the L1 prefix.

**L3 Registration root.** The root is the `Application(handlers=[(regex, HandlerClass), ...])`
url-spec list — each tuple binds a URL regex to a handler class. Sub-applications
and `app.add_handlers(host, [...])` registrations are additional roots. The PATH
lives at the registration tuple (the regex), so the main agent reads the url-spec
list, **pre-composes any prefix, and pairs each regex with its `HandlerClass`**; the
worker reads the handler class for its HTTP-verb methods.

```bash
# Application construction and its url-spec list (the registration root)
grep -rnE 'tornado\.web\.Application\s*\(' --include='*.py' .

# Handler classes the tuples reference
grep -rnE 'class\s+\w+\(.*RequestHandler\)' --include='*.py' .

# Dynamic / sub-application route registration (additional roots)
grep -rnE 'add_handlers\s*\(' --include='*.py' .
```

**Prefix composition.** Compose L1 (any reverse-proxy prefix or `add_handlers`
host/mount) with each tuple's regex. The regex *is* the L3 path; the main agent
pre-composes the L1 + mount segment and hands the whole prefix down.

### Dispatch contract
- One worklist entry = one `Application` url-spec list (or one `add_handlers`
  block).
- Hand each worker: `framework=tornado`,
  `prefix=<L1 deployment + any add_handlers mount segment>`,
  `location=<file:line of the Application(handlers=...) list>`,
  `scope=<the handler classes referenced in that url-spec list>`.
- Split / merge: one entry per `Application` / `add_handlers` block. Do NOT
  over-split one list's handler classes into many tiny scopes.

---

## 3. Handler enumeration — worker

Given one root's url-spec list, enumerate every endpoint and compose the final path
(apply the prefix the main agent handed you). For each `(regex, HandlerClass)`
tuple:

- **The path is the regex** — record it **as written**; capture groups are path
  parameters (the auditor matches on the registered template, not a normalized
  form).
- **Open the `HandlerClass`** and enumerate its HTTP-verb methods. Each verb method
  present is one endpoint at that path.
- **The `region`** for each endpoint is that verb method's body.

### 3.1 Url-spec forms

```python
import tornado.web

# Basic tuple pattern
app = tornado.web.Application([
    (r"/", MainHandler),
    (r"/users", UserListHandler),
    (r"/users/([0-9]+)", UserDetailHandler),
])

# URLSpec / url(...) pattern (with additional options)
from tornado.web import url
app = tornado.web.Application([
    url(
        r"/story/([0-9]+)",  # Regex pattern (the path)
        StoryHandler,         # Handler class
        dict(db=db),          # Initialization kwargs
        name="story"          # Named route
    )
])

# Dynamic route addition (an additional registration root)
def make_app():
    app = tornado.web.Application()
    app.add_handlers(r".*$", [
        (r"/api/(.*)", ApiHandler),
        (r"/admin/(.*)", AdminHandler),
    ])
    return app
```

### 3.2 HTTP-verb methods on the handler class

A `RequestHandler` subclass implements one method per HTTP verb it serves; **each
verb method present = one endpoint at that handler's path:**

| Verb method | Endpoint method |
|-------------|-----------------|
| `get()` | GET |
| `post()` | POST |
| `put()` | PUT |
| `delete()` | DELETE |
| `patch()` | PATCH |
| `head()` | HEAD |
| `options()` | OPTIONS |

```python
class UserHandler(tornado.web.RequestHandler):
    def get(self, user_id=None):     # GET  endpoint, region = this body
        if user_id:
            self.write({"user_id": user_id})
        else:
            self.write({"users": []})

    def post(self):                  # POST endpoint, region = this body
        name = self.get_argument("name")
        self.write({"created": name})

    def put(self, user_id):          # PUT  endpoint
        self.write({"updated": user_id})

    def delete(self, user_id):       # DELETE endpoint
        self.write({"deleted": user_id})
```

**Custom HTTP methods** — a handler may extend `SUPPORTED_METHODS` and add a
matching lowercase method; record it as one endpoint at that verb:

```python
class WebDAVHandler(tornado.web.RequestHandler):
    SUPPORTED_METHODS = tornado.web.RequestHandler.SUPPORTED_METHODS + ('PROPFIND',)

    def propfind(self):              # PROPFIND endpoint
        self.write("WebDAV PROPFIND response")
```

### 3.3 Path patterns and parameters

The path is the tuple's regex — record it exactly. Capture groups are path
parameters (positional or named), passed to the verb method as arguments.

```python
# Simple path
(r"/", MainHandler)

# Dynamic path - positional parameter -> get(self, user_id) (receives string)
(r"/user/([0-9]+)", UserHandler)

# Dynamic path - named parameter -> get(self, year, month)
(r"/article/(?P<year>[0-9]{4})/(?P<month>[0-9]{2})", ArticleHandler)

# Capture all paths
(r"/(.*)", FileHandler)
```

Path parameters also reach the verb method via `self.path_args` (positional list)
and `self.path_kwargs` (named dict). A `url(..., name="...")` is the same route plus
a name for `reverse_url`; the name does not change the endpoint.

### 3.4 Region — anchor at the verb method body

The `region` you record must point at the verb method's body (where the request is
handled), not at the registration tuple. `start_line` = the verb method's signature
line, `end_line` = its closing brace. Downstream auditing reads the source at
`region`, so a region on the `(regex, HandlerClass)` line points the auditor at
plumbing, not logic.

A handler may inherit verbs from a base class (`class ProtectedHandler(BaseHandler)`)
and add request-lifecycle hooks; record the region at the concrete verb method that
serves the request. Authentication often lives in `get_current_user()` /
`prepare()` / the `@tornado.web.authenticated` decorator on the verb method.

```python
class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

class ProtectedHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):                   # GET endpoint, region = this body
        self.write("Protected content")
```

### 3.5 Input handling (for the downstream auditor)

The verb method body reads request input through these accessors — note them where
they feed a sink:

```python
def get(self):
    name = self.get_argument("name")          # single query/body param
    names = self.get_arguments("names")        # multiple values
    q = self.get_query_argument("q")           # query-only

def post(self):
    body_param = self.get_body_argument("body")   # form body
    if self.request.headers.get("Content-Type") == "application/json":
        import json
        data = json.loads(self.request.body)       # raw JSON body
```

Async handlers (`async def get(self): ... await ...`) are enumerated identically —
the verb name still decides the HTTP method.

### 3.6 Handler lifecycle methods (auditor context, not endpoints)

These are not endpoints, but they gate or shape every verb method on the handler —
note them for the auditor:

| Method | Purpose | Security focus |
|--------|---------|----------------|
| `initialize()` | Receive Application kwargs | Resource initialization |
| `prepare()` | Pre-request (all methods) | Authentication / authorization |
| `on_finish()` | Post-request cleanup | Resource cleanup |
| `write_error()` | Error page rendering | Info-leak prevention |
| `get_current_user()` | User authentication | Auth logic |
| `set_default_headers()` | Default response headers | Security headers |

### 3.7 Locating handlers fast

```python
# Handler class definitions
ast_grep_search(pattern='class $NAME(tornado.web.RequestHandler):', lang='python')

# URL patterns in Application
ast_grep_search(pattern='tornado.web.Application([$$$])', lang='python')

# URLSpec patterns
ast_grep_search(pattern='url($PATTERN, $HANDLER, $$$)', lang='python')
```

| File / Directory | Purpose |
|------------------|---------|
| `app.py` | Main application (the `Application` url-spec list) |
| `handlers/` | Handler classes |
| `views/` | View handlers |
| `api/` | API handlers |

### 3.8 Enumeration checklist

- One endpoint per `(regex, HandlerClass)` tuple **per verb method** on that handler
  class — a handler with `get` and `post` is two endpoints at the same path.
- The path is the regex, recorded **as written** (capture groups are path params).
- The HTTP method is the verb method name (`get`→GET, `post`→POST, …), including
  custom methods added via `SUPPORTED_METHODS`.
- The `region` is the verb method's body span (signature line → closing brace),
  never the registration tuple line.
- Compose the prefix (L1 + any `add_handlers` mount) the main agent handed you onto
  every path.
