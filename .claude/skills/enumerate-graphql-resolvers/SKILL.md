---
name: enumerate-graphql-resolvers
description: Enumerate a GraphQL API's resolver methods as HTTP controller endpoints so the per-endpoint auditor can audit each resolver. A standalone enumerator that runs concurrently with enumerate-http-controllers and enumerate-rpc-handlers inside enumerate-sources; it fast-exits when the project has no GraphQL surface. Covers Java (graphql-java-tools/kickstart, Spring for GraphQL, Netflix DGS, graphql-spqr), JS/TS (Apollo/graphql-js, NestJS, TypeGraphQL), Python (Graphene, Strawberry, Ariadne), Go (gqlgen).
---

# enumerate-graphql-resolvers

GraphQL serves every query/mutation/subscription over a **single HTTP path**
(usually `/graphql`), but each GraphQL field is handled by a distinct **resolver
method** whose arguments carry the user input — those resolver methods are the
real "controllers." A naive scan sees one endpoint and misses every sink behind
it.

Your job: emit **one `HttpControllerSource` per resolver method**, all sharing the
GraphQL HTTP path as their `endpoint`, so the per-endpoint audit can analyze each
resolver's data flow independently.

You run as your **own** enumerator — a sibling of the HTTP-controller and RPC-handler
enumerators, dispatched directly by the source-enumeration pipeline (not from inside
the HTTP enumerator). Do every read/grep yourself. Record via enumerate-http-controllers'
existing `record_controllers.py` (a GraphQL resolver IS an `HttpControllerSource` with
`graphql_operation` set, so it shares that one schema and recording script).

## Step 0 — Detect a GraphQL surface (cheap no-op gate)

Before reading any source in depth, grep for the presence of a GraphQL stack.
**Most projects have no GraphQL surface at all; a fast negative here is the common,
cheap case — stop and report rather than doing expensive reads for a technology that
isn't present.** Run these (adapt paths to the language):

```bash
# Schema files declaring GraphQL types (strongest signal)
grep -rlE 'type\s+(Query|Mutation|Subscription)\b' --include='*.graphql' --include='*.graphqls' --include='*.gql' . 2>/dev/null | head -5
# Library deps / imports across stacks
grep -rlE 'graphql-java|com\.netflix\.graphql|graphql-spqr|spring-boot-starter-graphql|apollo-server|@nestjs/graphql|type-graphql|graphql-yoga|graphene|strawberry|ariadne|gqlgen|graphql-go|99designs/gqlgen' \
  pom.xml build.gradle package.json requirements.txt pyproject.toml go.mod 2>/dev/null | head -5
# Resolver markers in source
grep -rlE 'GraphQLQueryResolver|GraphQLMutationResolver|@QueryMapping|@MutationMapping|@DgsQuery|@DgsMutation|@Resolver\(|resolve_[A-Za-z]|gqlgen' \
  --include='*.java' --include='*.kt' --include='*.ts' --include='*.js' --include='*.py' --include='*.go' . 2>/dev/null | head -5
```

If **none** of these hit, STOP. Report "no GraphQL surface found — project exposes no
GraphQL API" and record nothing. Do not proceed to step 1.

If one or more hit, note the stack and continue.

## Step 1 — Find the GraphQL HTTP path

Almost always `/graphql` (sometimes `/api/graphql`, `/query`, or a `/graphql/*`
mount). Confirm it from the HTTP wiring, do not assume:

- **Java**: a servlet/handler bound to the path — `GraphQLHttpServlet`, a
  `*GraphQLQueryHandler` registered on a route, Spring `spring.graphql.path`
  (default `/graphql`), DGS default `/graphql`.
- **JS/TS**: Apollo `app.use('/graphql', ...)` / `ApolloServer({...})` path;
  NestJS `GraphQLModule.forRoot({ path: '/graphql' })` (default `/graphql`).
- **Python**: Graphene `GraphQLView.as_view()` in `urlpatterns`; Strawberry/
  Ariadne ASGI/WSGI mount path.
- **Go**: gqlgen `http.Handle("/query", srv)` (default `/query`).

Use that one path as `endpoint` for **every** entry you record. If you genuinely
cannot find it, default to `/graphql`.

## Step 2 — Find the resolvers (grep by stack)

Identify which GraphQL library is in use, then locate its resolver units:

