# Anvil POC: vision to approved plan

A doc-first harness for Claude Code. Give it a vision statement and it drafts a PRD, tech spec and design doc, gets an independent critique, then stops for a human review. Only after you approve does it write an implementation plan with milestones and checks you can run.

## Why it's built this way

- **Traceable.** The PRD defines IDs (REQ, NFR, AC). Every later doc must cover them, and nothing may cite an ID the PRD doesn't define. A script checks this, so drift is caught mechanically, not by rereading.
- **Testable.** Acceptance criteria are written in EARS form (`WHEN ... the system SHALL ...`) so each one maps to a test.
- **A real review gate.** `plan.md` is blocked until `docs/REVIEW.md` records your approval with file hashes. Edit the PRD after approving and the approval goes stale.
- **Repo-native.** Everything is markdown, one Python script (standard library), and Claude Code slash commands. No platform.

## Use it

```
cp -r anvil-poc my-project && cd my-project
# put your vision in docs/vision.md
claude
> /anvil-run          # PRD, spec, design, critique; stops at review
```

Then you review:

```
python scripts/anvil_check.py check docs --stage review
# read docs/, edit anything, answer the critique's decisions
python scripts/anvil_check.py approve docs --by "Your Name"
```

Then:

```
> /anvil-plan         # milestones, tickets, success checks
python scripts/anvil_check.py check docs --stage plan
```

Stage by stage instead: `/anvil-prd`, `/anvil-spec`, `/anvil-design`, `/anvil-critique`, `/anvil-plan`, and `/anvil-status` any time.

## What the checker enforces

| Stage | Checks |
|---|---|
| prd | Required sections; REQ/NFR/AC defined; every AC is EARS and linked to a REQ/NFR; every REQ has an AC |
| spec | Sections; covers every REQ and NFR; no unknown IDs |
| design | Sections; no unknown IDs; warns on user-facing REQs with no design |
| review | All of the above plus critique sections; warns on undispositioned blocking findings; plan must not exist yet |
| plan | Valid, current approval; every milestone has requirements, exit criteria, an automated check in backticks; every REQ and NFR placed |

## Layout

```
.anvil/anvil.yaml          chain, gates, ID rules, Definition of Ready
.anvil/templates/          prd, tech-spec, design, critique, plan
.claude/commands/          /anvil-run, -prd, -spec, -design, -critique, -plan, -status
scripts/anvil_check.py     the gate checker
CLAUDE.md                  rules every agent session reads
docs/                      your project's chain (vision.md goes here)
examples/ballot-explorer/  a full worked run, stopped at the review gate
```

## Not in the POC yet

- Ticket export to GitHub Issues or Linear, the builder/reviewer loop, rubric scoring. The plan's ticket table is shaped for that next step.
- Running the critique on a different model automatically. Today: run `/anvil-critique` in Codex or Gemini CLI, or a fresh Claude session.
