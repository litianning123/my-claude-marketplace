# Dev-Unslop

[中文](README.zh-CN.md)

A Claude Code plugin that removes AI-generated slop from technical writing — documentation, PR replies, code comments, READMEs, and commit messages.

## What it does

Detects and removes the predictable patterns of AI-generated prose:

- **Throat-clearing** — preambles that delay the actual content
- **Filler adjectives** — vague intensifiers ("robust", "seamless") replaced with numbers
- **Structural bloat** — the three-paragraph essay shape that pads technical docs
- **AI watermark phrases** — "leverage", "delve", "it's not just X, but Y", and 30+ other signals
- **PR glazing** — social padding ("Great question!") stripped to direct technical discussion

Applies a senior engineer's aesthetic: if a sentence doesn't carry load, it's cut.

## Installation

```bash
# Copy into your Claude Code plugins directory
cp -r dev-unslop/ ~/.claude/plugins/dev-unslop/
```

## Usage

Invoke with any of these phrases:

- "Clean up this README — remove the AI slop"
- "Unslop this PR description"
- "Rewrite this like a senior engineer"
- "Tighten up these code comments"
- "去水 — 把这个文档精炼一下"

The skill reads the target text, strips everything that isn't the payload, and outputs the tightened version with a summary of changes.

## What it won't do

- Won't add new content or elaborate on existing points
- Won't swap one slop word for another synonym
- Won't turn direct statements into rhetorical questions
- Won't add summaries where the text is already scannable
