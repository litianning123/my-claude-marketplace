# Karpathy Behavioral Guardrails (Phase 5 — Opt-in)

Fetch the four principles from: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md

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
2. Fetch the Karpathy guidelines from the source URL above (WebFetch; fall back to asking the user to paste if unavailable)
3. Merge — do NOT blindly append:
   - **Deduplicate**: if the user already has a rule covering a principle, skip it
   - **Preserve** existing rules verbatim — never rephrase or reorder
   - **Add only what is genuinely new** — label added blocks clearly
   - Produce structured output under `## Coding discipline` / `## Task execution` / `## Change scope`
4. Show the full merged result + diff summary. Wait for explicit approval before writing
5. Apply via Plan → Act → Verify

## Note

Opt-in. Offer once if the hit threshold (2+) is met. If declined, do not offer again in this session. Governed by SOSA rules — no writes without explicit approval.
