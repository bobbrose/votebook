# Working in an Anvil repo

This repo uses the Anvil doc chain: humans own intent and judgment, agents do the drafting and building.

    vision.md -> prd.md -> tech-spec.md -> design.md -> critique.md -> [HUMAN REVIEW] -> plan.md -> [HUMAN PLAN REVIEW] -> build by milestone

- Docs live in `docs/`. Templates in `.anvil/templates/`. Rules in `.anvil/anvil.yaml`.
- Requirement IDs (REQ-, NFR-, AC-) are defined only in `docs/prd.md`. Every other doc, ticket, commit and test cites them.
- Run the gate check after every doc change: `python scripts/anvil_check.py check docs --stage <stage>`.
- Never create or edit `docs/REVIEW.md`. Only the human approves, via `anvil_check.py approve`.
- Never add or edit the `Reviewed by:` line in `docs/plan.md`. Only the human records plan review, via `anvil_check.py approve-plan docs --by "Name"`.
- Never run `anvil_check.py override`. Only the human decides to proceed past a failing check; it is recorded in `docs/REVIEW.md` with their name and reason. You may tell the human the command when a gate blocks them.
- Before starting any milestone, run `python scripts/anvil_check.py check docs --stage build`. If it fails, stop and ask for plan review. If it passes only because of overrides (OVERRIDDEN warnings), proceed, and name the overridden checks in your milestone report. Plan edits after review are fine (dates, ticket splits, ordering); anything that changes scope goes through the PRD and its approval first.
- Changes start at the spec. If code needs to diverge from the docs, update the doc first, then the code. Editing an approved doc makes the approval stale, which is intended.
- Writing style: plain, direct sentences. Avoid double dashes.
