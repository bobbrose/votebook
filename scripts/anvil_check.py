#!/usr/bin/env python3
"""Anvil gate checker.

Checks a docs folder produced by the Anvil doc chain:

    vision.md -> prd.md -> tech-spec.md -> design.md -> critique.md
              -> [human review: REVIEW.md] -> plan.md

Usage:
    python scripts/anvil_check.py check   <docs_dir> [--stage prd|spec|design|review|plan]
    python scripts/anvil_check.py approve <docs_dir> --by "Name"
    python scripts/anvil_check.py status  <docs_dir>

What it enforces:
  * Each doc has its required sections (from .anvil/anvil.yaml-equivalent rules below).
  * Traceability: every requirement ID defined in the PRD (REQ-, NFR-) is covered
    by the tech spec, and every REQ is placed in a plan milestone. No doc may cite
    an ID the PRD does not define.
  * Every acceptance criterion (AC-) is testable: written as WHEN/IF ... SHALL.
  * Every plan milestone has exit criteria and at least one automated check.
  * The review gate: plan.md may not exist (or pass) until REVIEW.md records a
    human approval whose hashes still match prd, tech-spec and design. Editing an
    approved doc makes the approval stale.

Exit code 0 = gate passes, 1 = gate fails. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

STAGES = ["prd", "spec", "design", "review", "plan"]

DOCS = {
    "vision": "vision.md",
    "prd": "prd.md",
    "spec": "tech-spec.md",
    "design": "design.md",
    "critique": "critique.md",
    "review": "REVIEW.md",
    "plan": "plan.md",
}

# Required level-2 headings (case-insensitive prefix match).
REQUIRED = {
    "prd": [
        "Problem", "Goals", "Non-goals", "Users", "Functional requirements",
        "Non-functional requirements", "Acceptance criteria", "Success metrics",
        "Open questions",
    ],
    "spec": [
        "Overview", "Architecture", "Data model", "Components",
        "Requirement coverage", "Security and privacy", "Testing strategy",
        "Risks", "Open questions",
    ],
    "design": [
        "Principles", "Information architecture", "Key flows", "Screens",
        "Accessibility", "Content and tone", "Requirement coverage",
        "Open questions",
    ],
    "critique": ["Summary", "Findings", "Decisions needed"],
    "plan": ["Milestones", "Ticket list", "Requirement coverage", "Risks"],
}

# Every stage includes the checks for the stages before it.
STAGE_DOCS = {
    "prd": ["prd"],
    "spec": ["prd", "spec"],
    "design": ["prd", "spec", "design"],
    "review": ["prd", "spec", "design", "critique"],
    "plan": ["prd", "spec", "design", "critique", "plan"],
}

ID_RE = re.compile(r"\b((?:REQ|NFR|AC)-\d{2,3})\b")
DEF_RE = re.compile(r"^\s*[-*]?\s*\**((?:REQ|NFR|AC)-\d{2,3})\**\s*[:.—-]", re.M)
EARS_RE = re.compile(r"\b(WHEN|IF|WHILE|WHERE)\b.*\bSHALL\b|\bThe \w[\w ]* SHALL\b", re.S)
MILESTONE_RE = re.compile(r"^###\s+(M\d+)\b.*$", re.M)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def print(self) -> None:
        for m in self.passes:
            print(f"  PASS  {m}")
        for m in self.warnings:
            print(f"  WARN  {m}")
        for m in self.errors:
            print(f"  FAIL  {m}")
        verdict = "GATE PASSES" if not self.errors else "GATE BLOCKED"
        print(f"\n{verdict}: {len(self.passes)} pass, {len(self.warnings)} warn, {len(self.errors)} fail")


def read(docs: Path, key: str) -> str | None:
    p = docs / DOCS[key]
    return p.read_text(encoding="utf-8") if p.exists() else None


def headings(text: str) -> list[str]:
    return [h.strip().lower() for h in re.findall(r"^##\s+(.+)$", text, re.M)]


def section(text: str, name: str) -> str:
    """Body of the first level-2 section whose heading starts with name."""
    m = re.search(rf"^##\s+{re.escape(name)}.*$", text, re.M | re.I)
    if not m:
        return ""
    nxt = re.search(r"^##\s+", text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start()] if nxt else text[m.end():]


def check_sections(key: str, text: str, r: Report) -> None:
    hs = headings(text)
    missing = [s for s in REQUIRED[key] if not any(h.startswith(s.lower()) for h in hs)]
    if missing:
        r.err(f"{DOCS[key]}: missing sections: {', '.join(missing)}")
    else:
        r.ok(f"{DOCS[key]}: all {len(REQUIRED[key])} required sections present")
    if re.search(r"\bTODO\b|\bTBD\b|\[fill in\]", text):
        r.warn(f"{DOCS[key]}: contains TODO/TBD placeholders")


def prd_ids(prd: str) -> dict[str, set[str]]:
    defs = set(DEF_RE.findall(prd))
    return {
        "REQ": {i for i in defs if i.startswith("REQ")},
        "NFR": {i for i in defs if i.startswith("NFR")},
        "AC": {i for i in defs if i.startswith("AC")},
    }


def check_prd(prd: str, r: Report) -> dict[str, set[str]]:
    ids = prd_ids(prd)
    if not ids["REQ"]:
        r.err("prd.md: no functional requirements defined (expected lines like '- REQ-01: ...')")
    if not ids["AC"]:
        r.err("prd.md: no acceptance criteria defined (expected lines like '- AC-01: ...')")
    r.ok(f"prd.md: {len(ids['REQ'])} REQ, {len(ids['NFR'])} NFR, {len(ids['AC'])} AC defined")

    # Every AC must be EARS-style and trace to at least one REQ/NFR.
    ac_body = section(prd, "Acceptance criteria")
    bad_ears, untraced = [], []
    for line in ac_body.splitlines():
        m = DEF_RE.match(line)
        if not m or not m.group(1).startswith("AC"):
            continue
        if not EARS_RE.search(line):
            bad_ears.append(m.group(1))
        if not re.search(r"\b(?:REQ|NFR)-\d{2,3}\b", line):
            untraced.append(m.group(1))
    if bad_ears:
        r.err(f"prd.md: acceptance criteria not in WHEN/IF ... SHALL form: {', '.join(bad_ears)}")
    else:
        r.ok("prd.md: every acceptance criterion is EARS-style (testable)")
    if untraced:
        r.err(f"prd.md: acceptance criteria not linked to a REQ/NFR: {', '.join(untraced)}")

    # Every REQ should have at least one AC pointing at it.
    covered = set(re.findall(r"\bREQ-\d{2,3}\b", ac_body))
    no_ac = sorted(ids["REQ"] - covered)
    if no_ac:
        r.err(f"prd.md: functional requirements with no acceptance criterion: {', '.join(no_ac)}")
    else:
        r.ok("prd.md: every REQ has at least one acceptance criterion")
    return ids


def check_refs(key: str, text: str, ids: dict[str, set[str]], r: Report,
               must_cover: tuple[str, ...]) -> None:
    all_ids = ids["REQ"] | ids["NFR"] | ids["AC"]
    cited = set(ID_RE.findall(text))
    unknown = sorted(cited - all_ids)
    if unknown:
        r.err(f"{DOCS[key]}: cites IDs the PRD does not define: {', '.join(unknown)}")
    for kind in must_cover:
        missing = sorted(ids[kind] - cited)
        if missing:
            r.err(f"{DOCS[key]}: {kind}s not covered: {', '.join(missing)}")
        elif ids[kind]:
            r.ok(f"{DOCS[key]}: covers all {len(ids[kind])} {kind}s")


def check_critique(text: str, r: Report) -> None:
    blocking = len(re.findall(r"\[blocking\]", text, re.I))
    resolved = len(re.findall(r"\[blocking\].*\b(resolved|accepted|deferred)\b", text, re.I))
    if blocking - resolved > 0:
        r.warn(f"critique.md: {blocking - resolved} blocking finding(s) not marked resolved/accepted/deferred; reviewer should decide")
    else:
        r.ok(f"critique.md: {blocking} blocking finding(s), all dispositioned")


def doc_hashes(docs: Path) -> dict[str, str]:
    out = {}
    for key in ("prd", "spec", "design"):
        p = docs / DOCS[key]
        if p.exists():
            out[DOCS[key]] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def check_review(docs: Path, r: Report) -> bool:
    text = read(docs, "review")
    if text is None:
        r.err("REVIEW.md: no human approval recorded. Review the docs, then run: anvil_check.py approve <docs> --by \"Name\"")
        return False
    if not re.search(r"^Status:\s*approved\s*$", text, re.M | re.I):
        r.err("REVIEW.md: status is not 'approved'")
        return False
    recorded = dict(re.findall(r"^-\s+(\S+\.md):\s+([0-9a-f]{16})\s*$", text, re.M))
    current = doc_hashes(docs)
    stale = [f for f, h in current.items() if recorded.get(f) != h]
    if stale:
        r.err(f"REVIEW.md: approval is stale; changed since approval: {', '.join(stale)}")
        return False
    who = re.search(r"^Approved by:\s*(.+)$", text, re.M)
    r.ok(f"REVIEW.md: approved by {who.group(1).strip() if who else 'unknown'}, hashes match")
    return True


def check_plan(text: str, ids: dict[str, set[str]], r: Report) -> None:
    ms = MILESTONE_RE.findall(text)
    if not ms:
        r.err("plan.md: no milestones (expected '### M1 ...' headings)")
        return
    parts = re.split(r"^###\s+(?=M\d+\b)", text, flags=re.M)[1:]
    for part in parts:
        name = part.split()[0]
        nxt = re.search(r"^##\s+", part, re.M)
        body = part[: nxt.start()] if nxt else part
        if not re.search(r"Exit criteria", body, re.I):
            r.err(f"plan.md: {name} has no exit criteria")
        if not re.search(r"`[^`]+`", body):
            r.err(f"plan.md: {name} has no automated check (expected a command in backticks)")
        if not ID_RE.search(body):
            r.err(f"plan.md: {name} does not reference any requirement")
    r.ok(f"plan.md: {len(ms)} milestones found")
    check_refs("plan", text, ids, r, must_cover=("REQ", "NFR"))


def cmd_check(docs: Path, stage: str) -> int:
    r = Report()
    print(f"Anvil gate check: {docs}  (stage: {stage})\n")
    if read(docs, "vision") is None:
        r.err("vision.md: missing; the chain starts from a vision")
    ids: dict[str, set[str]] = {"REQ": set(), "NFR": set(), "AC": set()}
    for key in STAGE_DOCS[stage]:
        text = read(docs, key)
        if text is None:
            r.err(f"{DOCS[key]}: missing")
            continue
        check_sections(key, text, r)
        if key == "prd":
            ids = check_prd(text, r)
        elif key == "spec":
            check_refs(key, text, ids, r, must_cover=("REQ", "NFR"))
        elif key == "design":
            check_refs(key, text, ids, r, must_cover=())
            ux = [i for i in sorted(ids["REQ"]) if i not in set(ID_RE.findall(text))]
            if ux:
                r.warn(f"design.md: REQs with no design coverage (fine if not user-facing): {', '.join(ux)}")
        elif key == "critique":
            check_critique(text, r)
    if stage == "plan":
        approved = check_review(docs, r)
        if approved and read(docs, "plan") is not None:
            check_plan(read(docs, "plan"), ids, r)
    elif stage == "review" and read(docs, "plan") is not None and not (docs / DOCS["review"]).exists():
        r.err("plan.md exists before human approval; the plan must come after review")
    r.print()
    return 0 if not r.errors else 1


def cmd_approve(docs: Path, by: str) -> int:
    if cmd_check(docs, "review") != 0:
        print("\nNot approving: fix the failures above first.")
        return 1
    hashes = doc_hashes(docs)
    lines = [
        "# Review record",
        "",
        "Status: approved",
        f"Approved by: {by}",
        f"Approved at: {dt.datetime.now().isoformat(timespec='minutes')}",
        "",
        "Approval covers these files at these hashes. Editing any of them makes the approval stale.",
        "",
        *[f"- {f}: {h}" for f, h in hashes.items()],
        "",
        "## Reviewer notes",
        "",
        "(Add decisions on critique findings here.)",
        "",
    ]
    (docs / DOCS["review"]).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nRecorded approval in {docs / DOCS['review']}")
    return 0


def cmd_status(docs: Path) -> int:
    print(f"Anvil status: {docs}\n")
    for key in ["vision", "prd", "spec", "design", "critique", "review", "plan"]:
        mark = "x" if (docs / DOCS[key]).exists() else " "
        print(f"  [{mark}] {DOCS[key]}")
    nxt = next((k for k in ["prd", "spec", "design", "critique", "review", "plan"]
                if not (docs / DOCS[k]).exists()), None)
    hint = {
        "prd": "/anvil-prd", "spec": "/anvil-spec", "design": "/anvil-design",
        "critique": "/anvil-critique", "review": "human review, then anvil_check.py approve",
        "plan": "/anvil-plan",
    }
    print(f"\nNext step: {hint[nxt] if nxt else 'build milestone M1 (/anvil-build M1)'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("docs", type=Path)
    c.add_argument("--stage", choices=STAGES, default="review")
    a = sub.add_parser("approve")
    a.add_argument("docs", type=Path)
    a.add_argument("--by", required=True)
    s = sub.add_parser("status")
    s.add_argument("docs", type=Path)
    args = ap.parse_args()
    if args.cmd == "check":
        return cmd_check(args.docs, args.stage)
    if args.cmd == "approve":
        return cmd_approve(args.docs, args.by)
    return cmd_status(args.docs)


if __name__ == "__main__":
    sys.exit(main())
