---
name: local-first-orchestrator
description: Hardware-aware code orchestration that minimizes Claude tokens by delegating to local vLLM (GPU) + llama.cpp (CPU). Auto-escalates to Claude only when needed. Works on any repo.
---

# 🚀 Local-First Code Orchestrator v2

**Philosophy:** Local models do 100% of the work they can. Claude is the safety gate, not the workhorse.

---

## When to invoke

Auto-trigger when:
- ✅ User asks for a **code change** (edit, test, refactor, add feature)
- ✅ Local stack is online (`http://localhost:8002/v1/models` responds)
- ✅ File is in the repo (not external)

Auto-skip when:
- ❌ "Explain this code" (question, not change)
- ❌ "What does this do?" (research, not implementation)
- ❌ One-liner changes (typos, comments)
- ❌ User says `// @skip-orchestrator`

---

## 5-Stage Pipeline (Autonomous)

### **Stage 0: Route Decision + Timeout Budget** (Claude, ~50 tokens)

Classify the request and set the timeout budget before calling any local model.

```
User request → Classify task type → Set timeout budget

TIER 1 — Quick fix (one-liner, comment, rename, typo)
  Reviewer:  local-reviewer (DeepSeek-R1-70B @ :8001)
  Timeouts:  GPU=120s, Review=300s
  → Skip to Stage 2 directly (no planning needed)

TIER 2 — Routine (add function, fix bug, write test)
  Reviewer:  local-reviewer (DeepSeek-R1-70B @ :8001)
  Timeouts:  GPU=300s, Review=900s
  → Stage 1 local planning, then Stage 2

TIER 3 — Moderate (refactor, new feature, new module)
  Reviewer:  local-reviewer (DeepSeek-R1-70B @ :8001)
  Timeouts:  GPU=600s, Review=1800s
  → Stage 1 local planning, Claude validates plan

TIER 4 — Deep (architecture, security, auth, API design)
  Reviewer:  local-reviewer (DeepSeek-R1-70B @ :8001)
  Timeouts:  GPU=600s, Review=2400s
  → Stage 1 Claude planning required, Claude approves result

Unknown complexity → start at TIER 2, escalate if reviewer flags issues
```

**Classification rules:**
- Lines changed ≤ 5, no logic change → TIER 1
- Bug fix / test / small feature → TIER 2
- Refactor / new class / new module → TIER 3
- Security, auth, crypto, API, architecture → TIER 4
- User flag `// @deep` → force TIER 4
- User flag `// @fast` → force TIER 1

---

### **Stage 1: Strategic Planning**

#### **Path A: Local Planning (routine work)**
```
Model: llama.cpp (70B reasoning, CPU)
Input: User request + affected files
Output: plan.md with:
  - What files change
  - Why each change
  - Success criteria
  
Gate: Does plan make sense?
  ✅ PASS → Continue to Stage 2
  ❌ FAIL → Escalate to Claude Planning (Path B)
```

#### **Path B: Claude Planning (complex work)**
```
Model: Claude Sonnet (cloud)
Input: User request + files + local plan (if any)
Output: High-level strategy
Cost: 200 tokens

Gate: Is strategy approved?
  ✅ PASS → Continue to Stage 2
  ❌ FAIL → Ask user for clarification
```

---

### **Stage 2: Code Generation**

```
Model: vLLM (80B GPU, or llama.cpp CPU fallback)
Input: plan.md + affected files + context
Output: diffs (code changes only, no explanation)

Optimization:
  - Parallel generation if 3+ files
  - Streaming output (don't wait for full response)
  - Cache recently-viewed files
  
Gate: Do diffs match the plan?
  ✅ PASS → Continue to Stage 3
  ⚠️  PARTIAL → Review & fix (Stage 3)
  ❌ FAIL → Regenerate with more context
```

---

### **Stage 3: Quality Review** (Parallel — reviewer chosen by Stage 0 tier)

