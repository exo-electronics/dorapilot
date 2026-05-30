---
name: post-mortem
description: Write the canonical engineering record of a fixed bug — root cause, mechanism, fix, validation, and how it slipped through. Engineer-audience, code identifiers welcome. Use after a debug session lands a fix, before closing the ticket. Trigger on /post-mortem, when the user says "write the post-mortem / postmortem / RCA / root cause analysis", "document this fix", "write up the root cause", "close out this bug with a writeup", or hands you a fixed-and-validated bug and asks for the writeup.
---

# Post-mortem

The canonical engineering record of a bug fix. Written **after** debugging lands a real fix, **for** other engineers (and future-you, who will have forgotten everything in 6 months). Code identifiers are welcome here — this is the artifact that lets the next person recover the mental model fast.

For the up-the-org version of this same content, hand the finished post-mortem to [`management-talk`](../../productivity/management-talk/SKILL.md). They compose: post-mortem owns the engineering truth, management-talk reframes it for leadership.

## When to invoke

- "/post-mortem"
- "write the post-mortem / postmortem / RCA / root-cause analysis"
- "document this fix" / "write up the root cause" / "close out this bug with a writeup"
- After a debug session has clearly landed a fix, proactively offer to draft one.

## When NOT to use

- **Bug not fixed yet, or fix not validated.** A post-mortem of a hypothesis is misleading. Refuse and tell the user what's missing.
- **Vehicle-level safety incident / field event.** Those need a separate incident report (timeline, affected systems, notification chain) — not this skill. Flag and confirm before proceeding.
- **Trivial fix** (typo, obvious one-liner). The PR description is the record. Don't manufacture ceremony.

## Required inputs — refuse to draft without these

Before writing a single line, confirm all four. If any are missing, list what's missing and stop:

- [ ] **Reliable repro** exists (a deterministic or high-rate-flake repro the next person can run — failing test, replay script, minimal invocation).
- [ ] **Root cause is known** (the mechanism is identified, not a hypothesis).
- [ ] **Fix is identified** (PR / commit / branch pointer).
- [ ] **Fix is validated** (the original repro now passes; the affected system behaves correctly).

These map directly to `debug-mantra` steps 1–4. If you came in via `debug-mantra`, the breadcrumb ledger from step 4 is your raw material.

## Structure

Use these blocks in this order. **Summary, Root cause, Fix, and Validation are mandatory.** The rest are conditional but usually present.

### 1. Summary _(mandatory)_
One paragraph. What broke, in system/user terms. What fixed it, in one sentence. Ticket key, PR number, owner, affected component(s). A reader who stops here should have the right answer.

### 2. Symptom
What was actually observed. Test output, error message, log line, perf number, field report. Concrete identifiers — file paths, function names, component names, message types. Don't paraphrase the failure mode.

### 3. Root cause _(mandatory)_
The actual bug mechanism. **Code identifiers welcome and expected** — file paths, class names, method names, config keys, commit SHAs, line numbers. Walk the cause chain end-to-end. This is the most expensive section and the reason the post-mortem exists at all. Future-you will live or die by how clearly you write this.

### 4. Why it produced the symptom
Link the root cause to the symptom. Often non-obvious — the bug is in one component but the visible failure is somewhere else downstream. Walk the chain so a reader who only knows the symptom can connect it back to the cause without re-deriving it.

### 5. Fix _(mandatory)_
What changed and **why this change addresses the root cause** rather than hiding the symptom. Link to PR / commit. If a previous fix attempt papered over the symptom, name it and explain what was wrong with it.

### 6. How it was found
Short. The debugging path:
- What repro made it deterministic.
- What tools cracked it (debugger, source tracing, knob enumeration, in-code instrumentation — the `debug-mantra` step 2 cascade).
- Hypotheses tried and rejected, with the one-line reason each was rejected.
- The single experiment that confirmed the cause.

This section is for the next debugger — make it learnable.

