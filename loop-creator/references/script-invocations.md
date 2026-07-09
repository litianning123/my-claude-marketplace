# Script Invocations

Copy-paste these blocks when generating output. Replace `<placeholder>` values with escaped user answers.

## Escaping Rule

Before substituting user answers, escape `"` → `\"` and `\` → `\\`.

## Shared Preamble

All blocks start with resolving the plugin root:

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
```

---

## Tier Detection

```bash
echo '{"multi_step":<bool>,"stateful":<bool>,"external_tools":<bool>,"human_review":<bool>,"complex_verification":<bool>,"reusable":<bool>}' | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from tier_detector import detect_tier
d = json.loads(sys.stdin.read())
tier, reasoning = detect_tier(d)
print(json.dumps({'tier': tier, 'reasoning': reasoning}))
"
```

Parse JSON. Present: "Based on your answers: {reasoning}. I recommend the **{tier}** tier. Sound good?"

---

## Tier 1: Command

```bash
echo '{"goal":"<goal>","cadence":"<cadence>","context":"<context>","action":"<action>","stop_condition":"<stop>","verify":"<verify>","risk":"<risk>"}' | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_command import generate_command, generate_manual_test_reminder
d = json.loads(sys.stdin.read())
print(generate_command(d['goal'], d['cadence'], d['context'], d['action'], d['stop_condition'], d['verify'], d['risk']))
print()
print(generate_manual_test_reminder())
"
```

Present the command + reminder to user. No files written.

---

## Tier 2: Project

```bash
echo '{"goal":"<goal>","scope":"<scope>","expected_output":"<expected_output>","action":"<action>","verify":"<verify>","safety":"<safety>","cadence":"<cadence>","stop":"<stop>","initial_status":"<initial_status>","output_name":"<output_name>"}' | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_project import generate_all_project_files
d = json.loads(sys.stdin.read())
files = generate_all_project_files(d)
print(json.dumps(files))
"
```

Parse JSON. Ask user where to create the project folder. Write each file.

Then present the manual test prompt:
```
Run the <goal> loop for this workspace.
Follow LOOP_INSTRUCTIONS.md exactly. Read TASK.md and PROGRESS.md first.
Do not modify any files except the allowed output paths.
```

And scheduling:
```
/loop <cadence> Run the <goal> loop. Follow LOOP_INSTRUCTIONS.md exactly.
```

---

## Tier 3: Skill

First, generate project files (same as Tier 2) as the reference implementation.

Then generate the SKILL.md:

```bash
echo '{"goal":"<goal>","trigger_phrases":"<triggers>","description":"<description>","operating_procedure":"<procedure>"}' | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from gen_skill import generate_skill_md, generate_reference_implementation
d = json.loads(sys.stdin.read())
skill = generate_skill_md(d['goal'], d['trigger_phrases'], d['description'], d['operating_procedure'])
print('===SKILL===')
print(skill)
print('===END_SKILL===')
"
```

Write the SKILL.md + reference implementation. Tell user where to place the skill.

---

## Discovery: Scan Transcripts

```bash
PLUGIN_ROOT=$(ls -dt ~/.claude/plugins/cache/*/loop-creator/*/ 2>/dev/null | head -1)
CURRENT_PROJECT=$(git -C "$(pwd)" remote get-url origin 2>/dev/null | sed 's|.*/||; s|\.git$||')
[ -z "$CURRENT_PROJECT" ] && CURRENT_PROJECT=$(basename "$(pwd)")
echo "{\"days\":30,\"project\":\"$CURRENT_PROJECT\"}" | python3 -c "
import sys, json
sys.path.insert(0, '${PLUGIN_ROOT}/scripts')
from discover import scan_sessions
d = json.loads(sys.stdin.read())
candidates = scan_sessions(days=d.get('days', 30), project=d.get('project'))
print(json.dumps(candidates))
"
```

If 0 candidates: "Nothing obvious found in your last 30 days. Want to create a loop from scratch?" → jump to Phase 1.

If 1+ candidates, present each with rank, score, goal, and a one-line evidence summary:

```
Here's what I found in your recent sessions:

1. CI Status Monitor (score 8.5)
   Found you checking CI status in 5 sessions over 14 days.
   Sample: "check if PR #42's CI passed"

2. Daily Project Review (score 6.0)
   Found "every morning" + workspace inspection pattern in 3 sessions.
   Sample: "what changed in the repo since yesterday"

Pick a number, or say "from scratch" to design your own, or "show more."
```

When user picks a candidate, pre-populate Phase 1:

| Q | Discovery mode |
|---|---------------|
| Q1 | "I found you {sample_prompt} across {N} sessions. Create a '{goal}' loop?" |
| Q2 | If cadence_hint set: "I see a {cadence_hint} pattern. Keep that?" If None: ask original Q2 |
| Q3 | If verify_hint set: "You typically verify by {verify_hint}. Use that?" If None: ask original Q3 |
| Q4 | "You access {context_hint or 'local files'}. Anything else?" |
| Q5 | "You usually stop after one check. Escalate on failure?" |
| Q6 | "{risk_hint or 'read-only'}. Any risk I'm missing?" |

Phases 2-3 (Q7-Q11) are asked fresh. "from scratch" → skip to Phase 1. "show more" → re-run with max_candidates=10.