```
Reviewer: local-reviewer (DeepSeek-R1-70B Q8_0 @ :8001, ~2-4 tok/s)
Always the 70B — one model, always loaded, quality-first.

Run 3 checks in parallel:

3a. Correctness Review
  Model: (tier-chosen reviewer)
  Check: Logic errors, off-by-one, edge cases, memory leaks
  Output: PASS / MUST-FIX (max 3 issues)

3b. Completeness Review
  Model: (tier-chosen reviewer)
  Check: Does it implement the entire plan?
  Output: PASS / INCOMPLETE

3c. Safety Review (if code touches: auth, crypto, core logic)
  Model: Claude (cloud, ~100 tokens)
  Check: Security issues, dangerous patterns
  Output: PASS / BLOCK

Timeout: use the budget set in Stage 0 (180s / 600s / 1200s / 2400s)
If review times out: log timeout, report partial findings, ask user to continue.
```

**Gate Logic:**
```
If all PASS
  → Continue to Stage 4 (Apply)
  
If any MUST-FIX (≤3 issues)
  → Loop back to Stage 2 with feedback
  → Max 2 loops, then escalate
  
If INCOMPLETE
  → Generate missing code (Stage 2)
  
If BLOCK
  → Escalate to Claude for security review
```

---

### **Stage 4: Apply & Verify**

```
Apply diffs to files
Run: make test (or repo's test command)

If tests PASS
  → Success! Show summary
  
If tests FAIL
  → Show error output
  → Ask user:
     a) Fix it yourself?
     b) Have local models fix it? (loops to Stage 2)
     c) Escalate to Claude?
```

---

## Advanced Modes

### **1. Batch Mode** (`// @batch`)
```
You: "Refactor these 10 functions // @batch"

Result:
  ✅ llama.cpp plans all 10 in sequence
  ✅ vLLM generates code for all 10 (parallel)
  ✅ llama.cpp reviews all 10 (parallel)
  → Show summary with cost/time

Cost: ~0 tokens (all local)
Time: 2-5 minutes
```

### **2. Autonomous Mode** (`// @autonomous`)
```
You: "Fix all linting errors // @autonomous"

Result:
  → Local models run the entire pipeline
  → Apply changes automatically
  → No Claude review
  → Only escalate if errors occur
  
Use case: Routine maintenance, cleanup, boring refactors

Cost: ~0 tokens
Risk: Low (just lint fixes)
```

### **3. Reasoning Mode** (`// @reason`)
```
You: "Why is this function slow? Fix it // @reason"

Result:
  → llama.cpp (70B reasoning model) analyzes performance
  → Generates optimization
  → Reviews the fix
  → Reports findings + changes
  
Cost: ~0 tokens (all reasoning happens locally)
```

### **4. Expert Mode** (`// @expert`)
```
You: "Design a new auth system // @expert"

Result:
  → Claude plans (strategic decisions)
  → llama.cpp implements (detail work)
  → Claude reviews (final gate)
  → Claude approves (signature)
  
Cost: 300 tokens (planning + approval only)
Work done by: Local models (90%)
```

---

## Token Budget by Mode

| Mode | Planning | Coding | Review | Approval | **Total** | **Use Case** |
|------|----------|--------|--------|----------|----------|-------------|
| **Autonomous** | Local | Local | Local | Local | **0** | Lint, refactor, routine |
| **Local-First** | Local | Local | Local | Claude | **50** | Features, tests, bugs |
| **Balanced** | Claude | Local | Local | Claude | **300** | Default, safe mode |
| **Expert** | Claude | Local | Claude | Claude | **300** | Architecture, security |
| **Claude-Only** | Claude | Claude | Claude | Claude | **3,300** | Complex reasoning (rare) |

---

## Escalation Rules

**Auto-escalate to Claude when:**

