# Django & DRF Endpoint Enumeration Reference

Django maps URLs to views through `urlpatterns` lists (`path()`, `re_path()`,
legacy `url()`), composed across apps via `include()`. Django REST Framework
(DRF) extends this with ViewSets and Routers that auto-generate REST endpoints.

Routing here is **per-root, pre-composed by the main agent**: each `include()`
mounts an app's urlconf under a prefix, and prefixes compose through nested
includes. The main agent walks from `ROOT_URLCONF` through every `include()`,
pre-composes L1 + the include prefixes, and hands the whole segment to the
worker; the worker enumerates each `path/re_path/url` line in that urlconf and
its views.

---

## 1. Identify

- **Dependency** — `django` (plus `djangorestframework` if DRF is present) in
  `requirements.txt` / `pyproject.toml` / `setup.py`.
- **Route-registration markers** — `urlpatterns = [...]`, the
  `path(...)` / `re_path(...)` / `url(...)` calls inside it, and `include(...)`
  for sub-urlconfs.
- **Admin surface** — `admin.site.urls` mounted in a urlconf (often
  `path("admin/", admin.site.urls)`), `admin.autodiscover()`, and every
  `admin.site.register(...)` / `@admin.register(...)`. These pull in a large set
  of endpoints that are NOT written as `path()` lines — see §3.7.
- **i18n wrapper** — `i18n_patterns(...)` (from `django.conf.urls.i18n`) wraps
  routes with a language prefix; treat it as transparent — see §3.8.
- **Entry point** — `ROOT_URLCONF` in the settings module names the root
  urlconf where the URL tree begins.

---

## 2. Structural traversal — main agent

The main agent walks from `ROOT_URLCONF` through every `include()`, composing the
prefix prepended at each mount. It stops there — it does **not** read the
individual `path/re_path/url` handler lines or the views (that is the worker's
job, §3).

**L1 Deployment.** Any WSGI mount or a `FORCE_SCRIPT_NAME` base path applied
before any code; usually `/` (Django apps typically mount at the root). If a
reverse-proxy / WSGI mount prefix exists, it is the L1 segment.