| Stack | Resolver unit = grep for | What counts as a handler |
|---|---|---|
| Java · graphql-java-tools / kickstart | classes `implements GraphQLQueryResolver` / `GraphQLMutationResolver` / `GraphQLSubscriptionResolver` / `GraphQLResolver<T>` | every **public method** of the class |
| Java · Spring for GraphQL | `@Controller` beans with `@QueryMapping` / `@MutationMapping` / `@SubscriptionMapping` / `@SchemaMapping` / `@BatchMapping` | each annotated method |
| Java · Netflix DGS | `@DgsComponent` with `@DgsQuery` / `@DgsMutation` / `@DgsSubscription` / `@DgsData(parentType,field)` | each annotated method |
| Java · graphql-spqr | beans with `@GraphQLQuery` / `@GraphQLMutation` / `@GraphQLSubscription` | each annotated method |
| Java · raw graphql-java | `DataFetcher` impls / lambdas wired in a `RuntimeWiring` / `TypeRuntimeWiring` | each `DataFetcher.get()` body |
| JS/TS · Apollo / graphql-js | a `resolvers` object: `{ Query: {...}, Mutation: {...}, Subscription: {...} }` | each function value under Query/Mutation/Subscription/<Type> |
| JS/TS · NestJS | `@Resolver()` classes with `@Query()` / `@Mutation()` / `@Subscription()` / `@ResolveField()` | each decorated method |
| JS/TS · TypeGraphQL | `@Resolver()` classes with `@Query()` / `@Mutation()` / `@FieldResolver()` | each decorated method |
| Python · Graphene | `class Query/Mutation(graphene.ObjectType)` with `resolve_<field>` / `mutate` methods | each `resolve_*` / `mutate` method |
| Python · Strawberry | `@strawberry.type` classes with `@strawberry.field` / `@strawberry.mutation` | each decorated method/field with a resolver |
| Python · Ariadne | `QueryType()` / `MutationType()` / `ObjectType()` with `@<type>.field("name")` | each decorated resolver function |
| Go · gqlgen | the generated `*Resolver` struct's methods (in `*.resolvers.go`), keyed by `queryResolver` / `mutationResolver` | each resolver method |

If the stack isn't listed, fall back on the shared shape: a class/object whose
methods/functions are wired to GraphQL schema fields, where the method arguments
come from the GraphQL request variables. Treat each such method as a handler.

## Step 3 — Record one entry per resolver method

For each resolver method, record:

```bash
python .claude/skills/enumerate-http-controllers/scripts/record_controllers.py \
  '{"endpoint":"<graphql path from step 1>","method":"POST","protocol":"http","graphql_operation":"Mutation.addTemplate","region":{"file_path":"<relative path>","start_line":N,"end_line":M}}' \
  '<item2>' ...
```

(No `-o` — the script writes to the host-injected `ZAST_ENUMERATION_SOURCES_FILE` on its own.)

- `endpoint` — the GraphQL HTTP path from step 1, **identical for every entry**
  (so findings match an endpoint-level `/graphql` label).
- `method` — always `"POST"` (GraphQL is served over HTTP POST).
- `graphql_operation` — **required for every GraphQL entry**: the type-qualified
  operation, `"<OperationType>.<field>"` where OperationType is `Query` /
  `Mutation` / `Subscription` and field is the GraphQL field name the resolver
  implements (e.g. `"Mutation.addTemplate"`, `"Query.searchServices"`). This is
  what keeps the many resolvers behind one `/graphql` path distinguishable
  downstream (working dir / snippet file / log are keyed on it); a field name is
  unique within its type, so this label is unique per resolver. Derive it from
  the schema field or the resolver method name + its resolver class's role
  (a `GraphQLMutationResolver` / `@MutationMapping` / `@DgsMutation` method →
  `Mutation.<field>`; a query resolver → `Query.<field>`).
- `region` — the resolver **method** itself: from its signature/decorator line to
  its closing brace. Each resolver lives at a distinct file:line, so the entries
  stay distinct even though they share the endpoint.
- **One entry per method.** Never merge multiple resolvers into one entry.
- Record per file as you go (one file read → one `record_controllers.py` call),
  same discipline as the generic worker — do not batch across files.

## Boundaries

- **Mutations are highest risk** (they write) — always include them.
- Skip pure schema/SDL files (`.graphqls`, `.graphql`, schema strings): they
  declare types, they do not handle requests.
- A trivial field resolver that takes no arguments and returns a stored scalar
  has no user input — you may skip it; but when unsure, include it (recall over
  precision: a needless entry costs one audit, a missed resolver hides a CVE).
- Read the resolver source and the schema-wiring file only; do not chase
  unrelated imports.
- You enumerate audit **units**; whether a resolver's input is actually
  exploitable is the downstream audit skill's judgment, not yours.
