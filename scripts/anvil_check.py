#!/usr/bin/env python3
"""Anvil gate checker.

Checks a docs folder produced by the Anvil doc chain:

    vision.md -> prd.md -> tech-spec.md -> design.md -> critique.md
              -> [human review: REVIEW.md] -> plan.md
              -> [human review: "Reviewed by" line in plan.md] -> build

What it enforces:
  * Each doc has its required sections (from .anvil/anvil.yaml-equivalent rules below).
  * Traceability: every requirement ID defined in the PRD (REQ-, NFR-) is covered
    by the tech spec, and every REQ is placed in a plan milestone. No doc may cite
    an ID the PRD does not define.
  * Every acceptance criterion (AC-) is testable: written as WHEN/IF ... SHALL.
  * Every plan milestone has exit criteria and at least one automated check.
  * The review gate: plan.md may not exist (or pass) until REVIEW.md records a
    human approval for each of vision, prd, tech-spec and design whose hash still
    matches. Docs can be approved one at a time (approve --doc) or all at once.
    Editing an approved doc makes only that doc's approval stale.
  * The build gate: building may not start until plan.md has a "Reviewed by:"
    line written by approve-plan. Plan review is not hash-locked; plans change
    during a build, and scope changes go through the PRD and its approval.
  * Overrides: a human can choose to proceed past failing checks with
    "override", recorded in REVIEW.md with a name and reason. An override covers
    only the exact failures it lists; any new failure still blocks. Overridden
    failures are shown as warnings so they stay visible.

Exit code 0 = gate passes, 1 = gate fails. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import sys
from pathlib import Path

STAGES = ["prd", "spec", "design", "review", "plan", "build"]

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
    "build": ["prd", "spec", "design", "critique", "plan"],
}

ID_RE = re.compile(r"\b((?:REQ|NFR|AC)-\d{2,3})\b")
DEF_RE = re.compile(r"^\s*[-*]?\s*\**((?:REQ|NFR|AC)-\d{2,3})\**\s*[:.—-]", re.M)
EARS_RE = re.compile(r"\b(WHEN|IF|WHILE|WHERE)\b.*\bSHALL\b|\bThe \w[\w ]* SHALL\b", re.S)
MILESTONE_RE = re.compile(r"^###\s+(M\d+)\b.*$", re.M)
PLAN_REVIEW_RE = re.compile(r"^Reviewed by:\s*(.+?),\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)


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

    def apply_overrides(self, overrides: list[dict]) -> None:
        """Turn failures a human has overridden into visible warnings."""
        for o in overrides:
            for msg in o["failures"]:
                if msg in self.errors:
                    self.errors.remove(msg)
                    self.warnings.append(f"OVERRIDDEN by {o['by']} ({o['at']}): {msg} [reason: {o['reason']}]")

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


APPROVABLE = ["vision", "prd", "spec", "design"]
# Stage whose checks must pass before a single doc can be approved (vision has none).
APPROVE_STAGE = {"vision": None, "prd": "prd", "spec": "spec", "design": "design"}
APPROVAL_RE = re.compile(
    r"^-\s+(\S+\.md):\s+([0-9a-f]{16})(?:\s+·\s+approved by\s+(.+?)\s+·\s+(\S+))?\s*$", re.M)
NOTES_DEFAULT = "## Reviewer notes\n\n(Add decisions on critique findings here.)\n"
OVERRIDES_HEAD = "## Overrides"
OVERRIDES_INTRO = ("Human decisions to proceed past failing checks. Each covers only the failures listed under it; "
                   "a new failure still blocks. Only humans override, via anvil_check.py override; "
                   "remove all with override --clear.")
OVERRIDE_RE = re.compile(r"^-\s+by\s+(.+?)\s+·\s+(\S+)\s+·\s+(\S+)\s+·\s+reason:\s*(.*)$")


def overrides_section(text: str) -> str:
    m = re.search(rf"^{OVERRIDES_HEAD}\n.*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def read_overrides(docs: Path) -> list[dict]:
    """Each override: who, when, stage, reason and the exact failure messages it covers."""
    out: list[dict] = []
    for line in overrides_section(read(docs, "review") or "").splitlines():
        m = OVERRIDE_RE.match(line)
        if m:
            out.append({"by": m.group(1), "at": m.group(2), "stage": m.group(3), "reason": m.group(4), "failures": []})
        elif out and line.startswith("  - "):
            out[-1]["failures"].append(line[4:].strip())
    return out


def render_overrides(overrides: list[dict]) -> str:
    if not overrides:
        return ""
    lines = [OVERRIDES_HEAD, "", OVERRIDES_INTRO, ""]
    for o in overrides:
        lines.append(f"- by {o['by']} · {o['at']} · {o['stage']} · reason: {o['reason']}")
        lines += [f"  - {f}" for f in o["failures"]]
    return "\n".join(lines) + "\n"


def write_review(docs: Path, records: dict[str, tuple[str, str, str]], overrides: list[dict]) -> None:
    old = read(docs, "review") or ""
    m = re.search(r"^## Reviewer notes.*?(?=^## |\Z)", old, re.M | re.S)
    notes = m.group(0).rstrip() + "\n" if m else NOTES_DEFAULT
    order = [DOCS[k] for k in APPROVABLE]
    lines = [
        "# Review record",
        "",
        "One line per approved doc: file, hash at approval, approver, time.",
        "Editing a doc makes its approval stale. Only humans approve, via anvil_check.py approve.",
        "",
        *[f"- {f}: {records[f][0]} · approved by {records[f][1]} · {records[f][2]}"
          for f in sorted(records, key=lambda f: order.index(f) if f in order else len(order))],
        "",
    ]
    ov = render_overrides(overrides)
    if ov:
        lines += [ov]
    lines += [notes]
    (docs / DOCS["review"]).write_text("\n".join(lines), encoding="utf-8")


def doc_hashes(docs: Path) -> dict[str, str]:
    out = {}
    for key in APPROVABLE:
        p = docs / DOCS[key]
        if p.exists():
            out[DOCS[key]] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def read_approvals(docs: Path) -> dict[str, tuple[str, str, str]]:
    """File name -> (hash, approver, approved at). Also reads the older all-at-once format."""
    text = read(docs, "review")
    if text is None:
        return {}
    legacy_ok = re.search(r"^Status:\s*approved\s*$", text, re.M | re.I)
    legacy_by = re.search(r"^Approved by:\s*(.+)$", text, re.M)
    legacy_at = re.search(r"^Approved at:\s*(.+)$", text, re.M)
    out = {}
    for f, h, by, at in APPROVAL_RE.findall(text):
        if by:
            out[f] = (h, by, at)
        elif legacy_ok:
            out[f] = (h, legacy_by.group(1).strip() if legacy_by else "unknown",
                      legacy_at.group(1).strip() if legacy_at else "unknown")
    return out


def approval_state(docs: Path) -> dict[str, str]:
    """Per approvable doc: 'x' approved and unchanged, '!' changed since approval, ' ' not approved."""
    recorded = read_approvals(docs)
    current = doc_hashes(docs)
    out = {}
    for key in APPROVABLE:
        f = DOCS[key]
        out[key] = " " if f not in recorded else ("x" if recorded[f][0] == current.get(f) else "!")
    return out


def check_review(docs: Path, r: Report) -> bool:
    state = approval_state(docs)
    missing = [DOCS[k] for k, v in state.items() if v == " "]
    stale = [DOCS[k] for k, v in state.items() if v == "!"]
    if missing:
        r.err(f"REVIEW.md: no human approval recorded for: {', '.join(missing)}. "
              "Review, then run: anvil_check.py approve <docs> --by \"Name\" (add --doc <file> for one doc)")
    if stale:
        r.err(f"REVIEW.md: approval is stale; changed since approval: {', '.join(stale)}")
    if missing or stale:
        return False
    who = sorted({v[1] for v in read_approvals(docs).values()})
    r.ok(f"REVIEW.md: {len(APPROVABLE)} docs approved by {', '.join(who)}, hashes match")
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


def check_plan_review(text: str, r: Report, required: bool) -> None:
    m = PLAN_REVIEW_RE.search(text)
    if m:
        r.ok(f"plan.md: reviewed by {m.group(1).strip()} on {m.group(2)}")
    elif required:
        r.err('plan.md: no human review recorded. Review the plan, then run: anvil_check.py approve-plan <docs> --by "Name"')
    else:
        r.warn("plan.md: not reviewed yet; building is blocked until a human runs approve-plan")


def cmd_check(docs: Path, stage: str) -> int:
    print(f"Anvil gate check: {docs}  (stage: {stage})\n")
    r = run_checks(docs, stage)
    r.apply_overrides(read_overrides(docs))
    r.print()
    return 0 if not r.errors else 1


def run_checks(docs: Path, stage: str) -> Report:
    r = Report()
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
    if stage in ("plan", "build"):
        approved = check_review(docs, r)
        if approved and read(docs, "plan") is not None:
            check_plan(read(docs, "plan"), ids, r)
            check_plan_review(read(docs, "plan"), r, required=(stage == "build"))
    elif stage == "review" and read(docs, "plan") is not None and not (docs / DOCS["review"]).exists():
        r.err("plan.md exists before human approval; the plan must come after review")
    return r


def cmd_override(docs: Path, by: str, reason: str, stage: str, match: str | None, clear: bool) -> int:
    overrides = read_overrides(docs)
    if clear:
        write_review(docs, read_approvals(docs), [])
        print(f"Removed {len(overrides)} override(s) from {docs / DOCS['review']}")
        return 0
    if not reason.strip():
        print("An override needs a reason (--reason).")
        return 1
    r = run_checks(docs, stage)
    covered = {f for o in overrides for f in o["failures"]}
    failures = [e for e in r.errors if e not in covered and (match is None or match.lower() in e.lower())]
    if not failures:
        print(f"Nothing to override: no {'matching ' if match else ''}failures at stage {stage} that aren't already overridden.")
        return 0
    now = dt.datetime.now().isoformat(timespec="minutes")
    overrides.append({"by": by, "at": now, "stage": stage, "reason": " ".join(reason.split()), "failures": failures})
    write_review(docs, read_approvals(docs), overrides)
    print(f"Recorded override by {by} in {docs / DOCS['review']} for {len(failures)} failure(s):")
    for f in failures:
        print(f"  - {f}")
    print("\nThese now show as warnings. Any new failure still blocks.")
    return 0


def doc_key(name: str) -> str | None:
    name = name.strip()
    for key in APPROVABLE:
        if name in (key, DOCS[key], DOCS[key].removesuffix(".md")):
            return key
    return None


def cmd_approve(docs: Path, by: str, only: list[str] | None = None) -> int:
    # plan.md has no hash lock; --doc plan.md records its "Reviewed by" line via approve-plan.
    plan_names = ("plan", DOCS["plan"])
    if only and any(n.strip() in plan_names for n in only):
        rest = [n for n in only if n.strip() not in plan_names]
        if rest and cmd_approve(docs, by, rest) != 0:
            return 1
        return cmd_approve_plan(docs, by)
    if only:
        keys = []
        for name in only:
            key = doc_key(name)
            if key is None:
                print(f"Unknown doc '{name}'. Approvable: {', '.join(DOCS[k] for k in APPROVABLE)}")
                return 1
            keys.append(key)
        for key in keys:
            if not (docs / DOCS[key]).exists():
                print(f"{DOCS[key]}: missing")
                return 1
            if APPROVE_STAGE[key] and cmd_check(docs, APPROVE_STAGE[key]) != 0:
                print(f"\nNot approving {DOCS[key]}: fix the failures above first.")
                return 1
    else:
        if cmd_check(docs, "review") != 0:
            print("\nNot approving: fix the failures above first.")
            return 1
        keys = list(APPROVABLE)

    records = read_approvals(docs)
    hashes = doc_hashes(docs)
    now = dt.datetime.now().isoformat(timespec="minutes")
    for key in keys:
        records[DOCS[key]] = (hashes[DOCS[key]], by, now)

    write_review(docs, records, read_overrides(docs))
    print(f"\nRecorded approval of {', '.join(DOCS[k] for k in keys)} in {docs / DOCS['review']}")
    return 0


def cmd_approve_plan(docs: Path, by: str) -> int:
    if cmd_check(docs, "plan") != 0:
        print("\nNot recording plan review: fix the failures above first.")
        return 1
    p = docs / DOCS["plan"]
    text = p.read_text(encoding="utf-8")
    line = f"Reviewed by: {by}, {dt.date.today().isoformat()}"
    if PLAN_REVIEW_RE.search(text):
        text = PLAN_REVIEW_RE.sub(line, text, count=1)
    else:
        lines = text.split("\n")
        at = next((i + 1 for i, l in enumerate(lines) if l.startswith("# ")), 0)
        lines[at:at] = ["", line]
        text = "\n".join(lines)
    p.write_text(text, encoding="utf-8")
    print(f"\nRecorded plan review in {p}: {line}")
    return 0


def cmd_status(docs: Path) -> int:
    print(f"Anvil status: {docs}\n")
    approvals = approval_state(docs)
    plan = read(docs, "plan")
    reviewed = {**approvals, "plan": "x" if plan and PLAN_REVIEW_RE.search(plan) else " "}
    print("  Created  Approved  Doc")
    for key in ["vision", "prd", "spec", "design", "critique", "plan"]:
        created = "x" if (docs / DOCS[key]).exists() else " "
        rev = f"[{reviewed[key]}]" if key in reviewed else " - "
        print(f"  [{created}]      {rev}       {DOCS[key]}")
    print("\n  Approved: [x] yes, [!] changed since approval, [ ] not yet, - no approval step.")
    print("  vision, prd, tech-spec and design approvals are recorded per doc in REVIEW.md; plan.md by its 'Reviewed by' line.")

    hint = {
        "prd": "/anvil-prd", "spec": "/anvil-spec", "design": "/anvil-design",
        "critique": "/anvil-critique", "plan": "/anvil-plan",
    }
    missing = next((k for k in ["prd", "spec", "design", "critique"] if not (docs / DOCS[k]).exists()), None)
    stale = [DOCS[k] for k, v in approvals.items() if v == "!"]
    if missing:
        nxt = hint[missing]
    elif stale:
        nxt = f"approval is stale ({', '.join(stale)} changed); human review, then anvil_check.py approve --doc <file>"
    elif " " in approvals.values():
        todo = ", ".join(DOCS[k] for k, v in approvals.items() if v == " ")
        nxt = f"human review of {todo}, then anvil_check.py approve (or --doc <file> for one)"
    elif plan is None:
        nxt = hint["plan"]
    elif reviewed["plan"] != "x":
        nxt = "human review of plan.md, then anvil_check.py approve-plan"
    else:
        nxt = "build milestone M1 (/anvil-build M1)"
    ov = read_overrides(docs)
    if ov:
        n = sum(len(o["failures"]) for o in ov)
        print(f"\n  Overrides: {n} failure(s) overridden by {', '.join(sorted({o['by'] for o in ov}))} (see REVIEW.md).")
    print(f"\nNext step: {nxt}")
    return 0


EXAMPLES = """\
examples:
    python scripts/anvil_check.py status docs
    python scripts/anvil_check.py check docs --stage design
    python scripts/anvil_check.py approve docs --by "Name"
    python scripts/anvil_check.py approve docs --doc vision.md --by "Name"
    python scripts/anvil_check.py approve-plan docs --by "Name"
    python scripts/anvil_check.py override docs --by "Name" --stage build --reason "Why we proceed"
    python scripts/anvil_check.py override docs --clear

