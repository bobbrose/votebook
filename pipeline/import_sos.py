"""Draft sources/<election>/statewide.yaml from the Secretary of State's official files.

    uv run python -I pipeline/import_sos.py CANDIDATES.xlsx DRAWING.xlsx MEASURES.html OUT.yaml

Inputs, downloaded by hand from coloradosos.gov (see pipeline/README.md for URLs):
    CANDIDATES.xlsx  2026 General Election official candidate list
    DRAWING.xlsx     2026 General Election ballot order drawing for party candidates
    MEASURES.html    "Amendments and Propositions on the 2026 Ballot" page

This is the extraction step in tech-spec C1. Its output is a draft: a person checks it
against the Blue Book and a sample ballot and records that in verification/statewide.yaml.
Lines that need a person's attention are printed as NOTE at the end.

Standalone on purpose (no package imports) so it can run with python -I on downloaded files.
"""
from __future__ import annotations

import html
import re
import sys
from collections import defaultdict
from urllib.parse import urljoin

import openpyxl
import yaml

SOS = "https://www.coloradosos.gov/pubs/elections/"
CANDIDATES_URL = SOS + "vote/files/2026/2026GeneralCandidateListOfficial.xlsx"
CANDIDATES_PAGE = SOS + "vote/generalCandidates.html"
DRAWING_URL = SOS + "vote/files/2026/20260728MajorMinorPartyDrawing.xlsx"
MEASURES_PAGE = SOS + "Initiatives/ballot/contacts/2026.html"
BLUE_BOOK = "https://leg.colorado.gov/bluebook"
JPE_INDEX = "https://judicialperformance.colorado.gov/judicial-evaluations"

notes: list[str] = []


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def rows(path: str) -> list[tuple]:
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    return [tuple(c.strip() if isinstance(c, str) else c for c in r) for r in ws.iter_rows(values_only=True)]


# ---------- candidates ----------

# Candidate list office -> (drawing office, item id prefix, title, group, district kind)
OFFICES = [
    ("US Senate", "US Senate", "us-senate", "United States Senator", "federal", None),
    ("US House of Representatives", "US House", "us-house-cd", "Representative to the 120th United States Congress",
     "federal", "cd"),
    ("Governor", "Governor/Lt. Governor*", "governor", "Governor/Lieutenant Governor", "state", None),
    ("Secretary of State", "Secretary of State", "secretary-of-state", "Secretary of State", "state", None),
    ("State Treasurer", "State Treasurer", "state-treasurer", "State Treasurer", "state", None),
    ("Attorney General", "Attorney General", "attorney-general", "Attorney General", "state", None),
    ("State Board of Education", "State Board of Education", "sbe-cd", "State Board of Education Member",
     "state", "cd"),
    ("University of Colorado Board of Regents", "CU Regent", "cu-regent-cd", "Regent of the University of Colorado",
     "state", "cd"),
    ("State Senate", "State Senate", "state-senate", "State Senator", "legislature", "senate"),
    ("State House of Representatives", "State House", "state-house", "State Representative", "legislature", "house"),
]
DISTRICT_IDS = {"cd": "co-cd-{}", "senate": "co-senate-{}", "house": "co-house-{}"}
DISTRICT_NAMES = {"cd": "Congressional District {}", "senate": "District {}", "house": "District {}"}


def drawing_positions(path: str) -> dict[tuple[str, str], dict[str, int]]:
    data = rows(path)
    header = data[0]
    out = {}
    for r in data[1:]:
        if not r[0]:
            continue
        positions = {header[i]: int(v) for i, v in enumerate(r) if i >= 2 and header[i] and v is not None}
        out[(str(r[0]), str(r[1]))] = positions
    return out


