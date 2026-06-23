# efficiency-audit — Future Improvements

Ideas identified during source code analysis. Not in scope for v1.

## B: Offline-First Heuristic Synthesis

Replace the Claude CLI dependency in the synthesis step with a template-based heuristic rule engine. Keyed to pattern categories with configurable thresholds. Benefits: deterministic output, zero latency, no API cost, works offline.

## C: Visualization & Historical Trends

- **HTML dashboard** — Static HTML report generated after each audit run with inline charts (session activity timeline, category breakdown, trend vs baseline). No web server needed.
- **SQLite storage** — Persist every audit run to a local SQLite database (stdlib, zero deps). Enables multi-run trend charts, per-session drill-down, and "what changed since last month?" queries.

## D: Multi-Agent Support

Parse transcripts from Codex CLI (JSONL envelope format) and OpenCode (SQLite database) in addition to Claude Code. The reference doc at `references/multi-agent-portability.md` (in source repo) documents the formats — implementation was planned but never built.

## E: Other Ideas

- **Semantic clustering** — Beyond regex: group similar messages by embedding similarity for broader friction detection
- **Configurable thresholds** — Expose detection thresholds (count ≥ N, sessions ≥ M) via config file
- **Cross-project analytics** — Compare friction patterns across multiple projects
- **Write targets beyond CLAUDE.md** — Support MEMORY.md, settings.json, .claude/rules/ for rule application
