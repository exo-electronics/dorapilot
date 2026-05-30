---
name: management-talk
description: Rewrite engineer-to-engineer content for engineering-org leadership (VPs, directors, PMs, release managers, execs in an engineering-savvy company) and shape it for the channel it is going to — ticket comment, Slack post, async standup line, email, or meeting talking-points. Trigger when the user asks to write/rewrite for management / exec / VP / director / PM / release manager, asks for an "executive summary / leadership update / status update", says "make this less technical / less jargony", or asks for a slack / email / standup / meeting version of work originally written engineer-to-engineer.
---

# Management Talk

Same audience and translation rules as a written status report, but **shaped for the channel** — ticket comment, Slack post, async standup, email, or meeting talking-points. The audience reads product/component names but not code. The channel decides the length, formatting, and how much structure to leave on the page.

Use this any time engineering content needs to flow up the org, sideways into product/release, or into a non-engineering meeting — regardless of the destination.

## When to invoke

- "write something for management / exec / VP / director / PM / release manager"
- "rewrite this for [non-eng audience]"
- "make this non-technical" / "less techy" / "less jargony"
- "send a slack update / standup note / email" *about a piece of engineering work*
- "executive summary" / "exec summary" / "leadership update" / "status update"
- "talking points for [meeting]" *based on an engineering update*

If the channel is unclear after the trigger, ask one short question — *"ticket, Slack, standup, or email?"* — and stop.

## Audience — what "engineering-org leadership" means

Engineering-savvy non-engineers: VPs, directors, PMs, release managers, execs in companies that ship technical products. They read product/component names and cross-reference ticket keys and PRs. They do not read code.

They want: *what's the state, what does it mean for the product / customer / release, who owns it, what's next.* They do not want: how the bug works at the function level.

This is **not** for marketing, finance, end-customer, or true ELI5 audiences — those need a different rewrite. Flag and confirm before producing one.

## Tone

**Keep.** Component names, system names, team-owned module names, ticket keys, PR numbers, feature/scenario identifiers. These are the bridge between engineering and leadership tracking.

**Strip.** File paths, class names, method names, commit SHAs, config keys, internal variable names, framework-internal jargon. None of this is actionable to the audience.

**Translate.** Mechanism into one or two sentences of plain-English cause-and-effect. Not *"the scan matcher returned early because `self._map_ready` was False"* but *"the localization module started up before its map was loaded, so it silently ignored all incoming data until restarted."* Translate without lying — a race condition stays a race condition; a regression stays a regression.

**Don't over-strip.** Engineering-org leadership reads concept-level technical vocabulary fluently — *race condition, localization, trajectory planning, emergency braking, sensor fusion, CAN bus, inference latency, safety boundary*. The line is between *concept matters here* (keep) and *here's the function/file/SHA* (strip).

**Bias toward** active voice, concrete subjects, short paragraphs. *"We found the bug. The fix is up for review."* beats *"The root cause has been identified and a fix has been submitted for review."*

**Avoid:**
- Hedging that isn't really hedging (*"we believe," "appears to," "may have"*). State it or don't.
- Re-stating the obvious for context (*"AEB is the braking system, which is important for safety, which means..."*).
- Telling leadership how to do their job (*"you should prioritize," "this needs to land before X"*). Give them the facts; they decide.
- Engineering-process minutiae: test runs, replay sessions, debug iterations. They care that you found it, not how.

## Channel shapes

### Ticket comment / written status report

Full structured block. Bolded section labels. Easy to scan from the ticket page.

Building blocks (use as many as fit):

- **Status / TL;DR.** One bolded line. *"Fixed pending merge."* / *"Root cause unknown — investigating."* / *"Blocked on hardware."* / *"Safety regression in v2.1; hotfix in flight."*
- **Impact.** Who or what is affected, how badly, what they observe. Vehicle / feature / scenario terms, not test-suite terms.
- **What broke.** Short paragraph. Plain-English mechanism, one level of why, no code identifiers.
- **Why now / how it slipped through.** Optional. Include when leadership will ask: latent regression, coverage gap, prior incomplete fix.
- **Owner.** Person + team + PR/branch/ticket artifact. One link, not five.
- **Next steps.** Concrete, near-term, ordered.
- **Workaround / mitigation.** If the issue is live today, what can operators do?
- **Risk.** Real risks only. Don't manufacture risk to look thorough.

