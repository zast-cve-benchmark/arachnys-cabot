# MyBatis: the SQL sink lives in the mapper XML, not the Java pool

When a Spring handler calls a MyBatis mapper interface method
(`userMapper.selectList(query)`, `genTableMapper.selectDbTableList(...)`), the
actual SQL — and the injectable `${}` — is in a **mapper XML file that is NOT in
your snippets pool** (the pool only has the Java call graph). You must resolve
and read it yourself.

## Resolve the mapper method -> XML

1. From the handler/service, note the mapper **interface FQN** and the **method
   name** being called (e.g. `com.example.app.mapper.UserMapper.selectUserList`).
2. Find the mapper XML: it declares `<mapper namespace="<that FQN>">`. Locate it:
   ```bash
   grep -rl 'namespace="com.example.app.mapper.UserMapper"' --include=*.xml .
   # or by file convention:  **/resources/**/UserMapper.xml
   ```
3. Inside that XML, read the `<select|update|insert|delete id="<methodName>">`
   block (and any `<sql>` fragments it `<include>`s).

## The sink: `${}` vs `#{}`

- `#{param}` -> bound PreparedStatement placeholder. **Safe.**
- `${param}` -> raw string substitution into the SQL. **Injectable** when the
  value is user-controllable.

Common injectable `${}` spots even when the handler "looks" parameterized:
- **`ORDER BY ${orderBy}` / `${sortColumn} ${isAsc}`** — column/sort can't be
  bound; almost always `${}`. User-controlled sort params are a classic sink.
- **`${params.dataScope}` / AOP-injected SQL fragments** — some Spring admin
  frameworks use a `@DataScope`-style AOP aspect to inject a raw SQL fragment
  into a `params` map; the mapper appends `${params.dataScope}`. The taint enters
  via the AOP aspect, not a visible handler argument — trace the `@DataScope`-style
  annotation on the service/mapper method, then find `${params.dataScope}` in the XML.
- `<if test="...">${...}</if>`, `LIKE '%${kw}%'`, `IN (${ids})`.

## Report

File the finding as `sql-injection` with the **endpoint** target (the HTTP entry
the user hits), and put the mapper XML location (file + line of the `${}`) in
`data_flow`. Do not file it against the XML as if it were the endpoint.
