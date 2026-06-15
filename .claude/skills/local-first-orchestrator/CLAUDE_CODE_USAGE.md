# Using Local-First Orchestrator in Claude Code

**Yes! This skill runs automatically inside Claude Code. No extra commands needed.**

## How it works

### Step 1: Start services (once per session)

In your terminal:
```bash
cd ~/pilot/openpilot  # or your repo
make start-local
make test-local       # Verifies everything is online
```

This starts:
- **vLLM** (GPU editor) at :8000
- **llama.cpp** (CPU reviewer) at :8001
- **LiteLLM** proxy at :8002

**Wait for "✅ Local-first orchestrator is ready!" message.**

### Step 2: Open Claude Code

```bash
claude .
# Or in VS Code with Claude extension, just open the folder
```

### Step 3: Ask Claude for a code change

Claude Code (inside the session) will see the `.claude/skills/local-first-orchestrator/SKILL.md` file and **automatically use it** for code changes.

**Examples of prompts that trigger the skill:**

✅ "Add a new function to calculate bearing from lat/lon"
✅ "Refactor the CAN parser to handle extended IDs"
✅ "Write unit tests for the safety check module"
✅ "Add logging to the vision pipeline"
✅ "Fix the memory leak in the buffer pool"

**Examples that DON'T trigger the skill:**

❌ "What does this function do?" (question, not a code change)
❌ "How do I run the tests?" (search/explanation)
❌ "Fix the typo in line 42" (one-liner)
❌ "Explain the architecture" (conceptual, not implementation)

### Step 4: Watch Claude delegate the work

**In Claude Code's conversation:**

```
You: "Add error handling to the CAN bus reader"

Claude:
✅ Stage 1: Planning
  └─ Claude decides what needs to change

✅ Stage 2: Editing
  └─ vLLM (GPU) writes the code
  └─ Expected time: 10-30 seconds

✅ Stage 3: Review
  └─ llama.cpp (CPU) checks for bugs
  └─ Expected time: 20-60 seconds

✅ Stage 4: Approval
  └─ Claude gives final sign-off
  └─ Changes are ready

Total tokens used: 200 (planning + approval only)
Total time: ~1-2 minutes
Cost: ~$0.002
```

You'll see Claude's reasoning:
- "Planning the change..."
- "Delegating to local GPU editor..."
- "Waiting for local CPU reviewer..."
- "All checks passed, applying changes"

### Step 5: Review the changes

Claude will show you the diffs:
```diff
+ def can_error_handler():
+     """Handle CAN bus errors gracefully"""
+     try:
+         # error handling code
+     except CANError as e:
+         logger.error(f"CAN error: {e}")
```

Approve or ask for adjustments.

---

## Real Example Workflow

```
Terminal 1: Start services
$ make start-local
$ make test-local
✅ Local-first orchestrator is ready!

Terminal 2: Open Claude Code
$ claude .
(Claude Code window opens)

Claude Code:
(you type) "Add a new safety check that verifies GPS is locked before allowing autonomous mode"

Claude:
📋 I see you need a code change. Local-first orchestrator is available!
🚀 Delegating to local models:

[Stage 1] Planning...
  - New file: safety/gps_check.py
  - New function: verify_gps_locked()
  - Integration point: selfdrive/car.py

[Stage 2] Editing...
  - vLLM writing code... [████████░░] 85% done
  - ~15 seconds elapsed

[Stage 3] Reviewing...
  - llama.cpp checking for bugs... [██████░░░░] 60% done
  - ~30 seconds elapsed

[Stage 4] Approval...
  ✅ All checks passed
  ✅ Code follows safety patterns
  ✅ No memory leaks detected

Here are the changes:

<shows diffs>

Ready to apply? (y/n) y

✅ Changes applied successfully!
Tokens used: 200 (plan) + 100 (approval)
Cost: $0.003
```

---

## What if you want Claude to do it instead?

Sometimes you want Claude to handle everything (e.g., complex architectural changes, security review):

```
You: "Redesign the authentication system"

Claude:
🔔 This is a complex architectural change.
   Skipping local delegation (too much design work).

I'll handle this myself:
- [do the planning]
- [do the editing]
- [do the review]
- [approve]

(This uses normal Claude tokens, no local delegation)
```

Or explicitly:
```
You: "Add logging // @skip-local-first"

Claude:
✅ Noted. I'll do this entirely myself, no delegation.
```

---

## Checking the skill is working

### During Claude Code session

Claude will mention when delegating:
- "Delegating to local-editor..."
- "Asking local-reviewer to check..."
- "Local models confirmed: ..."

### In your terminal

```bash
# Check services are still running
make status-local

# Watch logs in real-time
tail -f ~/.local-first-logs/vllm.log
tail -f ~/.local-first-logs/llamacpp.log
tail -f ~/.local-first-logs/litellm.log

# Monitor GPU usage
nvidia-smi -l 1  # Update every 1 second
```

---

## Troubleshooting

### "Local models not found" error in Claude

**Fix:**
```bash
# Ensure services are running
make status-local

# If not running:
make start-local
make test-local

# Then refresh Claude Code session (close & reopen)
```

### vLLM crashes during editing

The skill has **automatic fallback**: if GPU fails, llama.cpp takes over.

```bash
# Check logs
tail -f ~/.local-first-logs/vllm.log

# Common fixes:
# 1. Reduce context
export LLAMACPP_CONTEXT=4096

# 2. Reduce tensor parallelism
export VLLM_TP=1

# 3. Restart
make start-local
```

### Edits seem wrong / review too lenient

This is expected—local models are smaller and faster than Claude, not perfect.

**Trigger escalation:**
```
You: "Review this more carefully and fix any issues"

Claude:
✅ I'll skip local models and review this myself.
   (uses full Claude reasoning)
```

### Using the skill in other repos?

Just copy the files:
```bash
cd ~/another-repo
mkdir -p .claude/skills/local-first-orchestrator
cp ~/RTX3090/.claude/skills/local-first-orchestrator/* \
   .claude/skills/local-first-orchestrator/
cp ~/RTX3090/Makefile.local-first .
cp ~/RTX3090/bin/init-local-first.sh bin/

make start-local
make test-local
claude .
```

---

## Key Takeaways

✅ **Automatic:** Skill triggers on code changes, no manual invocation
✅ **Transparent:** Claude shows you what's happening
✅ **Fallback:** If local models fail, Claude handles it
✅ **Cost:** 98% token reduction for typical edits
✅ **Speed:** Instant local processing, no cloud wait

**Start using it:**
```bash
make start-local  # 2-3 min first time
claude .
<ask for a code change>
```

Done! 🚀
