# Quartz scheduled-task: stored job config -> deferred RCE

A very common second-order RCE in Spring admin apps (the "scheduled task" /
"定时任务" pattern): an endpoint **stores a job definition**, and the
**scheduler later executes it** in a different code path. Source (the endpoint)
and sink (the scheduler) are decoupled across storage + time, so a first-order
auditor never sees the sink.

## Source side (this endpoint persists)

Endpoints like `POST /job/add`, `/job/edit`, `/schedule/job/*` save a job row
whose key field is typically **`invokeTarget`** (a.k.a. `jobClass`, `beanName`,
`methodParams`). `invokeTarget` is a string the user controls, e.g.
`demoTask.run('test')` or `com.example.Foo.bar('x')`.

Enumerate `invokeTarget` / `jobClass` / `methodParams` / `cronExpression` as
persisted user-controllable fields.

## Sink side (scheduler executes — find it via Grep)

The downstream executor is NOT in your pool. Locate it:
```bash
grep -rn 'invokeTarget\|getBean\|invokeMethod\|JobInvokeUtil\|SchedulerFactory' --include=*.java .
```
Typical sink shapes — each is a distinct category:
- **`code-injection` / `el-injection`** — `invokeTarget` parsed and dispatched by
  reflection or SpEL/OGNL (`getBean(beanName).method(args)`), letting an attacker
  invoke arbitrary beans/methods. Look for a `*JobInvokeUtil.invokeMethod` or
  similar reflection-based dispatcher class.
- **`jndi-injection`** — `invokeTarget` reaches a JNDI/RMI/LDAP lookup, or the job
  data is fed to `Naming.lookup` / `InitialContext.lookup`.
- **`insecure-deserialization`** — job params (`methodParams`, blobs) are
  deserialized (SnakeYAML `Yaml.load`, Fastjson `parseObject` with autotype,
  native `ObjectInputStream`) when the scheduler hydrates the job.

## Whitelist note (don't false-negative on a weak filter)

These admin frameworks often ship an `invokeTarget` "whitelist"/blacklist
(a `*ScheduleUtils` allow-list / package-prefix checks). These are routinely
**bypassable** (allowed package prefixes, `ldap:` payloads, nested calls). If the
filter is present but incomplete, still report — note the filter and the bypass.

## Report

File against the **HTTP endpoint** that stores the config (the add/edit handler),
with the executor location in `data_flow`. One finding per distinct sink class
reachable from the stored field.
