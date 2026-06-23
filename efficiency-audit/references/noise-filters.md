# Noise Filter Reference

Patterns applied automatically during transcript parsing via `_is_noise()` / `NOISE_PATTERNS` in `scripts/scanner.py`. Messages matching any filter are excluded from JSON output and analysis — they are system-generated or pasted output, not real user friction.

## Active Filters

### 1. Context-Compaction Messages

System-injected continuation notices when a session is resumed from a previous conversation. These contain no user intent.

```
this session is being continued from a previous conversation
```

### 2. Command Tags

XML-style tags injected by the harness to communicate with the agent. These are infrastructure, not user messages.

```
^<command-name>
^<command-message>
^<command-args>
^<local-command-stdout>
^<local-command-caveat>
```

### 3. Security Review Boilerplate

Content injected by security-review skills that wraps the agent's context with review instructions. Detected via:

```
you are a (security reviewer|subagent)
review this change for security vulnerabilities
```

### 4. Code-Review & Skill-Body Injections

System prompts injected by code-review tools and skill loaders. Includes:

```
provide a code review for the given pull request
base directory for this skill
```

### 5. Hook/Skill Context

Context blocks injected by hooks or skills at session start:

```
^## context [-–]
```

### 6. Task-Workflow Messages

When users paste tool/test output back into the conversation for review. Detected via regex:

```
review the (test|script|command|tool|output|run) (run )?output and fix
review the output and fix
```

Additionally, `_is_tool_output_paste()` catches messages that are dominated by pasted shell output:
- Messages that start with a fenced code block (` ``` `)
- Messages whose first content line is a shell invocation (`python3`, `bash`, `node`, `./`, etc.) AND contain fewer than 8 distinct conversational English words (excluding common stopwords like "please", "this", "that")

### 7. Subagent Dispatch Messages

Messages originating from workflow orchestration and subagent dispatch systems. Captured by the subagent pattern in filter #3 (`you are a subagent`) and by the general tool-output detection in filter #6.

## How Filters Are Applied

Filters run inside `scanner.parse_session()` on every user message before it enters the analysis pipeline:

```python
if content and not _is_noise(content):
    session.user_messages.append(...)
```

Filtered messages are silently dropped — they never reach `patterns.analyze()` and never appear in findings or recommendations.

## Adding a New Filter

When new noise formats appear in transcripts, add their signature to `NOISE_PATTERNS` in `scripts/scanner.py`:

```python
NOISE_PATTERNS = [
    # ... existing patterns ...
    r"your new noise pattern here",
]
```

Guidelines:
- Use `re.search` semantics (match anywhere in the string)
- Match against lowercased text
- Prefer specific patterns over broad ones — a filter that's too greedy will suppress real user friction
- Add a comment labeling which category the pattern falls under
- Re-run the audit after adding to confirm the false positive is gone
