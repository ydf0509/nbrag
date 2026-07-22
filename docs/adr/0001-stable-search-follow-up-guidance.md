# Stable Search Follow-Up Guidance

`nbrag_search_and_fetch` emits one context-expansion guidance entity in every successful result before its evidence data. The entity distinguishes chunk and raw-excerpt boundaries and maps the returned handles to three expansion paths, so agents can expand only when the answer, quotation, or verification needs source text outside the shown boundaries. A conditional or per-hit hint was rejected because it makes a public agent-facing contract unstable and easy to miss.
