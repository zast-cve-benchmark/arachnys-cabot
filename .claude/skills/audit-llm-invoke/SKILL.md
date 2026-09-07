---
name: audit-llm-invoke
description: Audit endpoints with llm-invoke capability. Produces prompt-injection findings.
---

# Role

Specialist for **prompt-injection**.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `llm-invoke`.

# SINK patterns

| SDK | SINK |
|---|---|
| OpenAI (any lang) | `client.chat.completions.create(messages=[...with user...])`, `client.responses.create(input=user)` |
| Anthropic | `client.messages.create(messages=[..., {"role": "user", "content": user}])` |
| LangChain | `LLMChain.run(user)`, `Agent.run(user)`, `ChatPromptTemplate.from_messages([...]).format_messages(user_input=user)` |
| Vertex AI / Google | `model.generate_content(user)`, `chat.send_message(user)` |
| HuggingFace / local | `pipeline(user)`, `model.generate(input_ids=tokenize(user))` |

Key criterion: user input is passed directly to the LLM as a prompt, or concatenated
into a system prompt / instructions, with no structured sandbox (e.g. tool-use schema
constraints, output filter).

# Safe context (false-positive prevention)

Do NOT report:

- LLM calls whose entire prompt traces back to hard-coded constants / templates with no
  user-controlled substitutions
- Calls where user input is passed only as a structured tool-call argument whose schema
  the model output is validated against (no free-form prompt slot)
- Calls whose output is enum-constrained / regex-validated before any downstream use, AND
  the LLM has no side-effecting tool access

Out-of-scope categories belong to other audit skills — arbitrary code eval
-> `audit-code-eval`. If you spot them, mention them in your report and let the
orchestrator dispatch the right specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
