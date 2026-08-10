# Stable Retrieve Follow-Up Guidance

`nbrag_retrieve` emits one context-expansion guidance entity in every successful result before its evidence data. The entity distinguishes chunk and auto-expanded-original-text boundaries and maps the returned handles to three expansion paths, so agents can expand when the answer, quotation, or verification needs source text outside the shown boundaries. A conditional or per-hit hint was rejected because it makes a public agent-facing contract unstable and easy to miss.