1. **Security concerns** — Anything touching auth, crypto, permissions
2. **Architectural changes** — New patterns, APIs, major refactors
3. **Local model loops >2** — Can't fix the issue themselves
4. **Tests fail repeatedly** — Logic error too complex for local
5. **User explicitly asks** — `// @claude` or "You handle this"
6. **Complexity score >8/10** — Subjective assessment of task difficulty

**Never escalate (always use local):**
- Linting, formatting, simple renames
- Test additions for existing code
- Documentation updates
- Dependency bumps

---

## Real-Time Cost Tracking

After each change, show:
```
📊 Cost Breakdown:
   Tokens used: 50 (planning)
   Claude cost: $0.0005
   Local cost: $0.00 (free)
   Total: $0.0005
   
   Saved: $0.029 vs traditional
   Time: 2 min 15 sec (instant local + brief review)
```

---

## Smart Fallbacks

If vLLM (GPU) crashes:
```
User: "Refactor this function"
  → vLLM failed to respond
  → Automatically use llama.cpp (CPU)
  → User sees: "Using CPU editor (auto-fallback)"
  → Changes still apply, same quality
```

If llama.cpp (CPU) crashes:
```
User: "Add tests"
  → llama.cpp review failed
  → Escalate to Claude for review (safe)
  → User sees: "Local reviewer down, using cloud backup"
```

---

## Session Memory & Context

