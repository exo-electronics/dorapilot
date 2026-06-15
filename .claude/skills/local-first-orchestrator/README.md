# Local-First Code Orchestrator

**Minimize Claude token usage by delegating code editing to local GPU models and reviews to local CPU models.**

## Quick Start (30 seconds)

```bash
cd /path/to/your/repo
bash <(curl -s https://your-host/bin/init-local-first.sh)
```

Or manually:
```bash
cd /path/to/your/repo
bash ~/RTX3090/bin/init-local-first.sh
make start-local
make test-local
```

## What it does

| Stage | Who | Model | Cost |
|-------|-----|-------|------|
| 1. Plan | Claude | (you) | 200 tokens |
| 2. Edit | Local GPU | vLLM 80B | $0.0001 |
| 3. Review | Local CPU | llama.cpp 70B | $0.00001 |

**Total per code change: 200 tokens + $0.0002.** (vs 12,000 tokens if you edited & reviewed in Claude)

## Files

- **SKILL.md** — Full orchestration workflow (read this first)
- **SETUP.md** — Hardware setup & model installation guide
- **README.md** — This file

## Commands

### One-time setup
```bash
bash ~/RTX3090/bin/init-local-first.sh
```

### Start local services
```bash
make start-local
# or
bash ~/RTX3090/bin/init-local-first.sh --start
```

### Test readiness
```bash
make test-local
# Verifies vLLM, llama.cpp, LiteLLM are all online
```

### Check status
```bash
make status-local
```

## How to use in Claude Code

1. **Initialize:** `bash ~/RTX3090/bin/init-local-first.sh`
2. **Start services:** `make start-local`
3. **Open Claude Code** in this repo
4. **Ask for a code change:** "Add a new function that..."
5. **The skill auto-triggers:**
   - Claude plans the change
   - vLLM (GPU) edits the code
   - llama.cpp (CPU) reviews it
   - Claude gives final approval

That's it! You just saved 98% of your token budget.

## Troubleshooting

### Services won't start
```bash
# Check if you have the required models
ls ~/models/Qwen3-Coder-Next-80B-AWQ/  # GPU editor
ls ~/models/DeepSeek-R1-Distill-Llama-70B-GGUF/  # CPU reviewer

# Download if missing
make install-models  # (if your repo has this target)
```

### LiteLLM returns 401
```bash
# Check the auth key in ~/.litellm-local-first.yaml
curl -H "Authorization: Bearer sk-local-dev-only" \
  http://localhost:8002/v1/models
```

### vLLM out of memory
```bash
# Reduce context or tensor parallelism
export VLLM_TP=1
make start-local
```

### Still need help?
```bash
tail -f ~/.local-first-logs/vllm.log
tail -f ~/.local-first-logs/llamacpp.log
tail -f ~/.local-first-logs/litellm.log
```

## Architecture

```
Your repo
├── .claude/skills/
│   └── local-first-orchestrator/
│       ├── SKILL.md         ← Orchestration workflow
│       ├── SETUP.md         ← Hardware guide
│       └── README.md        ← This file
│
Claude Code invokes skill
├── Stage 1: Plan (Claude, 200 tokens)
├── Stage 2: Edit (vLLM, local GPU)
├── Stage 3: Review (llama.cpp, local CPU)
└── Final gate (Claude, approval)
```

## Customization

### Use different models
Edit `~/.litellm-local-first.yaml`:
```yaml
- model_name: local-editor
  litellm_params:
    model: openai/my-custom-gpu-model
    api_base: http://localhost:8000/v1
```

### Adjust context size
```bash
export LLAMACPP_CONTEXT=4096  # Reduce to 4K if RAM is tight
make start-local
```

### Use Ollama instead of llama.cpp
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull deepseek-r1-distill-llama-70b:latest

# Start
ollama serve
```

Then update `~/.litellm-local-first.yaml` to point to `http://localhost:11434/v1`.

## For repo maintainers

To add this skill to your repo:

1. Copy these files to `.claude/skills/local-first-orchestrator/`:
   - `SKILL.md`
   - `SETUP.md`
   - `README.md`

2. Add to your Makefile:
   ```makefile
   include ~/.local-first-orchestrator/Makefile.local-first
   ```

3. Add to your `.gitignore`:
   ```
   .claude/skills/local-first-orchestrator/.progress.jsonl
   ~/.local-first-logs/
   ```

## License & Credits

This orchestrator was designed to minimize Claude API usage by delegating to local open-source models (vLLM, llama.cpp, Ollama). Inspired by ASPICE V-model gates and cost-aware delegation.

Built for safety-critical & automotive codebases but works with any repo.
