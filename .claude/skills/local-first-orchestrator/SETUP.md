# Setup: Local-First Code Orchestrator

Copy `SKILL.md` to `.claude/skills/local-first-orchestrator/SKILL.md` in your repo to enable token-minimizing local delegation.

## One-time setup (5 min)

### 1. Check your hardware

```bash
python3 << 'EOF'
import subprocess, json, os, psutil

gpu_vram = 0
try:
    out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total",
                                   "--format=csv,noheader,nounits"], text=True)
    gpu_vram = sum(int(x.strip()) for x in out.strip().split('\n')) // 1024
except: pass

cpu_count = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 8
ram_gb = psutil.virtual_memory().total // (1024**3)

print(f"\n🔧 Your hardware:")
print(f"  GPU: {'YES' if gpu_vram else 'NO'} ({gpu_vram} GB VRAM)")
print(f"  CPU: {cpu_count} cores")
print(f"  RAM: {ram_gb} GB\n")

if gpu_vram >= 20 and ram_gb >= 96:
    print("✅ Optimal: Use vLLM (GPU) + Ollama/llama.cpp (CPU)")
elif gpu_vram >= 20:
    print("✅ Good: Use vLLM (GPU). Review will use cloud fallback.")
elif ram_gb >= 32:
    print("⚠️  Limited: Use Ollama/llama.cpp (CPU). Editing will use cloud fallback.")
else:
    print("❌ Insufficient: Use Claude directly (no local delegation).")
EOF
```

### 2. Install models (once, ~2 hours)

**GPU editor** (pick one):
```bash
# Option A: Qwen3-Coder-Next-80B-AWQ (best, requires 2x GPU or 1x GPU + 24 GB offload)
huggingface-cli download Qwen/Qwen3-Coder-Next-80B-AWQ \
  --local-dir ~/models/Qwen3-Coder-Next-80B-AWQ

# Option B: Qwen/CodeQwen-1.5-7B (smaller, fits 1x RTX 3090)
huggingface-cli download Qwen/CodeQwen-1.5-7B-Chat \
  --local-dir ~/models/CodeQwen-1.5-7B-Chat
```

**CPU reviewer** (pick one):
```bash
# Option A: DeepSeek-R1-Distill-Llama-70B (best reasoning, 75 GB RAM)
huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Llama-70B \
  --local-dir ~/models/DeepSeek-R1-Distill-Llama-70B

# Option B: Ollama auto-download (easiest)
ollama pull deepseek-r1-distill-llama-70b:latest
```

### 3. Start services

**vLLM (GPU editor):**
```bash
python3 -m vllm.entrypoints.openai.api_server \
  --model ~/models/Qwen3-Coder-Next-80B-AWQ \
  --served-model-name local-editor \
  --port 8000 \
  --tensor-parallel-size 2 \
  --quantization compressed-tensors \
  --max-model-len 8192 \
  > ~/.vllm.log 2>&1 &
```

**Ollama (CPU reviewer):**
```bash
ollama serve > ~/.ollama.log 2>&1 &
# In another terminal:
ollama run deepseek-r1-distill-llama-70b
```

Or **llama.cpp (CPU reviewer, alternative):**
```bash
~/.llama.cpp/build/bin/llama-server \
  --model ~/models/DeepSeek-R1-Distill-Llama-70B-Q8_0/model.gguf \
  --alias local-reviewer \
  --port 8001 \
  --ctx-size 8192 \
  --threads $(nproc) \
  > ~/.llamacpp.log 2>&1 &
```

**LiteLLM proxy** (routes both endpoints):
```bash
# Create config
cat > ~/.litellm.yaml << 'EOF'
model_list:
  - model_name: local-editor
    litellm_params:
      model: openai/local-editor
      api_base: http://localhost:8000/v1
      api_key: dummy
      timeout: 600

  - model_name: local-reviewer
    litellm_params:
      model: openai/local-reviewer
      api_base: http://localhost:8001/v1
      api_key: dummy
      timeout: 1200

router_settings:
  fallbacks:
    - local-editor: ["local-reviewer"]

general_settings:
  master_key: sk-local-dev-only
EOF

# Start proxy
litellm_proxy --config ~/.litellm.yaml --port 8002 > ~/.litellm.log 2>&1 &
```

### 4. Verify setup

```bash
curl -s http://localhost:8002/v1/models | jq '.data[].id'
```

Expected output:
```
[
  "local-editor",
  "local-reviewer"
]
```

If you see both, you're ready! ✅

---

## Optional: Systemd auto-start (Linux)

Create `~/.config/systemd/user/vllm.service`:
```ini
[Unit]
Description=vLLM API Server
After=network.target

[Service]
Type=exec
ExecStart=/usr/bin/python3 -m vllm.entrypoints.openai.api_server \
  --model /home/USER/models/Qwen3-Coder-Next-80B-AWQ \
  --served-model-name local-editor \
  --port 8000 \
  --tensor-parallel-size 2 \
  --quantization compressed-tensors
Environment="PATH=/usr/local/bin:/usr/bin"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Then:
```bash
systemctl --user enable vllm.service
systemctl --user start vllm.service
systemctl --user status vllm.service
```

Do the same for `llamacpp.service` and `litellm.service`.

---

## Customization

### Use different models

In `SKILL.md`, change `local-editor` and `local-reviewer` model names/endpoints to match your setup:

```python
# Stage 2: your GPU editor
model: local-editor  # Point this to your vLLM/Ollama endpoint at :8000

# Stage 3: your CPU reviewer
model: local-reviewer  # Point this to your llama.cpp/Ollama endpoint at :8001
```

### Adjust context size

If you have limited VRAM, reduce `--max-model-len`:

```bash
# vLLM: 8K context (uses ~20 GB VRAM)
--max-model-len 8192

# llama.cpp: 4K context (uses ~32 GB RAM)
--ctx-size 4096
```

### Use smaller models

If hardware is tight, swap models:

```bash
# Editor (instead of 80B, use 34B)
--model Qwen/CodeQwen-1.5-7B  # 7B, ultra-fast, still good

# Reviewer (instead of 70B, use 32B)
ollama pull mistral:latest  # 7B, lightweight
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Connection refused :8000` | vLLM not started or crashed. Check `~/.vllm.log` |
| `CUDA out of memory` | Reduce `tensor-parallel-size` or `--max-model-len` |
| `Ollama slow / timeout` | Increase CPU threads. Check if model is swapping (use smaller model) |
| `LiteLLM 404 on /models` | Verify vLLM/Ollama are actually listening on :8000/:8001 |

---

## Benchmarks (your hardware)

Approximate tokens/sec and cost:

| Stage | Model | Hardware | Speed | Cost/req |
|-------|-------|----------|-------|----------|
| Edit | Qwen3-80B-AWQ | 2x RTX 3090 | 25 tok/s | $0.0001 |
| Review | DeepSeek-R1-70B-Q8 | CPU (96 GB) | 2 tok/s | $0.00001 |
| Plan | DeepSeek-V4-Pro | Claude cloud | 50 tok/s | $0.01 |

**Total cost per task:** Plan (200 tokens × $0.01) = $0.002. Edit & review are near-free.

---

## Next steps

1. Copy `SKILL.md` to your repo: `cp SKILL.md <your-repo>/.claude/skills/local-first-orchestrator/SKILL.md`
2. Run setup above
3. Create a new Claude Code session in that repo
4. Ask Claude to make a code change — the skill will auto-trigger and delegate to local models
5. Watch your token bill stay near $0 ✨

