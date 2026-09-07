# Thymeleaf SSTI via view name injection

In Spring MVC + Thymeleaf, `@Controller` handlers produce a **view name** that
`ThymeleafViewResolver` resolves to a template under `resources/templates/`.
When user input reaches the view name, two attack classes apply.

## View name sources

| Return type | View name | User-controllable? |
|---|---|---|
| `String` (no `@ResponseBody`) | The returned string itself | Yes, if it includes user input |
| `void` | Derived from request URL path by `DefaultRequestToViewNameTranslator` | Yes — URL segments are user-controlled |
| `ModelAndView` | `getViewName()` | Yes, if constructed from user input |

No view resolution when: `@RestController`, `@ResponseBody`.

## Attack: SSTI via SpEL preprocessing

Thymeleaf preprocesses `__${…}__` markers in view names as SpEL expressions
**before** locating the template file.  The template does not need to exist —
SpEL executes first.

```
GET /con/__${T(java.lang.Runtime).getRuntime().exec('id')}__::.x
```

Vulnerable patterns:

```java
// Void return — view name from URL path
@GetMapping("/con/{page}")
public void show(@PathVariable String page) { }

// String return with user input
@GetMapping("/home/{page}")
public String page(@PathVariable String page) {
    return "home/" + page;
}

// Fragment expression with user input
@PostMapping("/getNames")
public String names(String fragment, ModelMap mmap) {
    return "monitor/cache/cache::" + fragment;
}
```

## Attack: Path traversal

View name `../../other-dir/secret` resolves to
`templates/other-dir/secret.html`, reading templates outside the intended
directory.  This is an information disclosure, not RCE.

## Not vulnerable

```java
// Hardcoded view name — no user input reaches view resolution
@GetMapping("/login")
public String login() {
    return "login";
}

// @ResponseBody — bypasses view resolution entirely
@PostMapping("/login")
@ResponseBody
public ResponseEntity<?> login(@RequestBody LoginRequest req) { ... }
```

## Safe context

Thymeleaf does not have a sandbox mode comparable to Jinja2's
`SandboxedEnvironment`.  Any user-controlled data reaching the view name in a
default Spring Boot + Thymeleaf setup is a finding.

The explicit API `TemplateEngine.process(userTemplate, context)` where
`userTemplate` is the template **content** (not the view name) is a separate,
more direct SSTI vector — already covered in the main SINK patterns table.
