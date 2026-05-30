---
name: debug-mantra
description: Four-mantra debugging discipline — reproduce, trace the fail path, falsify the hypothesis, cross-reference every breadcrumb. Recite the mantra block verbatim at the start of any debugging session, then apply the four steps in order before proposing any fix. Trigger on /debug-mantra and proactively whenever debugging starts — user reports a bug, says something is broken/throwing/failing, asks to debug/diagnose/investigate an issue, or pastes a stack trace or error log.
---

# Debug Mantra

Four-step discipline for any debug session. Recite verbatim, then apply in order.

## Recite this — verbatim, as the first thing in your first response

> **Mantra:**
> 1. **First is reproducibility.** Can the issue be reproduced reliably?
> 2. **Know the fail path.** Debugger first; then source trace + knob enumeration; then in-code instrumentation.
> 3. **Question your hypothesis.** What would disprove it?
> 4. **Every run is a breadcrumb.** Cross-reference all of them.

Then begin work.

---

## 1. Reproduce reliably

Build a runnable repro before anything else.

- **Reliable repro** → capture the exact steps, inputs, and environment as a runnable artifact: failing test, script, recorded data replay, or minimal harness.
- **Flaky repro** → the bug is not yet debuggable. Raise the rate first: loop the trigger, replay the same inputs repeatedly, inject timing stress, narrow ordering windows. 50% flake is debuggable; 1% is not.
- **No repro at all** → stop. Say so explicitly. Ask for logs, captured data, or permission to instrument. Do **not** proceed to hypothesise.

Target: a fast, deterministic pass/fail signal. Replay recorded data rather than live runs where possible; isolate to the smallest reproducible scope (single package, single node, single test).

## 2. Know the fail path

Once reproducible, find *where* the code breaks and *what stops it from breaking*. Try in this order — escalate only when the prior tactic fails.

1. **Attach a debugger or check health output first.** If the system has a diagnostics/health channel (e.g. `/diagnostics` in ROS2), read it before diving into source. One structured health report beats ten log searches.

2. **Source trace + knob enumeration.** Trace the code path end-to-end and list every knob that can influence the outcome:
   - Config values (`.param.yaml`, env vars, launch args, feature flags)
   - Branch conditions, input shape, timing, concurrency
   - For pub/sub or pipeline systems: follow the data from publisher to consumer, step by step
   
   Each knob is a candidate axis to flip. Flip one at a time.

3. **In-code instrumentation.** If outside knobs can't move the failure, go inside: log statements at the suspected fail site, dump the relevant internal state. Tag every probe with a unique prefix (e.g. `[DBG-a4f2]`) so cleanup is a single grep. Let the trace show where reality diverges from your model.

## 3. Falsify the hypothesis

When a candidate root cause surfaces, scrutinise it **before** testing it.

- Does it actually explain the symptom end-to-end? Walk it through.
- What is the simplest **proof**? What is the cleanest **disproof**?
- Run the **disproof first**. If the hypothesis survives, it's real. If it dies, you saved yourself from chasing a phantom.
- Generate 3–5 ranked hypotheses, not one. Single-hypothesis thinking anchors on the first plausible idea.

For safety-critical code (e.g. `src/safety/`): a hypothesis needs a second disproof — the cost of a false "fixed" is a missed emergency stop or spurious intervention.

## 4. Every run is a breadcrumb

Maintain a running **ledger** of every experiment in this session. Each entry: what changed, what happened, what it ruled in or out.

- When a new hypothesis surfaces, walk the ledger. Does it hold for **every** prior observation, not just the most recent?
- If any past run contradicts it, the hypothesis is wrong or incomplete — refine or discard.
- When in doubt, design the **single experiment** whose outcome makes it certain. Run that next.
- Update the ledger after every run.

---

## Operating rules

- Recite the mantra block **once** per debug session, in your first response. Do not re-recite mid-session.
- Recite **verbatim**. Never paraphrase, shorten, or skip lines of the recital.
- If the user says "skip the mantra" → skip the recital but still apply the four steps silently.
- Apply the four steps **in order**:
  - Do not propose a fix before #1 is satisfied (reliable repro exists).
  - Do not start testing hypotheses before #2 has narrowed the fail path.
  - Do not commit to a hypothesis before #3 has tried to disprove it.
  - Do not declare a hypothesis correct until #4 confirms it against every prior breadcrumb.
- If you catch yourself proposing a fix without a reliable repro, stop and return to step 1.
- The mantra is a constraint **you** carry through the session — not advice to deliver back to the user.
