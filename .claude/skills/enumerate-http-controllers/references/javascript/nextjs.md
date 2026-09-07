# Next.js — file-as-route enumeration reference

A FILE-AS-ROUTE framework: there is no central route table — **the URL path is
derived from the file path**. Next.js has two routing systems that both map a file
location to a URL: the App Router (`app/` directory) and the Pages Router (`pages/`
directory). Each exposes several HTTP-reachable surfaces:

- **API handlers** — App Router `route.ts`/`route.js`, Pages Router `pages/api/*`.
- **Page routes** — App Router `page.tsx`/`page.js`, Pages Router non-`api` page
  files; these are server-rendered GET endpoints (they run server code: data
  fetching, `searchParams` / `getServerSideProps` — auditable).
- **Server Actions** — functions marked `'use server'`; Next dispatches them over
  HTTP, so each is a callable POST endpoint.

## 1. Identify

- **Dependency**: `next` in `package.json`.
- **App Router marker**: an `app/` directory containing `route.ts`/`route.js`
  (route handlers) and/or `page.tsx`/`page.js` (page routes).
- **Pages Router marker**: a `pages/` directory — `pages/api/*` (API handlers,
  `export default handler`) and/or non-`api` page files (`getServerSideProps` /
  `getStaticProps` exports).
- **Server Actions marker**: a `'use server'` directive (top of an `actions.ts`, or
  inline at the top of a function body in a Server Component).

A project may use either router or both at once.

## 2. Structural traversal — main agent

Next.js is a **FILE-AS-ROUTE framework** — the URL path is derived from the file
path; there is no central route table to grep.

- **L1 Deployment** — `basePath` from `next.config.js` (if any), prepended to every
  route. Absent → mounts at `/`.
- **L3 "roots"** — the two routing trees. Walk every one of these file-route
  surfaces in each tree:
  - **App Router** — the `app/` tree:
    - `route.ts` at `app/a/b/route.ts` → API endpoints at `/a/b`.
    - `page.tsx`/`page.js` at `app/a/b/page.tsx` → a GET endpoint at `/a/b`.
    - Server Actions (`'use server'`) in an `actions.ts` or inline in a Server
      Component → POST endpoints.
    - Dynamic segments `[id]` → `/:id`. **Route groups `(group)` add NO path
      segment** — preserve them as grouping only, never emit them into the URL.
  - **Pages Router** — the `pages/` tree:
    - `pages/api/a/b.ts` → API endpoint at `/api/a/b`.
    - non-`api` page files (`pages/a/b.tsx`) → a GET endpoint at `/a/b`.
- **Prefix composition** — because the URL path IS the file path, the **MAIN agent
  walks these dirs and PRE-COMPOSES each file's path prefix from its directory
  location**: fold in `basePath`, rewrite dynamic segments (`[id]` → `:id`), and
  drop route-group parens. The worker only appends the per-handler tail.

### Dispatch contract

- One worklist entry = one subtree of `app/` or `pages/` — group by feature
  directory. A subtree may contain `route.ts`, `page.tsx`, **and** server actions
  at once; one worker covers the whole subtree.
- Hand each worker: `framework=nextjs`, `prefix=<the composed dir path, incl.
  basePath>`, `location=<the dir>`, `scope=<the route/page/action files glob in that
  subtree>`.
- Split / merge rule: one entry per feature subtree. Do **not** make one entry per
  file — group a feature dir's files under a single worker; split only when a subtree
  is large enough to swamp one worker.

## 3. Handler enumeration — worker

Given one root's scope (an `app/` or `pages/` subtree), apply the prefix the main
agent handed you and enumerate every routed surface below.

### App Router route handlers (`route.ts`/`route.js`)

Each exported HTTP-method function in a `route.ts` is one endpoint at the file's
derived path; the **method is the exported function name**:

| Export Function | HTTP Method |
|-----------------|-------------|
| `GET()` | GET |
| `POST()` | POST |
| `PUT()` | PUT |
| `PATCH()` | PATCH |
| `DELETE()` | DELETE |
| `HEAD()` | HEAD |
| `OPTIONS()` | OPTIONS |

```ts
// app/api/posts/[id]/route.ts  →  endpoints at /api/posts/:id
export async function GET(request, { params }) { /* ... */ }   // GET  /api/posts/:id
export async function POST(request) { /* ... */ }              // POST /api/posts/:id
export async function PUT(request, { params }) { /* ... */ }   // PUT  /api/posts/:id
export async function DELETE(request, { params }) { /* ... */ }// DELETE /api/posts/:id
```

