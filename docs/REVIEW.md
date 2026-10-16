# Review record

One line per approved doc: file, hash at approval, approver, time.
Editing a doc makes its approval stale. Only humans approve, via anvil_check.py approve.

- vision.md: f718deee5707f20c · approved by Bob Rose · 2026-10-14T18:20
- prd.md: 72ec9162bfe8feb5 · approved by Bob Rose · 2026-10-15T09:03
- tech-spec.md: d08c2126c4853125 · approved by Bob Rose · 2026-10-15T09:03
- design.md: 9b29a509ed007753 · approved by Bob Rose · 2026-10-15T09:03

## Overrides

Human decisions to proceed past failing checks. Each covers only the failures listed under it; a new failure still blocks. Only humans override, via anvil_check.py override; remove all with override --clear.

- by Bob Rose · 2026-10-16T15:41 · build · reason: Pilot needs reviewers now; doc review continues in parallel
  - REVIEW.md: approval is stale; changed since approval: prd.md, tech-spec.md, design.md

## Reviewer notes

(Add decisions on critique findings here.)