def candidate_contests(cand_path: str, drawing_path: str) -> list[dict]:
    data = rows(cand_path)[1:]
    draw = drawing_positions(drawing_path)
    by_office: dict[tuple[str, str], list[dict]] = defaultdict(list)
    write_ins: set[tuple[str, str]] = set()
    for name, office, district, party, write_in in data:
        if not name or not office:
            continue
        key = (office, str(district))
        if write_in == "Y":
            write_ins.add(key)
            continue
        by_office[key].append({"name": name, "party": party or None})

    items = []
    for office, draw_office, prefix, title, group, kind in OFFICES:
        keys = sorted((k for k in by_office if k[0] == office),
                      key=lambda k: int(k[1]) if k[1].isdigit() else 0)
        for key in keys:
            district = key[1]
            if office == "Governor":
                cands = governor_tickets(by_office[key], by_office.get(("Lt. Governor", district), []))
            else:
                cands = by_office[key]
            positions = draw.get((draw_office, district)) or draw.get((draw_office, "State")) or {}
            if not positions and len(cands) > 1:
                notes.append(f"{title} {district}: no party drawing found; check candidate order")
            ordered = order_candidates(cands, positions, f"{title} {district}")
            item = {
                "id": prefix + (f"-{int(district)}" if kind else ""),
                "kind": "candidate_contest",
                "group": group,
                "district_id": DISTRICT_IDS[kind].format(int(district)) if kind else None,
                "title": title + (f" - {DISTRICT_NAMES[kind].format(int(district))}" if kind else ""),
                "vote_for": 1,
                "write_in": key in write_ins,
                "candidates": ordered,
                "links": {"official": [{"label": "Official candidate list (Secretary of State)",
                                        "url": CANDIDATES_PAGE}]},
                "provenance": {"source": CANDIDATES_URL},
            }
            items.append(item)
    unused = sorted({k[0] for k in by_office} - {o[0] for o in OFFICES} - {"Lt. Governor"} - JUDGE_OFFICES
                    - LOCAL_OFFICES)
    for o in unused:
        notes.append(f"candidate list office not imported: {o}")
    return items


def governor_tickets(govs: list[dict], lts: list[dict]) -> list[dict]:
    lt_by_party: dict[str | None, list[dict]] = defaultdict(list)
    for lt in lts:
        lt_by_party[lt["party"]].append(lt)
    tickets = []
    for g in govs:
        mates = lt_by_party.get(g["party"], [])
        if len(mates) != 1:
            notes.append(f"Governor {g['name']}: cannot pair with a Lieutenant Governor by party; check")
            tickets.append(g)
            continue
        tickets.append({"name": f"{g['name']} / {mates[0]['name']}", "party": g["party"]})
    return tickets


def order_candidates(cands: list[dict], positions: dict[str, int], where: str) -> list[dict]:
    """Party candidates in drawn order, then candidates the drawing does not place (unaffiliated)."""
    placed = sorted((c for c in cands if c["party"] in positions), key=lambda c: positions[c["party"]])
    rest = [c for c in cands if c["party"] not in positions]
    if len(rest) > 1:
        notes.append(f"{where}: {len(rest)} candidates not placed by the party drawing; order is a guess, "
                     "check the sample ballot")
    out = []
    for i, c in enumerate(placed + sorted(rest, key=lambda c: c["name"]), start=1):
        out.append({"id": "cand-" + slug(c["name"]), "name": c["name"], "party": c["party"], "order": i})
    return out


# ---------- judges ----------

JUDGE_OFFICES = {"Colorado Supreme Court", "Colorado Court of Appeals"}
# Judicial district, county court and special district races belong in county files.
LOCAL_OFFICES = {"District Court", "County Court", "Associate County Court", "RTD Board of Directors",
                 "District Court - Denver Juvenile Court", "Distirct Court - Denver Probate Court", "None"}


def retentions(cand_path: str) -> list[dict]:
    items = []
    for court, prefix, role in (("Colorado Supreme Court", "retain-supreme", "Justice"),
                                ("Colorado Court of Appeals", "retain-appeals", "Judge")):
        for name, office, _district, _party, _w in rows(cand_path)[1:]:
            if office != court:
                continue
            items.append({
                "id": f"{prefix}-{slug(name)}",
                "kind": "retention",
                "group": "judges",
                "district_id": None,
                "title": f"{court} {role} {name}",
                "judge": name,
                "court": court,
                "links": {"official": [{"label": "Judicial performance evaluation", "url": JPE_INDEX}]},
                "provenance": {"source": CANDIDATES_URL},
            })
            notes.append(f"{name}: evaluation link is the index page; replace with the judge's own page")
    return items


# ---------- measures ----------

def text_lines(path: str) -> list[tuple[str, list[str]]]:
    """(text, hrefs) per visible line of the measures page."""
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?is)<(script|style).*?</\1>", "", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|tr|li|h\d|div|td|th)>", "\n", t)
    out = []
    for raw in t.splitlines():
        hrefs = re.findall(r'href="([^"]+)"', raw)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        if text:
            out.append((text, hrefs))
    return out