### App Router page routes (`page.tsx`/`page.js`)

A `page.tsx`/`page.js` is a server-rendered **GET endpoint at its derived path**
(`app/a/b/page.tsx` → GET `/a/b`). Its default-export component runs server code —
data fetching, and reading `params` / `searchParams` (attacker-controlled query
input) — so it is auditable. Enumerate one GET endpoint per `page.tsx`/`page.js`.

```tsx
// app/blog/[slug]/page.tsx  →  GET /blog/:slug
export default async function Page({ params, searchParams }) {
  const { slug } = await params           // path segment
  const filters = (await searchParams).q  // attacker-controlled query input
  /* ... */
}
```

### Server Actions (`'use server'`)

A function marked `'use server'` is dispatched by Next over HTTP — enumerate each as
a **POST endpoint**. Two forms to spot:

- **Module-level**: a file whose first line is `'use server'` — every exported
  function in it is a server action.
- **Inline**: a function whose body's first statement is `'use server'` (commonly an
  action defined inside a Server Component, wired to a `<form action={...}>`).

```ts
// app/actions.ts  →  POST server action createPost
'use server'
export async function createPost(formData) { /* db write */ }
```

```tsx
// inline inside a Server Component  →  POST server action
async function createPost(formData) {
  'use server'
  /* ... */
}
```

### Pages Router API handlers (`pages/api/*`)

The **default export** of a `pages/api/*` file is one endpoint at the file's derived
path. The method is `*` unless the handler branches on `req.method`, in which case
record the methods it handles:

```ts
// pages/api/hello.ts  →  endpoint at /api/hello
export default function handler(req, res) {
  if (req.method === 'POST') { /* ... */ }   // method branched → POST + GET
  else { /* ... */ }
}
```

### Pages Router page routes (non-`api`)

A non-`api` page file (`pages/a/b.tsx`) is a **GET endpoint at its derived path**
(`pages/a/b.tsx` → GET `/a/b`). An exported `getServerSideProps` (or
`getStaticProps`) runs server code at request time — reading `context.query` /
`context.params` (attacker-controlled input) — so it is auditable. Enumerate one GET
endpoint per non-`api` page file.

```tsx
// pages/profile/[id].tsx  →  GET /profile/:id
export async function getServerSideProps(context) {
  const { id } = context.params           // path segment
  const sort = context.query.sort         // attacker-controlled query input
  /* ... */
}
```

### Middleware / proxy (NOT an endpoint)

`middleware.ts` (renamed `proxy.ts` in Next 16+) is **not itself an endpoint** — do
not enumerate it. It is a routing-affecting layer that runs before matched routes and
can rewrite/redirect requests (its `config.matcher` scopes which paths it touches).
Note its presence so the auditor is aware it can alter where a request lands, but
record no endpoint for it.

### Dynamic segments

| Pattern | Example File | URL Match |
|---------|--------------|-----------|
| `[segment]` | `app/blog/[slug]/route.ts`, `app/blog/[slug]/page.tsx`, `pages/blog/[slug].js` | `/blog/post1` |
| `[...segment]` | `app/shop/[...slug]/route.ts`, `pages/shop/[...slug].js` | `/shop/a/b/c` |
| `[[...segment]]` | `app/docs/[[...slug]]/route.ts` | `/docs`, `/docs/guide` |

A catch-all `[...slug]` / optional catch-all `[[...slug]]` matches a variable-length
path tail; in the Pages Router the resolved `slug` is always an array.

### Region

Anchor the region at the routed function body: the `GET`/`POST`/… function (App
Router route handler), the default `handler` (Pages Router API), the default-export
component (App Router page), `getServerSideProps`/`getStaticProps` (Pages Router
page), or the action function (server action).

### AST / regex search patterns

```typescript
// App Router route-handler exports
ast_grep_search(pattern='export async function GET($$$)', lang='typescript')
ast_grep_search(pattern='export async function POST($$$)', lang='typescript')
// Pages Router API handlers
ast_grep_search(pattern='export default function handler($$$)', lang='typescript')
// Server actions
ast_grep_search(pattern="'use server'", lang='typescript')
```

```regex
export\s+async\s+function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)
export\s+default\s+function\s+handler
export\s+(async\s+)?function\s+getServerSideProps     # Pages Router page route
'use\s+server'                                        # server action
export\s+function\s+(proxy|middleware)                # routing layer, not an endpoint
```
