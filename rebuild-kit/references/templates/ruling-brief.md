# Template: guide/briefs/OQ-nnn-ruling-brief.md

One page. Everything needed to rule well without opening the legacy tree. Generated when the
OQ is filed; the six human touchpoints all deserve this treatment — rulings get faster AND
better when the decider actually understands.

```markdown
# Ruling needed: OQ-007 — <one-line question>

**What's being decided.** <2-3 sentences: the behavior in question, in domain language.>

**Why it's ambiguous.** <the conflict itself>
- Reading A: <plain-language> — evidence: `legacy/...:41` <quoted snippet if short>
- Reading B: <plain-language> — evidence: <citation / trace>

**Where it bites.** Affected flows: <flow names, guide/flows/ links>. Blocks: <WO list or
"nothing — flags gate review">. Usage: <weight/traffic context if known>.

**Options & consequences.**
1. <option> → <consequence for users / migration / risk>
2. <option> → <consequence>
3. Defer → <what stays blocked, what risk accrues>

**Recommendation (non-binding).** <if the evidence leans, say so and why — the human rules.>

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
```
