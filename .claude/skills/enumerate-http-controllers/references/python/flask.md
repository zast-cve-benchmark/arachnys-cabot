# Flask Endpoint Enumeration Reference

Flask is a lightweight Python web framework that defines routes with decorators
(`@app.route`, `@bp.route`, the method-shortcut decorators) and groups them into
**blueprints** mounted onto the app at registration time.

Routing here is a **router-mount** shape: each blueprint binds a `url_prefix` to a
set of route handlers, so the **main agent pre-composes L1 + the blueprint's
`url_prefix`** and hands the whole prefix down; the worker enumerates that
blueprint's (or the app's) handlers and resolves each handler's path. App-level
`@app.route` handlers have no prefix — they mount directly under L1.

---

## 1. Identify

- **Dependency** — `flask` in `requirements.txt` / `pyproject.toml` / `Pipfile`.
- **Markers** — `Flask(__name__)` (the app object), `@app.route(...)` (route
  decorator), `Blueprint(...)` (a blueprint declaration),
  `app.register_blueprint(...)` (mounting a blueprint).

One grep-able signal each:

```bash
grep -rnE 'Flask\(|@\w+\.route|Blueprint\(|register_blueprint' --include='*.py' .
```

---

## 2. Structural traversal — main agent

The main agent finds the app, lists the registration roots (the app itself plus
each registered blueprint), and pre-composes each root's prefix. It stops there —
it does **not** read individual route handlers (that is the worker's job, §3).

**L1 Deployment.** Flask usually mounts at `/`. A non-root mount comes from
`APPLICATION_ROOT` / a WSGI mount prefix / a reverse-proxy prefix — read it if
present; otherwise L1 is `/`.

**L3 Registration roots.** Two kinds:

- **(a) The app itself** — for `@app.route` handlers declared directly on the
  `Flask(__name__)` object. No prefix beyond L1.
- **(b) Each blueprint** registered via `app.register_blueprint(bp, url_prefix="/x")`.
  A blueprint's root prefix is its **`url_prefix`** — taken from the
  `Blueprint(..., url_prefix=...)` declaration, or overridden by the `url_prefix`
  passed at `register_blueprint(...)` (the registration-site value wins).

**Prefix composition (router-mount → pre-compose).** Because each root binds one
prefix to its whole handler list, the main agent pre-composes `L1 + blueprint
url_prefix` and hands the whole segment:

```
L1 "/"  +  Blueprint(url_prefix="/api/v1")  ->  worker prefix "/api/v1"
L1 "/"  +  app-level @app.route             ->  worker prefix "/"
```

Find the roots:

```bash
grep -rnE 'register_blueprint|Blueprint\(|@app\.route|@bp\.route' --include='*.py' .
```

### Dispatch contract

- One worklist entry = **one blueprint** (or the **app root** for app-level
  `@app.route` handlers).
- Hand each worker: `framework=flask`,
  `prefix=<pre-composed L1 + blueprint url_prefix>` (e.g. `/api/v1`; `/` for the
  app root), `location=<file:line of the register_blueprint call / the Flask(...)
  app>`, `scope=<the module(s) defining that blueprint's routes>`.
- Split / merge: one entry per blueprint. **Compose nested blueprint prefixes** —
  a child blueprint registered onto a parent inherits the parent's prefix, so its
  worker prefix is `parent url_prefix + child url_prefix` (see §3.2). Do NOT
  over-split one blueprint's handler list into many tiny scopes.

---

## 3. Handler enumeration — worker

Given one root's scope (a blueprint module, or the app), enumerate every routed
handler and compose the final endpoint (apply the prefix the main agent handed
you). Anchor each `region` at the **view function body**.

### 3.1 Route decorators and HTTP methods

The basic route decorator; default method is **GET** (Flask also auto-adds `HEAD`
for any GET route, and `OPTIONS` for every route — record the explicitly-declared
methods, those are the audit surface):

```python
@app.route('/users')                      # GET  /users
def list_users():
    return {'users': ['alice', 'bob']}
```

**Method-specific shortcut decorators (Flask 2.0+)** — the verb is the decorator:

| Decorator | HTTP Method | Use Case |
|-----------|-------------|----------|
| `@app.get()` / `@bp.get()` | GET | Read operations |
| `@app.post()` / `@bp.post()` | POST | Create operations |
| `@app.put()` / `@bp.put()` | PUT | Full update |
| `@app.patch()` / `@bp.patch()` | PATCH | Partial update |
| `@app.delete()` / `@bp.delete()` | DELETE | Delete operations |

```python
@app.get('/users')
def list_users():
    return jsonify(users)

@app.post('/users')
def create_user():
    data = request.get_json()
    return jsonify(created=data['name']), 201

@app.put('/users/<int:id>')
def update_user(id):
    return jsonify(updated=id)

@app.delete('/users/<int:id>')
def delete_user(id):
    return jsonify(deleted=id)
```

**Multiple HTTP methods** via the `methods=[...]` argument — record one endpoint
per method, branched in the body on `request.method`:

```python
@app.route('/login', methods=['GET', 'POST'])   # GET and POST /login
def login():
    if request.method == 'POST':
        return handle_login()
    return show_login_form()
```

**Programmatic registration (`add_url_rule`)** — same routing, no decorator. The
path, `view_func`, and `methods` are arguments:

```python
def user_detail(user_id):
    return jsonify(id=user_id)

app.add_url_rule(
    '/users/<int:user_id>',
    view_func=user_detail,
    methods=['GET'],
)
```

### 3.2 Blueprints (prefix already composed)

The main agent handed you the composed prefix for this blueprint; compose it onto
every route path in the blueprint's module.

```python
# app/blueprints/api_v1.py
from flask import Blueprint
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

@api_v1.route('/users')          # final URL: /api/v1/users
def list_users():
    return jsonify(users)
```

| Blueprint Config | Route Decorator | Actual Route |
|-----------------|-----------------|--------------|
| No prefix | `@bp.route('/users')` | `/users` |
| `url_prefix='/api/v1'` | `@bp.route('/users')` | `/api/v1/users` |

**Nested blueprints** — a child blueprint registered onto a parent inherits the
parent's prefix; the composed prefix is `parent + child`:

```python
parent = Blueprint('parent', __name__, url_prefix='/parent')
child = Blueprint('child', __name__, url_prefix='/child')
parent.register_blueprint(child)
app.register_blueprint(parent)

# Endpoint: parent.child.create  ->  URL: /parent/child/create
```

### 3.3 Class-based views (MethodView)

A `MethodView` subclass maps each HTTP method to a same-named method
(`get`/`post`/`put`/`delete`/…), registered with `add_url_rule(...,
view_func=Cls.as_view('name'))`. Record **one endpoint per HTTP-method method
present on the class**, scoped to the `methods=[...]` of the rule it is bound to;
the `region` is each method's body.

```python
from flask.views import MethodView

class UserAPI(MethodView):
    def get(self, user_id=None):
        if user_id is None:
            return jsonify(users)            # list
        return jsonify(user=User.query.get_or_404(user_id))   # detail

    def post(self):
        data = request.get_json()
        return jsonify(created=data['name']), 201

    def put(self, user_id):
        return jsonify(updated=user_id)

    def delete(self, user_id):
        return jsonify(deleted=user_id)

app.add_url_rule('/users/',
    view_func=UserAPI.as_view('user_api'), methods=['GET', 'POST'])
app.add_url_rule('/users/<int:user_id>',
    view_func=UserAPI.as_view('user_api'), methods=['GET', 'PUT', 'DELETE'])
```

A class-level `decorators = [...]` list applies to every method (auth/rate-limit
wrappers) — note it, but it does not change the routed endpoints:

```python
class SecureAPI(MethodView):
    decorators = [login_required, rate_limit]
    def get(self):
        ...
```

### 3.4 Path parameters and converters

Record the path **as written** (the auditor matches the registered template). Flask
converters narrow what a segment matches; `<path:...>` is notable because it
matches slashes (multi-segment):

| Converter | Pattern | Matches | Example |
|-----------|---------|---------|---------|
| `string` (default) | `<name>` | Any text (no `/`) | `/user/john` |
| `int` | `<int:id>` | Positive integers | `/post/123` |
| `float` | `<float:temp>` | Floating point | `/temp/36.6` |
| `path` | `<path:filepath>` | Any text **including `/`** | `/files/a/b/c.txt` |
| `uuid` | `<uuid:id>` | UUID strings | `/users/550e8400...` |

```python
@app.route('/user/<username>')                       # string (default)
@app.route('/post/<int:post_id>')                    # int
@app.route('/files/<path:filepath>')                 # path (includes slashes)
@app.route('/users/<uuid:user_id>')                  # uuid
@app.route('/posts/<int:year>/<int:month>/<slug>')   # multiple variables
```

### 3.5 region — anchor at the view function body

The `region` must point at **where the request is handled** — the view function's
(or `MethodView` method's) body — not at the decorator/registration line.
`start_line` = the `def` signature line, `end_line` = the function's last line.
Downstream auditing reads the source at `region`, so a region on the `@app.route`
decorator points the auditor at routing plumbing, not logic.

### 3.6 Locating handlers (search patterns)

```python
# Route decorators (app- or blueprint-bound)
ast_grep_search(pattern='@app.route($PATH)', lang='python')
ast_grep_search(pattern='@bp.route($PATH)', lang='python')

# Method-specific decorators (Flask 2.0+)
ast_grep_search(pattern='@app.get($PATH)', lang='python')
ast_grep_search(pattern='@app.post($PATH)', lang='python')
ast_grep_search(pattern='@$BP.get($PATH)', lang='python')
ast_grep_search(pattern='@$BP.post($PATH)', lang='python')

# Class-based views
ast_grep_search(pattern='class $NAME(MethodView):', lang='python')
```

```regex
@(app|bp|blueprint)\.(route|get|post|put|delete|patch)\s*\(
add_url_rule\s*\(
class\s+\w+\(MethodView\)
```

**Key files to check:**

| Directory | Purpose |
|-----------|---------|
| `app.py` | Main application file |
| `routes/` | Route definitions |
| `blueprints/` | Blueprint modules |
| `views/` | View functions/classes |
| `api/` | API endpoints |

**Cross-check against the live URL map** (when the app can be imported) — confirms
nothing was missed; `url_for(...)` resolves an endpoint name back to its URL:

```python
with app.app_context():
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods} {rule.rule} -> {rule.endpoint}")

# url_for resolves endpoint name -> URL:
url_for('user_detail', user_id=123)   # /users/123
url_for('api_v1.list_users')          # /api/v1/users  (blueprint-qualified)
```

### 3.7 Enumeration checklist

- **Default method is GET** for `@route` with no `methods=`; the shortcut
  decorators (`@app.get`/`@bp.post`/…) name the verb. `methods=['GET','POST']` →
  one endpoint per method. (`HEAD`/`OPTIONS` are auto-added; record the declared
  methods.)
- **`add_url_rule`** is a decorator-free route — path / `view_func` / `methods`
  are its arguments.
- **MethodView** → one endpoint per HTTP-method method on the class, scoped by the
  rule's `methods=[...]`; `region` = each method body.
- **Compose the prefix** the main agent handed you (`L1 + blueprint url_prefix`)
  onto every path; for nested blueprints the prefix is `parent + child`.
- **Record the path as written** (`<int:id>`, `<path:p>`, `<slug>`) — do not
  normalize.
- **`region` = the view function body**, not the decorator line (§3.5).
