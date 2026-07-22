# Nbrag Retrieval Context

This context defines the retrieval-result concepts that agents use to turn a ranked hit into sufficient source evidence.

## Language

**Context Expansion Guidance**:
A stable result entity that explains when the returned evidence is bounded and which returned handles can obtain the needed surrounding evidence. It guides a conditional follow-up decision; it does not require a follow-up call.
_Avoid_: mandatory expansion, optional hint

**Evidence Boundary**:
The limit of source evidence visible in one result: a chunk stops at its chunk boundary and a raw excerpt stops at its configured context budget. Evidence beyond either limit requires a follow-up read when it is needed for the answer, quotation, or verification.
_Avoid_: complete source context, automatic follow-up

**Broad Context Window**:
A 500-line original-text read bounded by a selected start and end line. A small prior range does not determine the window; precise quotation, field, or line requests are the only exception.
_Avoid_: semantic closure, hit-sized read, arbitrary small window
