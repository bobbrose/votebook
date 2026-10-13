# Working in an Anvil repo

This repo uses the Anvil doc chain: humans own intent and judgment, agents do the drafting and building.

    vision.md -> prd.md -> tech-spec.md -> design.md -> critique.md -> [HUMAN REVIEW] -> plan.md -> build by milestone

- Docs live in `docs/`. Templates in `.anvil/templates/`. Rules in `.anvil/anvil.yaml`.
- Requirement IDs (REQ-, NFR-, AC-) are defined only in `docs/prd.md`. Every other doc, ticket, commit and test cites them.
- Run the gate check after every doc change: `python scripts/anvil_check.py check docs --stage <stage>`.
- Never create or edit `docs/REVIEW.md`. Only the human approves, via `anvil_check.py approve`.
- Changes start at the spec. If code needs to diverge from the docs, update the doc first, then the code. Editing an approved doc makes the approval stale, which is intended.
- Writing style: plain, direct sentences. Avoid double dashes.