### 7. Why it slipped through
What allowed this bug to reach the branch / release / vehicle. Pick the real reason:
- CI gap (no test exercises this path / configuration).
- Latent code (correct when written, broken by a later change in a different file).
- Coverage gap (no real scenario reached this code path until now).
- Incomplete prior fix (defensive check hid the symptom; root cause untouched).
- Review miss (the change was reviewable; the implication wasn't).

If the honest answer is "no good reason — we should have caught this," say so. **Blameless** — describe the gap, not the person.

### 8. Validation _(mandatory)_
How we know the fix works. Concrete:
- Original failing test now passes (test name, package).
- Scenario / data replay now produces correct output (replay name, metric before/after).
- Health / diagnostics output is now clean (key, value).
- If a safety boundary was touched (`src/safety/`): which safety tests were run.

If you only validated in simulation, say so explicitly. Don't imply broader coverage than you actually have.

### 9. Action items / follow-ups
Concrete next-steps that aren't in the fix PR itself. Each item: what + owner + tracking artifact.

- Regression test added. (Owner, test name.)
- Coverage extended with scenario X. (Owner, ticket.)
- CI gap closed: new check for this path. (Owner, PR.)
- Doc / runbook updated. (Owner, link.)
- Related ticket filed for adjacent issue. (Owner, key.)

If there are no action items, write *"None — the fix is sufficient and no class-of-bug follow-up is warranted."*

## Tone

Engineer-to-engineer. Different from `management-talk`:

- **Code identifiers are first-class.** Function names, file paths, config keys, commit SHAs, line numbers — keep them. The whole point is that future engineers can grep their way back to the change.
- **Mechanism over narrative.** Walk the actual cause chain. Don't soften it into "a synchronization issue" — say which function skipped which check under which condition.
- **Active voice, concrete subjects, short paragraphs.**
- **No hedging.** "We believe" / "appears to" / "may have" — drop. State it or don't write it.
- **Blameless.** Describe the bug, the gap, and the fix. Never "X should have caught this."
- **No advocacy.** A post-mortem records what happened and what's next. If you want to argue for a refactor, that's a separate proposal — link to it from the action items.

## Output flow

1. **Confirm all four required inputs are satisfied.** If any are missing, list them and stop.
2. **Confirm where it goes** (default: ticket comment or `docs/postmortems/<ticket>.md`).
3. **Produce the draft** as a single chat block.
4. **Offer the management-talk handoff:** *"Want a leadership-flavored version? I can hand this to `management-talk`."* Don't do it automatically.

## Worked example — NDT localizer hang on startup (VP-1234)

> **Summary.** The NDT localizer node hung indefinitely on startup when the initial pose arrived before the point cloud map finished loading, causing `/localization/ndt/pose` to never publish. All downstream planning and control components waited for a pose that never came, stalling the vehicle in "waiting for localization" state. Fixed by deferring first-scan matching until the map-load callback fires. VP-1234, PR #412, owner: localization team.
>
> **Symptom.** After launch, `/localization/ndt/pose` published at 0 Hz. `/diagnostics` reported `ndt_scan_matcher: WARN — no map received`. Planning logged `waiting for valid pose estimate` indefinitely. Reproduced 100% on cold-start.
>
> **Root cause.** `src/localization/ndt/ndt/ndt_scan_matcher_node.py`, `NdtScanMatcherNode.__init__`: the first `/localization/pose_initializer/pose` message arrived before `_on_map_loaded` had been called. The scan callback `_on_scan` entered an early-return guarded by `self._map_ready == False`. Since `_on_map_loaded` fires only once and had already been missed, `self._map_ready` was never set — every subsequent scan was silently dropped.
>
> **Why it produced the symptom.** The early-return was silent — no log, no diagnostic. The node appeared healthy (spun up, subscribed, no crash) but produced no output. The silence made it look like a downstream issue rather than a startup race.
>
> **Fix.** PR #412 adds a `self._pending_scans` queue. `_on_scan` enqueues when `_map_ready` is False; `_on_map_loaded` drains the queue immediately after setting the flag. The silent early-return is replaced with a `WARN` log so the condition is visible in `/diagnostics`.
>
> **How it was found.** `ros2 topic hz /localization/ndt/pose` showed 0 Hz. `/diagnostics` showed the map warning. Added `[DBG-7c2a]` log at the top of `_on_scan` — confirmed it fired but returned early on every scan. Single experiment: manually publishing a dummy map message before the pose initializer made the hang disappear.
>
> **Why it slipped through.** All test scenarios used a warm-start configuration (map pre-loaded). The cold-start race — common in real vehicle deployments — was never exercised in CI.
>
> **Validation.** Cold-start bag now produces `/localization/ndt/pose` within 2 s of launch. `colcon test --packages-select ndt` passes. Three consecutive cold-start launches on test vehicle: all localized within 3 s. Not retested on all vehicle configurations.
>
> **Action items.**
> - Regression test: `test_cold_start_map_race` added to `src/localization/ndt/test/`. (Merged in PR #412.)
> - CI: cold-start bag added to nightly localization suite. (VP-1235.)

## Rules

- **Refuse to draft without all four required inputs.**
- **Never invent root cause, owner, validation runs, or action items.**
- **Never strip code identifiers** in the engineering record.
- **Blameless.**
- **State validation coverage honestly.** If you only tested one config, say so.
- **One iteration is normal, three is a smell.** Ask what specific section is wrong rather than keep tweaking blindly.
