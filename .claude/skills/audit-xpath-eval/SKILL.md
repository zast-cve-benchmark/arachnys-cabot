---
name: audit-xpath-eval
description: Audit endpoints with xpath-eval capability. Produces xpath-injection findings.
---

# Role

Specialist for **xpath-injection** — XPath expression built from user-controlled strings. Produces findings with `category_id` = `xpath-injection`, aligned with the audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `xpath-eval`.

# SINK patterns

| Language | SINK |
|---|---|
| Java   | `XPath.compile(user)`, `XPathExpression.evaluate(user, ...)`, `javax.xml.xpath.XPathFactory.newXPath().evaluate(user, ...)` |
| Python | `lxml.etree.XPath(user)`, `Element.xpath(user)`, `xml.etree.ElementTree.find(user)` (XPath subset) |
| Node   | `xpath.select(user, doc)`, `xmldom`-based XPath libs |
| PHP    | `DOMXPath::query($user)`, `SimpleXMLElement::xpath($user)` |
| .NET   | `XmlNode.SelectNodes(user)`, `XPathNavigator.Evaluate(user)` |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param / header /
body / path param, or data carried via state (DB / session / file). If the source is a constant or system-controlled value,
do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- parameterized XPath (e.g., `XPathExpression.setXPathVariableResolver`) — the user input is bound as a variable, not concatenated into the expression
- the XPath string is hard-coded and only the document being queried is user-supplied — that is an XXE / XML-parsing concern, not XPath injection
- XSLT transformations with user-controlled stylesheets — out of scope here

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
