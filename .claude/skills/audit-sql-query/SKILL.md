---
name: audit-sql-query
description: Audit endpoints with sql-query or nosql-query capabilities. Produces sql-injection / nosql-injection / insecure-database-connection findings.
---

# Role

Specialist for **sql-injection**, **nosql-injection**, and **insecure-database-connection**. Produces findings with
`category_id` in `{sql-injection, nosql-injection, insecure-database-connection}`, aligned with the audit-endpoint
routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `sql-query` or `nosql-query`.

# SINK patterns

**SQL injection:**

| Language | SINK |
|---|---|
| Java   | `Statement.execute*(concat)`, `Connection.prepareStatement(concat)` (with concat), MyBatis `${...}` (vs safe `#{...}`), JdbcTemplate.queryForList/Object with string concat |
| Python | `cursor.execute(f"...{x}...")`, `connection.execute(text(concat))`, Django `Model.objects.raw(concat)`, SQLAlchemy raw `text(concat)` |
| Node   | `mysql.query(concat)`, `knex.raw(concat)`, Sequelize `sequelize.query(concat)` |
| PHP    | `mysql_query(concat)`, `mysqli_query(concat)`, PDO `query(concat)` (no prepare) |
| Go     | `db.Query(concat)`, `db.QueryRow(concat)` (vs safe `db.Query(sql, args...)`) |

**NoSQL injection:**

- Mongo `$where` with user-controlled JS, raw `db.eval`, JSON body fed directly into `find`/`update` filter
- Redis EVAL with user-controlled lua
- Cassandra raw CQL string concat

**Unsafe DB connection:**

- Hardcoded credentials in source
- Disabled TLS / weak cert validation
- Connection strings concatenated with user input (very rare)

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param /
header / body / path param, or data carried via state (DB / session / file). If the source is a constant or
system-controlled value, do not report it.

# MyBatis: mandatory mapper resolution (Java) — do this before concluding "no SQLi"

The most common Java SQLi sink (`${}` in a mapper XML) is **never visible in your
snippets pool** — the pool has the Java call graph, but the SQL lives in a
`*Mapper.xml`. So "I saw no `${}` in the pool" is **not** evidence of safety.

**If the handler/service calls any MyBatis mapper interface method** (e.g.
`xxxMapper.selectList(...)`, `selectXxxList(...)`), you **MUST**:

1. Read `references/mybatis-mapper.md`.
2. Resolve the mapper interface FQN → its `*Mapper.xml` (Grep
   `namespace="<FQN>"`) and read the `<select|update|...>` block for that method.
3. Check for `${}` (injectable) vs `#{}` (safe), paying special attention to
   `ORDER BY ${}`, `LIKE '%${}%'`, and the AOP `@DataScope` → `${params.dataScope}`
   pattern (the taint enters via the aspect, not a visible handler argument).

**Decision rule — `${}` in mapper SQL is sql-injection BY DEFAULT.** A `${}`
interpolation inside a `<select|update|insert|delete>` / `@Select`-style mapper
statement is string substitution into SQL by construction. The burden of proof
is on SAFETY, not on danger: report it as `sql-injection` **unless you can prove
the interpolated value is a compile-time constant or a closed enum** (e.g.
`${@com.x.Const@TABLE}` or a value the code restricts to a fixed allowlist before
the call). Do **NOT** waffle and return `[]` on these grounds — every one of
them is a false reason to suppress:
- *"`${params.dataScope}` comes from the `@DataScope` aspect, not a request
  param, so it's not user-controlled."* WRONG — the dataScope SQL fragment is
  assembled at runtime from role/dept state the user influences; this is the
  canonical AOP-injected dataScope SQLi pattern. **Report it.**
- *"The value looks like it's set server-side / by the framework."* Indirect
  taint is still taint. Unless it's provably constant, report.
- *"`ORDER BY ${orderBy}` is escaped by a helper."* A
  denylist escaper is bypassable and is not a parameterized bind — still report
  (note the weak escaper in the finding).
Two runs reading the same mapper must reach the same verdict; this rule exists to
remove that ambiguity. When a mapper has multiple `${}` sinks, report each
distinct one.

Skipping this step is the #1 cause of missed Java SQLi. Do not report zero SQLi
on an endpoint that calls a mapper until you have read the mapper XML.

# Safe context (false-positive prevention)

Do NOT report:

- Parameterized queries / prepared statements where user input only ever flows through `?` placeholders or named binds
- MyBatis `#{param}` usage (vs unsafe `${param}` string substitution)
- ORM query builders (e.g. Django `Model.objects.filter(...)` with kwargs, SQLAlchemy Core `select().where()`) without
  any raw-SQL fragment containing user input
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories belong to other audit skills — LDAP injection -> `audit-ldap-query`; XML/XPath -> `audit-xml-parse`
/ `audit-xpath-eval`. If you spot them, mention them in your report and let the orchestrator dispatch the right
specialist; do not file them yourself.

# References

- `references/mybatis-mapper.md` — **mandatory** read when a MyBatis mapper method
  is called (see "MyBatis: mandatory mapper resolution" above). Resolves the
  mapper XML and the `${}` / `@DataScope` sinks that are never in your pool.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
