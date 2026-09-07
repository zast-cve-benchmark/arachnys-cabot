# Thymeleaf (Spring MVC template engine)

[Thymeleaf](https://www.thymeleaf.org/) is a server-side Java template engine
auto-configured by Spring Boot.  `@Controller` handlers produce a **view name**
that Thymeleaf resolves to an HTML template under `resources/templates/`.

## View name sources

Every `@Controller` handler (NOT `@RestController`) produces a view name:

| Return type | View name | User-controllable? |
|---|---|---|
| `String` (no `@ResponseBody`) | The returned string itself | Yes, if it includes user input |
| `void` | Derived from request URL path by `DefaultRequestToViewNameTranslator` | Yes — URL segments are user-controlled |
| `ModelAndView` | `getViewName()` | Yes, if constructed from user input |

Anti-patterns — no view resolution occurs:
- `@RestController` at class level
- `@ResponseBody` on the method

## Decision rules

`@Controller` + non-`@ResponseBody` → always emit `template-render`.

The framework resolves a view regardless of whether the handler body is empty
or the return value is hardcoded — emit the capability and let the specialist
skill determine exploitability.

## Patterns

```java
// String return + user input → template-render
@GetMapping("/page/{name}")
public String page(@PathVariable String name) {
    return "folder/" + name;
}

// Void return → template-render (view name from URL)
@GetMapping("/con/{page}")
public void show(@PathVariable String page) { }

// Fragment expression → template-render
@PostMapping("/getNames")
public String names(String fragment, ModelMap mmap) {
    return "monitor/cache/cache::" + fragment;
}

// Hardcoded return → template-render (recall over precision)
@GetMapping("/login")
public String login() {
    return "login";
}

// @ResponseBody → NOT template-render
@PostMapping("/login")
@ResponseBody
public ResponseEntity<?> login(@RequestBody LoginRequest req) { ... }

// @RestController → NOT template-render
@RestController
@GetMapping("/api/data")
public Data getData() { ... }
```
