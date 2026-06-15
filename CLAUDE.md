# CLAUDE.md — dorapilot

Guidance for Claude Code when working on this dorapilot fork.

---

## Local Inference Stack

This workstation runs a two-tier local inference stack. All code changes use local GPU+CPU automatically — no flag needed. Use `// --claude` to skip local and go cloud-only.

```
:8000  GPU  Qwen3-Coder-30B AWQ    (RTX 3090) — code generation, 20-30 tok/s
:8001  CPU  DeepSeek-R1-70B Q8_0   (i9-13900K) — deep review, 2-4 tok/s
:8002  LiteLLM proxy               — unified endpoint, auto-failover
```

Override flags:
```
// --claude   → cloud only (security review, research)
// @deep      → force Tier 4 deep review (architecture, safety-critical)
// @fast      → Tier 1, skip review (trivial changes)
```

| Tier | Type | Review timeout |
|------|------|---------------|
| 1 | rename, comment | 300s |
| 2 | add function, fix bug | 900s |
| 3 | refactor, new module | 1800s |
| 4 | arch, safety, auth | 2400s |

```bash
# Check status
curl -s http://localhost:8002/v1/models \
  -H "Authorization: Bearer sk-local-dev-not-secret" | jq '.data[].id'
# Expected: "local-editor", "local-reviewer"
```

See `~/RTX3090/` for full setup and service management.