**L3 Registration root.** The root is the root `urlpatterns` list named by
`ROOT_URLCONF`. Each `path("x/", include("app.urls"))` mounts a sub-urlconf
(another app's `urls.py`) under the prefix `x/`. These compose through nested
includes — an include inside an included urlconf stacks its prefix onto the
parent's. Start from `ROOT_URLCONF`, follow each `include(...)` to the app's
`urls.py`, and treat each included urlconf (and the root urlconf itself) as a
root.

A mount of **`admin.site.urls`** (e.g. `path("admin/", admin.site.urls)`) is a
registration root too, but its routes are auto-generated from the registered
`ModelAdmin`s, not written in a urls.py. **Treat each registered `ModelAdmin` as
its own registration root**, and — exactly like an `include()` prefix — have the
MAIN agent **pre-compose that root's prefix as `/admin/<app_label>/<model_name>/`**
and hand it to the worker, so the worker only appends route paths (never has to
derive the admin prefix itself). Build this worklist by grepping EVERY
`admin.site.register(Model, SomeAdmin)` / `@admin.register(Model)` across all
`admin.py` / `admin/` modules; for each, `app_label` = the model's app and
`model_name` = the model class name lowercased (`register(Post, PostAdmin)` in app
`blog` → prefix `/admin/blog/post/`). One worker per registered model; the worker
expands that model's routes under the handed prefix per §3.7. Missing a registered
model drops its whole `/admin/<app>/<model>/` surface.

> **ORDER — app views FIRST, admin SECOND, always both.** The urlconfs reached by
> `include()` from `ROOT_URLCONF` (the app's own views, e.g. `include('blog.urls')`
> → its `/posts/`, `/posts/<id>/comment/…` views) are the PRIMARY worklist and MUST be
> built and dispatched. The admin model entries are ADDITIONAL, appended after.
> **Never submit a worklist (or emit a result) that is only `/admin/...` routes when
> `ROOT_URLCONF` `include()`s app urlconfs** — an all-admin result means you got
> absorbed in the admin and dropped the app's own views, the single worst and most
> common failure here. The app's `include()`d views are usually the bulk of the
> real surface; the admin is on top of them, not instead of them. **`i18n_patterns(...)` is transparent**: it
only adds an optional `/<lang>/` localization prefix that is not part of route
identity, so compose prefixes through it as if its arguments sat directly in
`urlpatterns` — do NOT add a `/<lang>/` segment (§3.8).

```python
# main/urls.py  (the ROOT_URLCONF)
from django.urls import include, path

urlpatterns = [
    path("polls/", include("polls.urls")),      # mounts polls.urls under "polls/"
]
```

Multiple instances of the same urlconf can be mounted under different prefixes
with namespacing, and each mount is its own prefix:

```python
urlpatterns = [
    path("author-polls/", include(("polls.urls", "polls"), namespace="author-polls")),
    path("publisher-polls/", include(("polls.urls", "polls"), namespace="publisher-polls")),
]
```

**Prefix composition.** Django is a **router-mount framework**, so the **MAIN
agent PRE-COMPOSES L1 + every `include()` prefix** down the chain and hands the
whole composed segment to the worker. Compose nested include prefixes (parent
mount + child mount + …) before handing off.

**DRF routers.** A `router.register(...)` auto-generates a set of REST endpoints
for a ViewSet; the router's URLs are usually mounted via `include(router.urls)`.
Treat that mount like any other include (the worker enumerates the generated
routes — §3.5). **Completeness on router-heavy apps:** a large DRF project registers
ViewSets across **many apps**, each `router.register` line expanding to ~6+ endpoints.
Grep the whole tree for **every** `router.register(` / `routers.` mount and give each
its own worklist entry — enumerating only a few apps' routers silently drops most of
the API surface (one ViewSet missed ≈ 6+ endpoints lost).

### Dispatch contract

- One worklist entry = **one included urlconf** (one app's `urls.py`), or the
  root urlconf itself.
- Hand each worker: `framework=django`,
  `prefix=<the pre-composed L1 + the composed include() prefixes leading to this
  urlconf>`, `location=<file:line of the include(...) call, or of this urls.py>`,
  `scope=<that app's urls.py PLUS its views (views.py / viewsets.py / api/ …)>`.
- Split / merge: one entry per included urlconf. Compose nested include prefixes
  into each entry's `prefix`. Do NOT over-split one urlconf's pattern list into
  many tiny scopes.

---

## 3. Handler enumeration — worker

Given one urlconf's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you). Each `path` / `re_path` /
`url` line in the `urlpatterns` is one endpoint; follow its view to record the
HTTP method(s) and the region.

### 3.1 URL pattern lines → endpoints

Each entry in `urlpatterns` maps a path to a view.

```python
# path() — modern Django (2.0+)
from django.urls import path
from . import views

urlpatterns = [
    path("about/", views.about, name="about"),
    path("articles/<int:year>/", views.year_archive, name="year-archive"),
    path("articles/<int:year>/<int:month>/", views.month_archive),
    path("articles/<slug:slug>/", views.article_detail),
]
```

```python
# re_path() — regular-expression patterns (and legacy url())
from django.urls import re_path

urlpatterns = [
    re_path(r"^articles/(?P<year>[0-9]{4})/$", views.year_archive),
    re_path(r"^articles/(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/$", views.month_archive),
]
```

**Path converters** (record the path as written — the auditor matches on the
registered template):

| Converter | Pattern | Matches |
|-----------|---------|---------|
| `str` | `<name>` | Any non-empty string (no `/`) |
| `int` | `<int:id>` | Positive integers |
| `slug` | `<slug:slug>` | ASCII letters, numbers, hyphens, underscores |
| `uuid` | `<uuid:id>` | Formatted UUID |
| `path` | `<path:filepath>` | Any string including `/` |

`re_path` uses raw regex groups (`(?P<year>[0-9]{4})`) for the same purpose.

### 3.2 Function-based views

The view named in the pattern is a function taking `request`. It may branch on
`request.method` internally, or be constrained by method decorators.

```python
from django.http import HttpResponse, JsonResponse

def hello_world(request):
    return HttpResponse("Hello, World!")

def api_endpoint(request):
    if request.method == "GET":
        return JsonResponse({"status": "ok"})
    elif request.method == "POST":
        return JsonResponse({"status": "created"})
```

HTTP-method restriction decorators narrow the allowed methods:

```python
from django.views.decorators.http import (
    require_http_methods, require_GET, require_POST, require_safe
)

@require_http_methods(["GET", "POST"])
def my_view(request): ...

@require_GET
def list_items(request): ...

@require_POST
def create_item(request): ...
```

**Methods:** read `require_GET`/`require_POST`/`require_http_methods([...])` if
present; else read the `request.method` branches; else the view serves any
method (`"*"`).

### 3.3 Class-based views — methods from the handler methods

A pattern points at `SomeView.as_view()`. The HTTP methods are the
lowercase method names defined on the class (`get` → GET, `post` → POST,
`put` → PUT, `delete` → DELETE, …).

```python
from django.views import View

class MyView(View):
    def get(self, request, *args, **kwargs):   # -> GET
        return HttpResponse("Hello, World!")
    def post(self, request, *args, **kwargs):  # -> POST
        return HttpResponse("Posted!")
```

Decoration via `@method_decorator` wraps the dispatch (e.g. `login_required`):

```python
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

@method_decorator(login_required, name="dispatch")
class ProtectedView(View):
    def get(self, request): ...
```

Generic CBVs (`ListView`, `DetailView`, `CreateView`, …) expose conventional
methods (a `ListView`/`DetailView` serves GET; `CreateView`/`UpdateView` serve
GET + POST):

```python
from django.views.generic import ListView, DetailView, CreateView

class ArticleListView(ListView):
    model = Article
    template_name = "article_list.html"

class ArticleDetailView(DetailView):
    model = Article

class ArticleCreateView(CreateView):
    model = Article
    fields = ['title', 'content']
```

### 3.4 DRF APIView

`APIView` subclasses define HTTP methods as methods, like a CBV:

```python
from rest_framework.views import APIView
from rest_framework.response import Response

class SnippetList(APIView):
    def get(self, request, format=None):    # -> GET
        snippets = Snippet.objects.all()
        return Response(SnippetSerializer(snippets, many=True).data)
    def post(self, request, format=None):   # -> POST
        serializer = SnippetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
```

### 3.5 DRF ViewSets — actions → REST verbs + paths

A ViewSet groups CRUD actions; each action maps to an HTTP verb + path shape.

```python
from rest_framework import viewsets

class SnippetViewSet(viewsets.ModelViewSet):
    queryset = Snippet.objects.all()
    serializer_class = SnippetSerializer
    permission_classes = [IsAuthenticated]
```

| ViewSet Type | Operations |
|--------------|------------|
| `ModelViewSet` | Full CRUD (list, create, retrieve, update, destroy) |
| `ReadOnlyModelViewSet` | Read-only (list, retrieve) |
| `GenericViewSet` | Base class for custom combinations |

The standard action → verb + path mapping (relative to the router's prefix for
the ViewSet):

| Action | Method | URL shape |
|--------|--------|-----------|
| list | GET | `<prefix>/` |
| create | POST | `<prefix>/` |
| retrieve | GET | `<prefix>/{pk}/` |
| update | PUT | `<prefix>/{pk}/` |
| partial_update | PATCH | `<prefix>/{pk}/` |
| destroy | DELETE | `<prefix>/{pk}/` |

**Custom `@action` methods** add extra routes (`detail=True` → `{pk}/<name>/`,
`detail=False` → `<name>/`; method(s) from the decorator's `methods=[...]`):

```python
from rest_framework.decorators import action

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(detail=True, methods=['post'])     # POST  <prefix>/{pk}/set_password/
    def set_password(self, request, pk=None):
        return Response({'status': 'password set'})

    @action(detail=False)                       # GET   <prefix>/recent/
    def recent(self, request):
        return Response([])
```

### 3.6 DRF router-generated routes

A `DefaultRouter` / `SimpleRouter` auto-generates the CRUD routes for each
registered ViewSet. Enumerate one endpoint per generated route (per §3.5's
table), composed under the registration prefix and the mount prefix.

```python
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'snippets', SnippetViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

**Auto-generated routes** for `router.register(r'users', UserViewSet)` mounted
under `api/`:

| Method | URL | Action |
|--------|-----|--------|
| GET | `/api/users/` | list |
| POST | `/api/users/` | create |
| GET | `/api/users/{pk}/` | retrieve |
| PUT | `/api/users/{pk}/` | update |
| DELETE | `/api/users/{pk}/` | destroy |

### 3.7 Django admin — `admin.site.urls` (an ADDITIONAL surface)

> Admin routes are enumerated **in addition to**, never **instead of**, the
> regular `urlpatterns` views of §3.1–3.6. Always enumerate every included
> urlconf's own views FIRST and in full (a function/CBV/DRF view reachable at a
> normal path is the primary surface and the usual label set); only THEN add the
> admin routes below. Do not let the admin crowd out the app's own views — a
> result that is all `/admin/...` and no app views means the regular urlconfs
> were skipped, which is the bigger miss.

When `path("admin/", admin.site.urls)` is mounted it adds the Django admin, a
surface that is NOT written as `path()` lines. You (the worker) are handed ONE
registered model and its **pre-composed prefix `/admin/<app_label>/<model_name>/`**
(e.g. a `Post` model in the `blog` app → `/admin/blog/post/`). Every route below
is that prefix **+** the route's own regex.

> **Every emitted endpoint MUST start with the handed `/admin/<app>/<model>/`
> prefix.** The route regexes inside `get_urls()` are RELATIVE — a bare
> `^([0-9]+)/publish/$` is the route `/admin/<app>/<model>/<id>/publish/`, NOT
> `([0-9]+)/publish/`. Never emit a bare/relative admin route (`([0-9]+)/some-action/`,
> `some-action/`) — always prepend the model prefix.

Default `ModelAdmin` routes, present for **every** registered model:

| Method | URL (under `/admin/<app>/<model>/`) | Action |
|--------|-------------------------------------|--------|
| GET | `` | changelist |
| GET,POST | `add/` | add |
| GET,POST | `<pk>/change/` | change |
| GET,POST | `<pk>/delete/` | delete |
| GET | `<pk>/history/` | history |

**Custom admin routes — read `get_urls()`.** A `ModelAdmin` that overrides
**`get_urls()`** prepends extra routes, each relative to that same
`/admin/<app>/<model>/` prefix. These custom views (publish, copy, move,
change-permissions, …) are the security-relevant admin endpoints — when a
registered `ModelAdmin` defines `get_urls()`, OPEN its class and read the
`get_urls()` body, emitting one endpoint per route it returns (before
`super().get_urls()`); don't stop at the default-CRUD table above.

**Follow the inheritance chain (MRO).** `get_urls()` routes are often contributed
by a **base class or mixin**, not the leaf `ModelAdmin` — e.g. a shared
`SomeAdminMixin.get_urls()` (often in a different file) adds routes like
`<id>/publish/`, `bulk-import/`, etc., and a leaf
`class FooAdmin(SomeAdminMixin, admin.ModelAdmin)` inherits them via
`super().get_urls()` (a common pattern for framework admin mixins). So for each registered model, read
`get_urls()` in EVERY class in its MRO (the leaf admin AND its bases/mixins) and
union the routes — all under that model's `/admin/<app>/<model>/` prefix. Missing
a mixin's routes drops them for every model that inherits it.

The routes are frequently built through a **local helper or lambda**, not a bare
`url(...)` — match ANY call inside the `get_urls()` return list whose first
argument is a URL regex/string, regardless of the wrapper's name
(`self.admin_site.admin_view(...)`, a `pat = lambda regex, fn: url(regex, ...)`
helper, etc.):

```python
@admin.register(Post)               # app "blog", model "Post" -> /admin/blog/post/
class PostAdmin(admin.ModelAdmin):
    def get_urls(self):
        # a local helper wrapping url() is the COMMON case — still a route
        pat = lambda regex, fn: url(regex, self.admin_site.admin_view(fn), name=fn.__name__)
        return [
            pat(r"^([0-9]+)/publish/$", self.publish),     # /admin/blog/post/<id>/publish/
            pat(r"^([0-9]+)/([a-z\-]+)/preview/$", self.preview),  # /admin/blog/post/<id>/<lang>/preview/
            url(r"^export/$", self.export),                # /admin/blog/post/export/
        ] + super().get_urls()
```

→ `/admin/blog/post/<id>/publish/`, `/admin/blog/post/<id>/<PARAM>/preview/`,
`/admin/blog/post/export/`. The raw regex groups `([0-9]+)` / `([a-z\-]+)` are
parameter slots — record them as written (the auditor normalizes them).

**Find every `admin.site.register(...)` / `@admin.register(...)` (across all
`admin.py` / `admin/` modules) and read every `ModelAdmin.get_urls()`** — these
endpoints exist only through the admin machinery, never as top-level `path()`
lines, and are a frequent audit target (CSRF, IDOR, privileged actions). region =
the admin view method body (the `self.<fn>` named in `get_urls()`, or the
`ModelAdmin` class for an inherited default action).

### 3.8 `i18n_patterns` — strip the language prefix

`urlpatterns += i18n_patterns(path("admin/", admin.site.urls), path("", include("app.urls")))`
wraps its arguments so every URL gains an optional language prefix (`/en/...`,
`/de/...`). That segment is a localization detail, **not** part of route
identity — enumerate the inner routes WITHOUT a leading `/<lang>/` segment
(record `/admin/...` and `/<slug>/`, never `/en/admin/...`). Treat
`i18n_patterns(...)` exactly like a plain `urlpatterns` list.

### 3.9 Region — anchor at the view body

Record the `region` at the **view body** — the function-view body, the relevant
HTTP-method method of a CBV/APIView, or the ViewSet action method. For
router-generated CRUD routes with no explicit override, anchor on the ViewSet
class's relevant member (or the class body if the action is inherited from the
base ViewSet).

### 3.10 Locating views

Search patterns for finding the views behind the patterns:

```python
# URL patterns
ast_grep_search(pattern='path($PATH, $VIEW)', lang='python')
ast_grep_search(pattern='re_path($PATTERN, $VIEW)', lang='python')

# Class-based / DRF views
ast_grep_search(pattern='class $NAME(View):', lang='python')
ast_grep_search(pattern='class $NAME(APIView):', lang='python')
ast_grep_search(pattern='class $NAME($ViewSet):', lang='python')

# Function views
ast_grep_search(pattern='def $NAME(request$$$):', lang='python')
```

```regex
path\s*\(
re_path\s*\(
class\s+\w+\((APIView|View|ModelViewSet|ReadOnlyModelViewSet|GenericViewSet)
@action\s*\(
register\s*\(
@?admin\.(site\.)?register
def get_urls\s*\(
i18n_patterns\s*\(
```

Key files: `urls.py` (URL config), `views.py` (view definitions),
`viewsets.py` (DRF ViewSets), `admin.py` (ModelAdmin registrations + custom
admin routes), and `api/` / `endpoints/` directories.

### 3.11 Enumeration checklist

- Each `path` / `re_path` / `url` line in this urlconf → one endpoint —
  **including lines whose view is a Django built-in class** (`JavaScriptCatalog`,
  `RedirectView`, `TemplateView`, `serve`, `auth` views, …). Never skip a
  registered route just because its view is framework code rather than app code;
  it is still a reachable endpoint.
- Follow the view: function view (method from decorator / `request.method` /
  else `"*"`), CBV/APIView (one method per `get`/`post`/… defined), ViewSet
  (the standard action → verb+path table, plus each `@action`).
- DRF router: enumerate every auto-generated CRUD route per registered ViewSet.
- **Django admin** (when `admin.site.urls` is mounted): for each registered
  `ModelAdmin`, the default CRUD routes + every `get_urls()` custom route, all
  under `/admin/<app>/<model>/` (§3.7).
- **`i18n_patterns`**: enumerate inner routes with NO `/<lang>/` prefix (§3.8).
- Record path converters `<int:id>` / `<slug>` / regex groups as written.
- Compose the prefix (L1 + include() prefixes) the main agent handed you onto
  every endpoint.
- `region` at the view body, never the `path(...)` registration line.
