# PHP — raw / file-as-endpoint routing

A FILE-AS-ROUTE framework: with no router, **the URL path IS the file path
relative to the web root**. Every reachable `.php` file under the web root is one
HTTP endpoint — there is no annotation, decorator, or route table to grep.

## 1. Identify

Raw PHP with NO router/framework: `.php` files are served directly, with no
front-controller or framework router in between. Marker: `.php` files reachable by
URL and running request-handling logic at top level, with no central dispatcher.

## 2. Structural traversal — main agent

- **L1 Deployment** — the web-root document path / context: the directory the
  server maps URLs into, so a request path maps to a file path relative to that web
  root (e.g. `admin/update-image1.php` ⇄ `<web-root>/admin/update-image1.php`).
- **L3 "root"** — the web-root directory tree (and its subtrees). A root here is a
  directory of served `.php` files, not a class or route table.
- **Prefix composition** — because the URL path IS the file path relative to the web
  root, the MAIN agent identifies the web root(s) and the directory subtrees and
  **pre-composes the directory path as the prefix**; the worker only appends the
  filename. Example: subtree `admin/` → `prefix=admin`.

### Dispatch contract

- One worklist entry = one web-root subdirectory.
- Hand each worker: `framework=raw-php`, `prefix=<directory path relative to web
  root>`, `location=<the directory>`, `scope=<the directory's `.php` files glob>`.
- Split / merge rule: one entry per **meaningful** subdirectory — group small dirs
  together rather than one entry per file, but split a large subtree so no worker is
  swamped. Skip non-served dirs (`vendor/`, an `includes/`/`inc/`/`partials/` that is
  not directly reachable) where discernible.

## 3. Handler enumeration — worker

Given one root's scope (a web-root subdirectory):

1. List every `.php` file in scope, EXCLUDING pure includes that are never requested
   directly (`config.php`, `db.php`, `header.php`, `footer.php`, files under an
   `includes/`/`inc/`/`partials/` dir that only define helpers). A file is an
   endpoint if it can be reached by URL and runs request-handling logic at top level.
2. Each endpoint file = one endpoint at `{dir prefix}/{filename}.php` (the file path
   relative to the web root, e.g. `check_availability.php`,
   `admin/update-image1.php`). Apply the prefix the main agent handed you.
3. The **HTTP method** is typically `*` by default. If the file documents which
   superglobal it reads, you may infer it: `$_GET` → GET, `$_POST` → POST,
   `$_REQUEST`/`$_COOKIE`/`$_SERVER` → either — but keep `*` unless the read is clear.
4. The **parameters** are the superglobal keys it reads (`$_POST['cid']`,
   `$_GET['id']`, …). Record each as an input.
5. Inline `<form action="x.php" method="post">` and `$.ajax({url:'x.php'})` in
   sibling `.php`/`.js` confirm the method + param names for `x.php`.
6. **Region** = the whole file, or its top-level request-handling block.

### Front-controller variant

Some apps route everything through `index.php` (a `switch($_GET['page'])` or an
`.htaccess` rewrite to `index.php`). Then `index.php` is ONE file but MANY logical
endpoints — enumerate by the dispatch keys (the `page`/`action`/`route` values) and
the files they `include`.

### Why this matters

PHP SQLi/LFI/XSS sinks usually sit in the SAME file as the request read, a few lines
below the `$_POST[...]` assignment — e.g.
`$cid=$_POST['cid']; mysqli_query($con,"... WHERE course='$cid'")`. Missing a file
means missing the endpoint AND its sink. Err toward listing a file as an endpoint; a
non-endpoint include costs one wasted audit, a missed endpoint costs a whole
vulnerability.