Run '<command> -h' for details on one command.
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", title="commands", metavar="<command>")
    c = sub.add_parser("check", help="run the gate checks for a stage and report failures")
    c.add_argument("docs", type=Path, help="docs folder, e.g. docs")
    c.add_argument("--stage", choices=STAGES, default="review",
                   help="check every doc up to and including this stage (default: review)")
    a = sub.add_parser("approve", help="record a human approval in REVIEW.md (humans only)")
    a.add_argument("docs", type=Path, help="docs folder, e.g. docs")
    a.add_argument("--by", required=True, help="name of the person approving")
    a.add_argument("--doc", action="append", metavar="FILE",
                   help="approve only this doc (vision.md, prd.md, tech-spec.md, design.md, plan.md); repeatable. "
                        "Without it, approves all four after the review-stage check passes")
    pp = sub.add_parser("approve-plan", help="record a human review line in plan.md (humans only)")
    pp.add_argument("docs", type=Path, help="docs folder, e.g. docs")
    pp.add_argument("--by", required=True, help="name of the person who reviewed the plan")
    o = sub.add_parser("override", help="record a human decision to proceed past failing checks (humans only)")
    o.add_argument("docs", type=Path, help="docs folder, e.g. docs")
    o.add_argument("--by", help="name of the person overriding")
    o.add_argument("--reason", default="", help="why it is right to proceed anyway; recorded in REVIEW.md")
    o.add_argument("--stage", choices=STAGES, default="build",
                   help="stage whose current failures to override (default: build)")
    o.add_argument("--match", metavar="TEXT", help="override only failures containing this text (default: all of them)")
    o.add_argument("--clear", action="store_true", help="remove every recorded override")
    s = sub.add_parser("status", help="show which stages pass and the next step")
    s.add_argument("docs", type=Path, help="docs folder, e.g. docs")
    if len(sys.argv) == 1:
        ap.print_help()
        return 0
    args = ap.parse_args()
    if args.cmd == "check":
        return cmd_check(args.docs, args.stage)
    if args.cmd == "approve":
        return cmd_approve(args.docs, args.by, args.doc)
    if args.cmd == "approve-plan":
        return cmd_approve_plan(args.docs, args.by)
    if args.cmd == "override":
        if not args.clear and not args.by:
            ap.error("override needs --by (or --clear)")
        return cmd_override(args.docs, args.by, args.reason, args.stage, args.match, args.clear)
    return cmd_status(args.docs)

if __name__ == "__main__":
    sys.exit(main())
