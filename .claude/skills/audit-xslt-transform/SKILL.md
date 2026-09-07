---
name: audit-xslt-transform
description: Audit endpoints with xslt-transform capability. Produces xslt-injection findings.
---

# Role

Specialist for **xslt-injection**.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `xslt-transform`.

# SINK patterns

| Language | SINK |
|---|---|
| Java   | `TransformerFactory.newInstance().newTransformer(new StreamSource(userXslt))` |
| Python | `lxml.etree.XSLT(lxml.etree.XML(userXslt))` |
| Node   | `xslt4node`/`saxon-js` taking user-controlled stylesheet |
| PHP    | `$xsltProcessor->importStylesheet(DOMDocument::loadXML($user))` |
| .NET   | `XslCompiledTransform.Load(userXslt, ...)` with `XsltSettings(enableScript: true, ...)` |

# Safe context (false-positive prevention)

Do NOT report:

- XSLT stylesheets whose content traces back to a hard-coded constant, packaged resource,
  or system-controlled value (i.e. the user controls only the XML *input* document, not the
  stylesheet itself)
- .NET `XslCompiledTransform.Load` with default `XsltSettings()` (scripting + document
  function disabled) when the stylesheet is not user-controlled

Out-of-scope categories belong to other audit skills — generic XML parsing / XXE
-> `audit-xml-parse`; XPath expressions -> `audit-xpath-eval`. If you spot them,
mention them in your report and let the orchestrator dispatch the right specialist;
do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
