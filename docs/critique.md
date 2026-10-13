# Critique of Colorado Ballot Explorer docs

Reviewer: Claude, same session that drafted the docs (NOT independent; rerun `/anvil-critique` in Codex, Gemini or a fresh session before approving) · Inputs: vision, prd, tech-spec, design

## Summary

The doc set is coherent and traceable: 23 requirements, 9 quality requirements and 39 testable acceptance criteria, all covered by the spec, with a design for every user-facing requirement. The privacy architecture holds up and is testable, which is the vision's highest priority.

Top three issues:
1. The November 3 release is not realistic as scoped. Three weeks remain, and the scope includes a data pipeline, two verified counties, a full app and a review process for neutral text that does not exist yet.
2. Fetching a county file tells the host roughly where the voter lives. The vision says the server "never learns which districts" someone cares about; the docs weaken that quietly. It needs an explicit decision.
3. Neutral measure descriptions (REQ-08) depend on a review process and reviewers who are not identified. Without them, AC-11 fails every build.

## Findings

- [blocking] prd.md / Release scope: Release 1 includes 21 requirements and nearly all NFRs, due November 3. Suggested fix: cut Release 1 to a tester pilot (lookup, narrowing, decisions, notes, write-out, local storage, privacy guard, Boulder and Larimer) and move export/import, descriptions and the error-report path to a later release, or retarget Release 1 to 2027. **Resolved:** 2026 is an invited-tester pilot with the suggested scope, starting October 16; the public Release 1 targets the November 2, 2027 coordinated election (D1; PRD Release scope).
- [blocking] tech-spec.md / Security and privacy vs vision: per-county fetches reveal county to the host. Suggested fix: decide between (a) "download all counties" by default if size allows, (b) bundle counties into a few regional files, or (c) keep per-county and disclose on the privacy page. Measure the all-counties size before choosing. **Resolved:** every browser downloads the same all-counties file, with a 1.5 MB size budget enforced by the build and regional bundles plus disclosure as the fallback (D2; NFR-01, AC-40).
- [blocking] prd.md / REQ-08, AC-10, AC-11: no reviewer or process exists (PRD Q5). Suggested fix: for Release 1, show official Blue Book and county text only, link out, and write no descriptions of our own. Add REQ-08 when a cross-spectrum review panel exists. **Resolved:** REQ-08, AC-10 and AC-11 now cover certified ballot text and official links only; project-written descriptions wait for a panel, which is still unnamed (D3; PRD Q5).
- [non-blocking] prd.md / AC-01: "every ballot style that intersects that ZIP" assumes ballot-style ground truth that the spec approximates with Census ZCTAs. Suggested fix: reword to "every item whose district intersects the ZIP's ZCTA", and add a data test comparing against the county sample ballot for 10 known addresses.
- [non-blocking] prd.md / Functional requirements: no requirement covers data changing after a voter has decided (a candidate withdraws, a measure is removed). Suggested fix: add a REQ and AC: when saved choices reference changed or removed items, show them with a notice instead of silently dropping them.
- [non-blocking] prd.md / REQ-10, REQ-13: write-in names are allowed in the design (S5) but their storage, export and write-out are not specified. Suggested fix: add write-in handling to REQ-10's ACs.
- [non-blocking] prd.md / REQ-06: judicial retention items need a named official source. Colorado's judicial performance evaluations are official but include a "meets / does not meet" finding, which some will read as a recommendation. Suggested fix: owner decides whether to link, quote or omit.
- [non-blocking] prd.md / NFR-04: the 3 s and 1 s targets are proposed, not from the vision. Suggested fix: keep, but confirm after measuring real county file sizes in the first milestone.
- [non-blocking] tech-spec.md / C9: "Report an error" by email exposes the reporter's address to the project; GitHub issues need a GitHub account. Both are acceptable for corrections, but the privacy page must say so.
- [non-blocking] design.md / S6: "Save as image" (open question) would create an image in the photo library, which syncs to cloud services. If adopted, warn the voter.

## Vision drift

- Covered well: completeness labeling, provenance, privacy commitments, nonpartisan presentation, write-out, offline.
- Weakened: "server never learns which districts" (see blocking finding 2).
- Not covered and correctly out of scope: endorsements (vision says links only, if at all), outreach partners, funding and governance.
- Missing input: "Lessons from Searchboard" is still blank in the vision. Searchboard's login-free storage and export patterns may change C5 and C6.
- Added without basis: performance targets (NFR-04), 48-hour correction target in Success metrics. Both flagged for confirmation.

## Decisions needed

Decisions below were made by Claude at the owner's request ("yours"), and are applied to prd.md, tech-spec.md and design.md. The owner confirms or overrules them at human review.

- D1: Release 1 scope and date: tester pilot for November 3, 2026, or full Release 1 for the 2027 coordinated election? **Decided:** both. An invited-tester pilot for the November 3, 2026 election, starting October 16, 2026 (date set by the owner), with the critique's suggested scope, and the public Release 1 on November 2, 2027. Odd-year coordinated elections move out of the non-goals.
- D2: County-file privacy: download-all by default, regional bundles, or per-county with disclosure? **Decided:** download-all by default, so the vision's "server never learns which districts" holds. The build enforces a 1.5 MB compressed budget; if real data exceeds it, regional bundles with disclosure on the privacy page. Never per-county.
- D3: Neutral descriptions in Release 1, or official text and links only until a review panel exists? Who sits on the panel? **Decided:** official certified text and links only, in the pilot and Release 1. No panel is named; recruiting one is open question Q5.
- D4: Judicial retention: link to performance evaluations, show their finding, or omit? **Decided:** link to each judge's official evaluation page as an official source, without quoting or displaying the finding in the app (REQ-06, AC-41). Omitting would hide an official source; showing the finding would give it a prominence the app does not give anything else.
- D5: Unverified counties: statewide items only (current assumption), or licensed data labeled unverified? **Decided:** statewide items only, as the PRD assumed. This keeps the rule against showing a partial ballot as complete simple to test.
- D6: Error reporting channel: email, GitHub issue, or both? **Decided:** both, from Release 1, each with a plain statement of what it exposes (also addresses the C9 finding). Pilot testers report directly in moderated sessions.