def measures(path: str) -> tuple[list[dict], dict[str, str]]:
    lines = text_lines(path)
    starts = [i for i, (t, _) in enumerate(lines) if re.fullmatch(r"(Amendment|Proposition) [0-9A-Z]+", t)]
    items, certified = [], {}
    for n, s in enumerate(starts):
        block = lines[s: starts[n + 1] if n + 1 < len(starts) else len(lines)]
        name = block[0][0]
        title_lines, pdf = [], None
        in_title = False
        side = None
        sides = {"Favor": False, "Oppose": False}
        for text, hrefs in block[1:]:
            if text.startswith("Text of"):
                in_title = False
                pdf = urljoin(MEASURES_PAGE, hrefs[0]) if hrefs else None
            elif re.match(r"(?i)^shall ", text) and not title_lines:
                in_title = True
            if in_title:
                title_lines.append(text)
            if text in sides:
                side = text
            elif side and text.startswith("Registered agent:"):
                sides[side] = True
            if text.startswith("Ballot Issue"):
                break
        if not title_lines:
            notes.append(f"{name}: no ballot title found")
            continue
        mid = slug(name)
        text, table = title_lines[0], None
        if len(title_lines) > 1:
            table = parse_table(title_lines[1:], name)
            if table is None:
                text = "\n".join(title_lines)
        committees = {"label": "Registered issue committees (Secretary of State)", "url": MEASURES_PAGE}
        official = [{"label": "Blue Book analysis", "url": BLUE_BOOK},
                    {"label": "Ballot title and committees (Secretary of State)", "url": MEASURES_PAGE}]
        if pdf:
            official.append({"label": "Full text", "url": pdf})
        items.append({
            "id": mid, "kind": "measure", "group": "measures", "district_id": None, "title": name,
            "ballot_text": {"text": text, "source": MEASURES_PAGE, **({"table": table} if table else {})},
            "links": {"official": official, "explainers": [],
                      "support": committees if sides["Favor"] else None,
                      "oppose": committees if sides["Oppose"] else None},
            "provenance": {"source": MEASURES_PAGE},
        })
        certified[mid] = text
    return items, certified


MONEY = re.compile(r"^[+-]?\$[\d,]+$")
ROW_LABEL = re.compile(r"^\$[\d,]+ (or less|- \$[\d,]+)$|^\$[\d,]+ or more$")


def parse_table(lines: list[str], name: str) -> dict | None:
    """The income tax table Colorado requires in some ballot titles (caption, header, rows, note)."""
    try:
        first_row = next(i for i, l in enumerate(lines) if ROW_LABEL.match(l))
    except StopIteration:
        notes.append(f"{name}: ballot title has extra lines that are not a recognized table; check it")
        return None
    caption = lines[1] if lines[0].startswith("Initiative ") else lines[0]
    head_start = 2 if lines[0].startswith("Initiative ") else 1
    header_text = " ".join(lines[head_start:first_row])
    header = [h.strip() for h in re.split(r" (?=Current |Proposed )", header_text)]
    rows, i = [], first_row
    while i + 4 <= len(lines) and ROW_LABEL.match(lines[i]) and all(MONEY.match(c) for c in lines[i + 1:i + 4]):
        rows.append(lines[i:i + 4])
        i += 4
    if len(header) != 4 or not rows:
        notes.append(f"{name}: could not parse its ballot title table; enter it by hand")
        return None
    notes.append(f"{name}: ballot title table parsed ({len(rows)} rows); check it against the Blue Book")
    return {"caption": caption, "header": header, "rows": rows, "note": " ".join(lines[i:]) or None}


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(__doc__)
        return 2
    _, cand, drawing, meas, out = argv
    contests = candidate_contests(cand, drawing)
    judges = retentions(cand)
    props, _ = measures(meas)
    doc = {
        "election_id": "co-2026-11-03",
        "districts": [],
        "items": contests + judges + props,
    }
    header = ("# Statewide items for the November 3, 2026 general election, in printed order.\n"
              "# Drafted by pipeline/import_sos.py from the Secretary of State's official files;\n"
              "# corrected and verified by a person (verification/statewide.yaml).\n")
    with open(out, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=110)
    print(f"Wrote {out}: {len(contests)} contests, {len(judges)} retentions, {len(props)} measures")
    for n in notes:
        print(f"NOTE  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
