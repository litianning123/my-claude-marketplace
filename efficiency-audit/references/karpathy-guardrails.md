# Karpathy Behavioral Guardrails (Phase 5 — Opt-in)

Four coding discipline principles that prevent common LLM mistakes. The audit scans correction/context patterns for evidence of violations, then offers to merge the relevant principles into CLAUDE.md.

Source: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md

## The Four Principles

1. **Think Before Coding** — State assumptions before acting. Stop and ask when ambiguous. Flag with `[ASSUMED: ...]`.
2. **Simplicity First** — Write only what was asked. No speculative features, unnecessary abstractions, or unrequested configurability.
3. **Surgical Changes** — Touch only files the task requires. Don't refactor, reformat, or "improve" adjacent code. Note unrelated issues but don't fix them.
4. **Goal-Driven Execution** — Define a verifiable success criterion before starting. Don't claim completion until the outcome is observable.

## Evidence Detection

Scan `corrections` and `missing_context` example strings for these signal keywords (case-insensitive, substring match):

| Signal keywords | Maps to guardrail |
|----------------|-------------------|
| "assumed", "don't guess", "should have asked", "clarify first" | Think Before Coding |
| "over-engineered", "too much", "didn't ask for", "not requested" | Simplicity First |
| "unrelated", "why did you change", "only change X", "didn't touch" | Surgical Changes |
| "does it work", "actually test", "didn't verify", "not confirmed" | Goal-Driven Execution |

Each matching example = 1 hit. Accumulate across all finding groups. Minimum threshold: **2 hits** to offer.

## Offer Templates

**One guardrail triggered:**
> "The audit found [N] corrections about [pattern] — the [Guardrail Name] principle directly addresses this. Merge it into CLAUDE.md?"

**Multiple guardrails triggered:**
> "The audit found evidence for [N] guardrails: [list with counts]. Merge the relevant ones into CLAUDE.md?"

## Merge Procedure

1. Read the user's current CLAUDE.md (global or project-level, based on routing)
2. Fetch the Karpathy guidelines from the source URL (WebFetch). Fall back to the principles above if unavailable
3. Merge — do NOT blindly append:
   - **Deduplicate**: if the user already has a rule covering a principle, skip it
   - **Preserve** existing rules verbatim — never rephrase or reorder
   - **Add only what is genuinely new** — label added blocks clearly
   - Produce structured output under `## Coding discipline` / `## Task execution` / `## Change scope`
4. Show the full merged result + diff summary. Wait for explicit approval before writing
5. Apply via Plan → Act → Verify

## Note

This is an **opt-in** phase. Offer once if the hit threshold (2+) is met. If declined, do not offer again in this session. Governed by the same SOSA rules as Phase 4 — no writes without explicit approval.