### Slack — channel post or DM

- One **bolded TL;DR** as the first line.
- 2–4 short bullets: impact, owner+link, next step.
- One link, embedded inline. Not a link wall.
- No greeting, no signoff.
- Thread reply: lose the TL;DR — just lead with the answer.

Length target: under ~80 words for a top-level post; under ~40 for a thread reply.

### Async standup note

- 1–3 lines, max.
- Pattern: *"\<state\> \<thing\>. \<owner if not me\>. \<next\>."*
- Examples:
  - *"Fixed localization cold-start hang (VP-1234). PR #412 in review. Regression test added."*
  - *"Still chasing AEB false-trigger on wet road. Reproducer is reliable; root cause TBD."*
- No bullets, no bolded labels.

### Email — internal exec / cross-team

- **Subject:** the TL;DR as a noun phrase. *"NDT localizer cold-start fix in review (VP-1234)."*
- **Greeting:** match the recipient register.
- **Body:** ticket-comment shape as flowing paragraphs. Two or three paragraphs is plenty.
- **Sign off** with the next decision point that needs the recipient's attention, if any.

### Meeting talking-points

- Bullet list, max one short clause per bullet. Order is the order you'll speak in.
- Include keys/identifiers you want to reference out loud.
- Skip prose. *"NDT localizer was hanging on cold-start."* / *"Map wasn't loaded in time — system silently disabled itself."* / *"Fix in review, PR #412."* / *"Regression test and CI coverage added."*

## Source material

1. **A ticket key** → fetch details if available.
2. **Pasted technical text or post-mortem** → use directly.
3. **The current conversation** → if you just produced engineering content and the user says *"now in slack"* / *"now for the VP,"* reuse what's in context.

If the source is ambiguous, ask one question and stop.

## Output flow

1. **Confirm the channel** if it's not stated.
2. **Produce the draft** as a single chat block, formatted as the channel would render it.
3. **Print-only by default** — the user copies it. Never post to Slack, email, or any external channel from this skill.
4. **One iteration is normal, three is a smell.** Ask what specific framing assumption is wrong rather than keep tweaking blindly.

## Worked example — same bug, three channels

**Source (engineering post-mortem excerpt):**

> `NdtScanMatcherNode._on_scan` entered an early-return guarded by `self._map_ready == False`. The first pose message arrived before `_on_map_loaded` fired. Every subsequent scan was silently dropped with no log or diagnostic.

### As a ticket comment

> **Status: Fixed pending merge.**
>
> **Impact:** The localization module silently stopped processing sensor data if its map file hadn't finished loading when the first position estimate arrived — which happens on every cold start. The vehicle remained stuck in "waiting for localization" indefinitely, blocking all autonomous driving until restarted.
>
> **What broke:** The localization system started accepting position requests before it was ready. When the first request arrived early, the system entered a state that permanently disabled scan processing, with no visible error.
>
> **Why it slipped through:** All existing test scenarios pre-loaded the map. The cold-start race — common in real deployments — was never exercised in CI.
>
> **Owner:** Localization team. PR #412.
>
> **Next steps:** Code review → merge → cold-start scenario added to nightly CI (VP-1235).

### As a Slack post

> **NDT localizer cold-start hang is fixed, pending review.** (VP-1234)
>
> - Every cold-start left the vehicle unable to localize — map wasn't loaded when the first scan arrived; system silently disabled itself with no warning.
> - Owner: localization team, PR #412.
> - Cold-start CI coverage added once merged.

### As a standup note

> Fixed NDT localizer cold-start hang (VP-1234). PR #412 in review. Cold-start CI coverage added (VP-1235).

What changed between channels: same diagnosis, same owner, same next step. Ticket gets every block. Slack drops "why it slipped through." Standup keeps just state + key + owner + next. None of them mention `_on_scan`, `self._map_ready`, or topic paths.

## Rules

- **Never invent facts** to make the rewrite cleaner.
- **Never strip a ticket key, PR number, or component/system name** during de-jargoning.
- **Never invent owners.**
- **Never post to Slack, email, or any external channel from this skill.** Hand the draft to the user.
- **Stay out of advocacy.** This skill produces a status update, not a recommendation.