Maintain per-session:
- Files already reviewed (don't re-review)
- Decisions made (don't re-plan)
- Patterns detected (apply automatically)
- Cost tracker (cumulative savings)

```
📋 Session Summary:
   Tasks completed: 7
   Local models handled: 7 (100%)
   Claude used: 1x (only for security review)
   Total tokens: 150 (would be 2,310 traditional)
   Saved: 2,160 tokens ($0.021) ✨
```

---

## Model Loading & Configuration

Models are stored in a shared directory (`~/models/`) and can be loaded by both vLLM and Ollama without duplication.

### **Shared Model Directory Structure**

```
~/models/
├── DeepSeek-R1-Distill-Llama-70B-GGUF/           # CPU reviewer (llama.cpp)
│   └── model.gguf                                 # 74GB, 70B reasoning model
├── Qwen3-Coder-Next-AWQ-Int4/                    # GPU editor (vLLM)
│   ├── model.safetensors                         # Quantized for fast GPU loading
│   └── config.json
└── [other models for Ollama or future use]
```

### **vLLM Loading from ~/models**

vLLM reads models from `~/models/` via the model ID path.

**In `bin/start_vllm.sh`:**
```bash
MODEL_PATH="~/models/Qwen3-Coder-Next-AWQ-Int4"

python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" \
  --quantization awq \
  --gpu-memory-utilization 0.85 \
  --served-model-name local-editor
```

**Environment variable (for CLI or scripts):**
```bash
export VLLM_MODEL_PATH="~/models/Qwen3-Coder-Next-AWQ-Int4"
vllm serve "$VLLM_MODEL_PATH" --quantization awq --served-model-name local-editor
```

### **Ollama Loading from ~/models**

Ollama can import models from `~/models/` and store them in its own registry without re-downloading.

**Import a model into Ollama:**
```bash
# Convert GGUF model and import into Ollama
ollama import ~/models/DeepSeek-R1-Distill-Llama-70B-GGUF/model.gguf deepseek-r1

# Check that it's imported
ollama list
# Output: deepseek-r1     70b     5.0 GB
```

**Use in Ollama:**
```bash
ollama run deepseek-r1 "your prompt"
```

**Serve on different port (if vLLM on :8000):**
```bash
OLLAMA_HOST="127.0.0.1:8001" ollama serve
```

### **Switching Between Tools Without Re-downloading**

Since both vLLM and Ollama point to `~/models/`, no models are duplicated.

**To use only Ollama (CPU-based):**
```bash
# Stop vLLM service
systemctl --user stop vllm-coder

# Configure LiteLLM to use only Ollama
# Update litellm config to skip vLLM endpoints
```

**To use only vLLM (GPU-based):**
```bash
# Start vLLM service
systemctl --user start vllm-coder

# Ensure LiteLLM routes to vLLM first
```

**To use both (recommended):**
```bash
# Both services read from ~/models/ without duplication
# LiteLLM automatically failsover from vLLM → Ollama if GPU unavailable
```

### **Environment Variables for Model Paths**

Set these to control where models are loaded from:

```bash
# In ~/.bashrc or systemd service:
export MODELS_DIR="$HOME/models"
export VLLM_MODEL_PATH="$MODELS_DIR/Qwen3-Coder-Next-AWQ-Int4"
export LLAMACPP_MODEL="$MODELS_DIR/DeepSeek-R1-Distill-Llama-70B-GGUF/model.gguf"
export OLLAMA_MODELS="$MODELS_DIR"  # Tell Ollama where to find imports
```

---

## Configuration

Users can set preferences:

```bash
# In .claude/config.yml:
local-first:
  min-complexity: 3      # Escalate tasks >3 if uncertain
  auto-escalate-security: true  # Always Claude for security
  max-local-loops: 2     # Give up after 2 local attempts
  batch-threshold: 5     # Auto-batch if 5+ files
  safety-gate: claude    # Final approval: "claude" or "local"
```

---

## Exit Conditions

**Stop delegating when:**

1. ✅ Task complete and tests pass
2. ⚠️ Local models fail 2+ times (ask user)
3. 🔒 Security concerns detected (escalate)
4. ❓ Unclear outcome (show findings, ask user)

**Then always show:**
- What changed (diffs)
- Cost savings (vs traditional)
- Time taken
- Next steps

---

## Example Workflows

### **Example 1: Routine refactor**
```
You: "Move the GPS validator to its own module"

Stage 0: Route → Simple change, use local planning
Stage 1: Local planning (llama.cpp) → plan.md ✅
Stage 2: Edit (vLLM) → diffs ✅
Stage 3: Review (llama.cpp) → PASS ✅
Stage 4: Apply & test → PASS ✅

Result:
  ✅ Done in 2 minutes
  💰 Cost: $0 (all local)
  📊 Saved: $0.03 vs traditional Claude
```

### **Example 2: Security-critical change**
```
You: "Add rate limiting to the API"

Stage 0: Route → Security, use Claude planning
Stage 1: Claude planning → strategy ✅
Stage 2: Edit (vLLM) → diffs ✅
Stage 3: Review (llama.cpp + Claude security) → PASS ✅
Stage 4: Apply & test → PASS ✅

Result:
  ✅ Done in 3 minutes
  💰 Cost: $0.003 (planning + security review)
  📊 Saved: $0.027 vs traditional Claude
```

### **Example 3: Batch cleanup**
```
You: "Fix all TODO comments across the codebase // @batch"

Stage 0: Route → Routine, use local
Stage 1: Local planning → find all TODOs
Stage 2: Edit (vLLM, parallel) → all fixes in parallel
Stage 3: Review (llama.cpp, parallel) → all PASS
Stage 4: Apply & test → PASS

Result:
  ✅ 47 TODOs fixed in 4 minutes
  💰 Cost: $0 (all local)
  📊 Saved: $0.47 (would be $0.47+ in Claude)
```

---

## Monitoring & Debugging

View what's happening:
```bash
# Real-time log
tail -f ~/.local-first-orchestrator/session.log

# Session cost breakdown
cat ~/.local-first-orchestrator/costs.json

# Model performance
cat ~/.local-first-orchestrator/metrics.json
```

---

## Summary

**You control the tradeoff:**

- **Maximum savings** (`@autonomous`): 0 tokens, 90% cost savings
- **Maximum safety** (`@expert`): 300 tokens, 90% work delegated
- **Default balance**: 50-100 tokens, ~95% work delegated

**Key principle:** Local models handle 95%+ of work. Claude is the decision-maker and safety gate, not the workhorse.
