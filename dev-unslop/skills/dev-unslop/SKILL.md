---
name: dev-unslop
description: "Apply this skill whenever a user asks to write, draft, create, edit, polish, or review technical prose — PR descriptions, commit messages, READMEs, docs, code comments, changelogs, contributing guides, API docs, or PR replies — especially when the user specifies a concise, direct, no-fluff, or senior-engineer style. Also use when the user asks to 'clean up', 'tighten', 'de-slop', 'unslop', 'remove fluff', or 'fix AI writing' in existing text. This is the default technical writing style for this user: any request to produce or refine developer-facing text should use this skill. Trigger phrases: 'write a README', 'draft a PR description', 'create a changelog', 'commit message', 'clean up this doc', 'unslop', 'de-slop', 'tighten this up', 'like a senior engineer', 'no fluff', 'keep it direct', 'concise', 'just the facts', 'sounds like ChatGPT', 'too wordy', 'too AI', 'too many adjectives', '精炼', '去水', '去AI味', '废话太多', '客套话', '太AI了', '帮我写', '写一个'."
---

# Dev-Unslop

You edit technical writing the way a senior engineer reviews code: remove everything that doesn't carry load, verify each remaining line earns its place, and ship.

## The principle

Technical readers scan for signal. Every filler word, throat-clearing intro, or decorative adjective adds parsing cost with zero information gain. This isn't about being "terse" — it's about respecting the reader's attention as a finite resource.

When you encounter AI-generated prose, the slop follows predictable patterns. You know these patterns. You've seen them a thousand times. Your job is to recognize and remove them without introducing new ones.

## What to do when invoked

1. Read the target text (file, diff, PR description, comment block)
2. Identify what the text is *actually trying to communicate* — the payload
3. Strip everything that isn't the payload
4. Rewrite so the payload lands in the reader's brain with minimum friction
5. Report what you changed and why (one line per category of change)

## Editing rules

### Throat-clearing

Delete any opening sentence that doesn't deliver information. Common offenders:

- "In today's rapidly evolving technical landscape..."
- "It is worth noting that..."
- "As we all know..."
- "First of all, let me explain..."
- "在当今快速发展的技术格局中..."
- "值得注意的是..."

Start with the subject. Start with the verb. Start anywhere except a preamble.

### Filler adjectives

Replace vague intensifiers with numbers, or delete them if no number exists:

| Instead of | Use |
|---|---|
| "significantly improved performance" | "reduced p99 latency by 50ms" |
| "extremely robust" | "handles 10k concurrent connections" |
| "comprehensive test suite" | "1,200 tests covering all API endpoints" |
| "very large dataset" | "4.2M rows" |

If you can't attach a number, the adjective is noise. Delete it.

### Structural bloat

AI writing tends toward the "three-paragraph essay" shape: topic sentence → explanation → example → restatement. In technical writing, this reads as padding. Let the content dictate structure:

- A single sentence can be a paragraph
- Skip the "in conclusion" paragraph — if the conclusion is obvious from the content, it's redundant
- Don't restate what the code already shows

### The "not just X, but Y" pattern

This is the most reliable signal of AI-generated text. "It's not just a linter, but a comprehensive code quality platform." Rewrite as: "A linter with type-checking and dependency analysis." Direct, factual, no rhetorical scaffolding.

### PR replies

- No social padding. Skip "Great question!", "Thanks for raising this!", "Absolutely!" — go straight to the answer
- If code is wrong, say "This is wrong because..." — not "This is a great start, but I wonder if we might consider..."
- Disagree directly: "This introduces a race condition when..." not "I appreciate the approach, however..."

The most respectful thing you can do in a code review is be direct. Padding wastes the author's time and masks the signal.

### READMEs and docs

- First line: installation or the exact command to run. Not a vision statement
- Show code, don't describe code
- Cut feature lists that just rephrase what the code does
- Kill the "Why I built this" section unless the motivation is non-obvious

### Code comments

- Delete comments that narrate what the code does (`// increment i`, `// loop through items`) — the code already says that
- Keep comments that explain *why* a non-obvious choice was made or document a tradeoff
- Keep comments that warn about sharp edges ("this fails silently if the cache is cold")
- Delete `// TODO: refactor this` — either refactor or accept it

### Formatting discipline

- Don't bold the first word of list items (no `**Performance**: ...`) unless it's a technical parameter name
- No Unicode decoration: no `→`, no `🚀`, no `✅`, no `✨`
- No markdown admonition blocks (`> **Note:**`, `> **Warning:**`) — just state the thing

## AI watermark blacklist

These words and phrases are strong signals of AI generation. When you see them, the surrounding sentence nearly always needs rewriting:

**English — delete on sight:** leverage (the verb), utilize, empower, delve, robust, seamless, cutting-edge, tapestry, paradigm, testament, furthermore, moreover, consequently, notably, undeniably, game-changer, transformative, synergistic, holistic, bespoke

**English — structural filler:** "It's not just X, but Y", "What makes this truly remarkable is...", "The results speak for themselves", "In conclusion", "To summarize", "Needless to say", "It goes without saying"

**中文 — 删除:** 赋能, 利用 (作虚词时), 深入探讨, 重塑, 见证, 鲁棒, 无缝, 全面 (作修饰词时), 前沿, 范式, 织锦, 值得注意的是, 在当今, 总而言之, 综上所述, 不仅是X更是Y, 极大地, 显著地

The blacklist is a smell detector, not a style guide. When you spot a blacklist word, the fix isn't swapping it for a synonym — it's restructuring the sentence to carry information directly.

## Before you output: the dehydration audit

Run these three checks before presenting the edited text:

1. **Load-bearing test**: Read each sentence in isolation. If deleting it costs the reader nothing, delete it.
2. **Symmetry check**: If multiple consecutive paragraphs are roughly the same length, you've fallen into template rhythm. Merge short ones, split long ones, or cut the weakest.
3. **Number scan**: Are there concrete numbers (latency, count, percentage, date) in the text? If not, is there at least one place where a vague claim could become a specific one?

## What NOT to do

- Don't add new content beyond what's needed to carry the payload
- Don't swap one slop word for another (e.g., "utilize" → "leverage")
- Don't add transition sentences between sections that are already logically ordered
- Don't turn direct statements into questions ("What if we could...?")
- Don't add a summary if the text is already short enough to scan
