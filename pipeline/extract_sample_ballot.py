"""Draft a county source file from the text of a compiled sample ballot PDF.

    uv run python -I pipeline/extract_sample_ballot.py BALLOT.txt STATEWIDE.yaml COUNTY_FIPS NAME SAMPLE_URL OUT.yaml

BALLOT.txt is the PDF's text, one page after another (pypdf extract_text), with
"=== PAGE n" lines between pages. This is the extraction step in tech-spec C1: the
output is a draft that a person corrects and verifies against the PDF. Anything the
extractor is unsure of is marked with "CHECK:" in the output and printed as NOTE.

Standalone on purpose (no package imports) so it can run with python -I on downloaded files.
"""
from __future__ import annotations

import re
import sys

import yaml

PARTIES = ["Republican", "Democratic", "Libertarian", "Unaffiliated", "Forward", "Unity", "Approval Voting",
           "American Constitution", "Center", "Green"]
SECTIONS = {
    "Federal Offices": "federal", "State Offices": "state", "County Offices": "county",
    "Local Offices": "city", "Judicial Retention Questions": "judges", "Ballot Measures": "measures",
    "State Ballot Measures": "measures", "Local Ballot Measures": "measures",
}
NOISE = re.compile(r"^(\d{1,2}|[1-9](st|nd|rd|th)|Choice|Sample Ballot|YES|NO|\(Vote YES or NO\))$"
                   r"|compiled ballot content|^every ballot|Not an official ballot")
BOILERPLATE = re.compile(
    r"^(Mark both sides|Sample Ballot for|SAMPLE BALLOT|Larimer County, Colorado|Boulder County, Colorado|Tuesday, November"
    r"|WARNING:|falsely makes|conviction, to|upon conviction|To vote for|for or against a measure|completely fill in"
    r"|your choice\.|If a race includes|write-in candidate by|left of the line|eligible write-in|To make a correction"
    r"|bold line through|then fill in the oval|only candidate in a race|Ballot questions referred|or any political subdivision"
    r"|ballot questions initiated|numerically\.|\"amendment\" proposes|constitution, and a ballot|\"proposition\" proposes"
    r"|Revised Statutes\. A|question is a vote|or existing circumstances|on any ballot question is|current law or existing"
    r"|State of Colorado$|\(Vote YES or NO\)$)", re.I)
VOTE_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9}

notes: list[str] = []


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def lines_of(path: str) -> list[str]:
    raw = open(path, encoding="utf-8").read()
    # Page footers and instructions on page 1 sit after the content; drop everything between
    # the page number line and the next page marker.
    pages = re.split(r"^=== PAGE \d+\s*$", raw, flags=re.M)[1:]
    out: list[str] = []
    for page in pages:
        body = re.split(r"^\d+\s*$\n(?=.*(compiled ballot content|Boulder County compiled))", page, flags=re.M)[0]
        for l in body.splitlines():
            l = clean(l)
            if l and not NOISE.search(l) and not BOILERPLATE.match(l):
                out.append(l)
        out.append("<<PAGE>>")
    return out


def split_party(line: str) -> tuple[str, str | None]:
    for p in sorted(PARTIES, key=len, reverse=True):
        if line.endswith(" " + p):
            return line[: -len(p) - 1].strip(), p
    return line, None


def vote_for(text: str) -> int | None:
    m = re.search(r"\(Vote for (?:no more than )?(\w+)", text, re.I) or \
        re.search(r"vote for (?:up to|not more than) (\w+)", text, re.I)
    if not m:
        return None
    w = m.group(1).capitalize()
    return VOTE_WORDS.get(w) or (int(w) if w.isdigit() else None)


def norm_title(s: str) -> str:
    return re.sub(r"\s*([/-])\s*", r"\1", clean(s).lower())


def match_statewide(title: str, sw: list[dict], kind: str) -> str | None:
    t = clean(title).lower()
    for it in sw:
        if it["kind"] != kind:
            continue
        if kind == "retention" and it["judge"].lower() in t:
            return it["id"]
        if kind == "measure" and clean(t).startswith(it["title"].lower() + " "):
            return it["id"]
        if kind == "candidate_contest" and norm_title(it["title"]) == norm_title(title):
            return it["id"]
    return None


VOTE_PHRASE = re.compile(r"\(Vote for (?:no more than |up to )?(\w+)", re.I)
DEFAULT_CHOICES = ["YES/FOR", "NO/AGAINST"]


def contest_start(lines: list[str], k: int) -> str | None:
    """Which header pattern starts a candidate contest at line k, if any."""
    l = lines[k]
    nxt = lines[k + 1] if k + 1 < len(lines) else ""
    nxt2 = lines[k + 2] if k + 2 < len(lines) else ""
    if "(Vote for" in l and "?" not in l.split("(Vote for")[0]:
        return "inline"
    if re.match(r"^(District \w+\s*)?\(Vote for", nxt) and "?" not in l:
        return "wrapped"
    if re.match(r"^\(Vote for", nxt2) and "?" not in l + nxt and not split_party(l)[1] \
            and (l.endswith((" ", "-")) or l.rstrip().endswith(("States", "-", "of", "the")) or nxt.startswith(("Congress", "Congressional", "District"))):
        return "wrapped2"
    if l.endswith("Candidates") and (re.match(r"^\w+ to be Elected$", nxt) or nxt.startswith("Following are")):
        return "paragraph"
    if nxt.startswith("Vote for not more than") or nxt2.startswith("Vote for not more than"):
        return "commission"
    return None


def read_contest(lines: list[str], i: int, kind: str) -> tuple[str, int | None, dict | None, int]:
    """Title, vote limit, ranked info, and the index of the first candidate line."""
    l = lines[i]
    if kind == "inline":
        closed = re.search(r"\(Vote for[^)]*\)", l)
        phrase = l if closed else l + " " + lines[i + 1]
        return clean(l.split("(Vote for")[0]).rstrip(" -"), vote_for(phrase), None, i + 1 if closed else i + 2
    if kind == "wrapped2":
        return clean(f"{l} {lines[i + 1]}").rstrip(" -"), vote_for(lines[i + 2]), None, i + 3
    if kind == "wrapped":
        district = lines[i + 1].split("(Vote for")[0]
        return clean(f"{l} {district}").rstrip(" -"), vote_for(lines[i + 1]), None, i + 2
    if kind == "paragraph":
        k = i + 1
        if re.match(r"^\w+ to be Elected$", lines[k]):
            seats = VOTE_WORDS[lines[k].split()[0]]
            m = re.match(r"^Rank up to (\w+) Candidates$", lines[k + 1])
            k += 2 if m else 1
            instr = []
            while k < len(lines) and lines[k].startswith(("Special Instructions", "In the ")):
                instr.append(lines[k].rstrip("·").strip())
                k += 1
            ranked = {"seats": seats, "max_ranks": VOTE_WORDS.get(m.group(1), 0) if m else 0,
                      "text": clean(" ".join(instr))}
            return l, None, ranked, k
        para, k = [], i + 1
        while k < len(lines) and not (para and para[-1].endswith(".") and looks_like_name(lines[k])):
            para.append(lines[k])
            k += 1
        return l, vote_for(" ".join(para)), None, k
    # commission: title on one or two lines, then a "Vote for not more than ..." sentence
    k = i + 1
    title = [l]
    if not lines[k].startswith("Vote for not more than"):
        title.append(lines[k])
        k += 1
    para = []
    while k < len(lines) and not (para and para[-1].endswith(".")):
        para.append(lines[k])
        k += 1
    m = re.search(r"Vote for not more than (\w+)", " ".join(para))
    return clean(" ".join(title)), VOTE_WORDS.get(m.group(1).capitalize()) if m else None, None, k


def looks_like_name(l: str) -> bool:
    return 1 <= len(l.split()) <= 6 and l[0].isupper() and not l.endswith((".", ",", "?"))


STATE_MEASURE = re.compile(r"(?:^|\s)((Amendment|Proposition) (\w+) \((CONSTITUTIONAL|STATUTORY)\))$")
COURT_HEADER = re.compile(r"^(Colorado Supreme Court Justice|Colorado Court of Appeals Judge|District Court Judge"
                          r"|County Court Judge)\b")
LOCAL_MEASURE = re.compile(r"^(.*?)\s*Ballot (Issue|Question) (\w+)$")


def group_for(title: str, section: str) -> str:
    """Group from the title; some ballots print section headers out of reading order."""
    if section == "measures":
        return "measures"
    if re.match(r"^(\w+ County |County )(Commissioner|Clerk|Treasurer|Assessor|Sheriff|Surveyor|Coroner)", title):
        return "county"
    if re.match(r"^(City|Town) of |^Proposed Municipality", title) or re.search(r"\b(Mayor|Mayoral|Council)\b", title):
        return "city"
    if re.match(r"^Regional Transportation", title) or \
            re.search(r"(Fire|Metropolitan|Water|Sanitation|School|Library|Recreation|Park).* District", title):
        return "special_districts"
    return section


def split_choices(rest: list[str]) -> tuple[list[str], str]:
    """Choice labels after a question, joined across wrapped lines; plus any trailing heading prefix."""
    if rest[:2] == DEFAULT_CHOICES:
        return DEFAULT_CHOICES, " ".join(rest[2:])
    if len(rest) == 2 or not rest:
        return rest, ""
    joined: list[str] = []
    for line in rest:
        if joined and (line[0].islower() or not re.search(r"[.;]( or)?$", joined[-1])):
            joined[-1] += " " + line
        else:
            joined.append(line)
    return [re.sub(r";( or)?$|\.$", "", j) for j in joined], ""


def is_section(l: str) -> bool:
    return l in SECTIONS or bool(re.fullmatch(r"[A-Z][A-Za-z ]* Ballot Measures", l))


def stops(lines: list[str], k: int) -> bool:
    l = lines[k]
    return is_section(l) or bool(STATE_MEASURE.search(l) or LOCAL_MEASURE.match(l)) or bool(COURT_HEADER.match(l)) or \
        l.startswith(("Shall Justice", "Shall Judge")) or contest_start(lines, k) is not None


def extract(lines: list[str], sw: list[dict], fips: str, sample_url: str) -> list[dict]:
    lines = [l for l in lines if l != "<<PAGE>>"]
    ballot: list[dict] = []
    group = "federal"
    prov = {"source": sample_url}
    i = 0
    heading_prefix = ""  # first line of a two-line measure heading, e.g. "X District of" + "County Ballot Issue 6A"

    def add_local(item: dict) -> None:
        item.setdefault("district_id", None)
        item["provenance"] = prov
        ballot.append(item)

    while i < len(lines):
        l = lines[i]
        if is_section(l):
            group = SECTIONS.get(l, "measures")
            i += 1
            continue
        if COURT_HEADER.match(l) and "(Vote for" not in l:
            i += 1
            continue
        ms = STATE_MEASURE.search(l)
        ml = None if ms else LOCAL_MEASURE.match(l)
        if ms or ml:
            j = i + 1
            body: list[str] = []
            while j < len(lines) and not stops(lines, j):
                body.append(lines[j])
                j += 1
            last_q = max((n for n, b in enumerate(body) if "?" in b), default=len(body) - 1)
            text = re.sub(r"\s*\(Vote for One\)$", "", clean(" ".join(body[: last_q + 1])))
            choices, next_prefix = split_choices(body[last_q + 1:])
            l = clean(f"{heading_prefix} {l}")
            ml = LOCAL_MEASURE.match(l) if ml else None
            heading_prefix = next_prefix
            if ms:
                sid = match_statewide(ms.group(1), sw, "measure")
                ballot.append({"statewide": sid or f"CHECK: no statewide match for {l}"})
                if not sid:
                    notes.append(f"{l}: no statewide match")
            else:
                who, kind_word, letter = ml.group(1), ml.group(2), ml.group(3)
                # Trust a heading prefix like "City of Boulder" or "Timberline Fire Protection District".
                # Two-column ballots can leave debris like "District No. 2" instead; then use the text.
                core = re.sub(r"District of \w+ County$", "District", who)
                trusted = (len(who.split()) >= 2 and not who.startswith("District")
                           and not re.search(r"[a-z][A-Z]", who)
                           and len(re.findall(r"\b(County|District|Town of|City of)\b", core)) <= 1)
                title, district = clean(l), None
                if not trusted:
                    found = jurisdiction_in_text(text)
                    if found:
                        district, name = found
                        title = f"{name} Ballot {kind_word} {letter}"
                        notes.append(f"{clean(l)}: jurisdiction taken from its text: {name}; CHECK the printed name")
                        who = name
                    else:
                        title = f"Ballot {kind_word} {letter}"
                        notes.append(f"{clean(l)}: no jurisdiction found; CHECK")
                else:
                    who = re.sub(r" of (Boulder|Larimer) County$", "", who) if " District of " in f"{who} " else who
                    district = district_for(who)
                item = {"id": f"{slug(who) or 'district'}-{letter.lower()}", "kind": "measure",
                        "group": "measures", "district_id": district, "title": title,
                        "ballot_text": {"text": text, "source": sample_url}}
                if choices and choices != DEFAULT_CHOICES:
                    item["choices"] = choices
                    notes.append(f"{clean(l)}: choices {choices}")
                add_local(item)
            i = j
            continue
        if l.startswith(("Shall Justice", "Shall Judge")):
            q, j = [l], i + 1
            while j < len(lines) and not q[-1].endswith("?"):
                q.append(lines[j])
                j += 1
            question = clean(" ".join(q))
            sid = match_statewide(question, sw, "retention")
            if sid:
                ballot.append({"statewide": sid})
            else:
                m = re.match(r"Shall (?:Justice|Judge) (.+?) of the (.+?) be retained in office\?", question)
                name, court = (m.group(1), m.group(2)) if m else ("CHECK", "CHECK")
                add_local({
                    "id": f"retain-{slug(court)}-{slug(name)}", "kind": "retention", "group": "judges",
                    "title": f"{court} Judge {name}", "judge": name, "court": court,
                    "links": {"official": [{"label": "Judicial performance evaluation",
                                            "url": "https://judicialperformance.colorado.gov/judicial-evaluations"}]},
                })
            i = j
            continue
        kind = contest_start(lines, i)
        if not kind:
            i += 1
            continue
        title, n, ranked, k = read_contest(lines, i, kind)
        cands, write_in = [], False
        while k < len(lines) and not stops(lines, k):
            if lines[k] == "Write-in":
                write_in = True
            else:
                name, party = split_party(lines[k])
                cands.append({"name": name, **({"party": party} if party else {})})
            k += 1
        sid = match_statewide(title, sw, "candidate_contest")
        if sid:
            ballot.append({"statewide": sid})
        else:
            item = {"id": slug(title), "kind": "candidate_contest", "group": group_for(title, group),
                    "district_id": district_for(title), "title": title, "candidates": cands, "write_in": write_in}
            if ranked:
                item.update({"ranked": True, "max_ranks": ranked["max_ranks"], "seats": ranked["seats"],
                             "rcv_instructions": {"text": ranked["text"], "source": sample_url}})
            else:
                item["vote_for"] = n or 1
                if not n:
                    notes.append(f"{title}: vote limit not found, set to 1; CHECK")
            add_local(item)
            if title.startswith(("State ", "United States", "Representative", "Regent", "Governor")):
                notes.append(f"{title}: looks statewide but has no statewide match; CHECK")
        i = k
    return ballot


def jurisdiction_in_text(text: str) -> tuple[str | None, str] | None:
    """(district id, name) from "SHALL <JURISDICTION> TAXES/DEBT ..." style ballot text, if found."""
    up = clean(text).upper()
    m = re.search(r"BOUNDARIES OF THE PROPOSED ([A-Z][A-Z .\-]+?DISTRICT(?: NO\. ?[A-Z0-9-]+)?)\b", up) or \
        re.search(r"SHALL (?:THE )?((?:CITY|TOWN) OF [A-Z ]+?|[A-Z][A-Z .\-]*?(?:COUNTY|DISTRICT(?: NO\. ?[A-Z0-9-]+)?"
                  r"(?: \([A-Z ]+\))?))(?: TAXES| DEBT| BE | WAIVE)", up)
    if not m:
        return None
    name = m.group(1).strip()
    if re.fullmatch(r"[A-Z]+ COUNTY", name):
        return None, name.title()
    pretty = re.sub(r"\bNo\b", "No.", name.title().replace("No.", "No")).replace("No..", "No.")
    pretty = re.sub(r"\b(Re-\w+)\b", lambda x: x.group(1).upper().replace("RE-", "RE-"), pretty)
    m2 = re.match(r"^(City|Town) Of (.+)$", pretty)
    if m2:
        return "city-" + slug(m2.group(2)), f"{m2.group(1)} of {m2.group(2)}"
    return slug(pretty), pretty


def district_for(text: str) -> str | None:
    m = re.match(r"^(City|Town) of ([A-Za-z ]+?)(?: Ballot| Mayor| Council| Town|$)", text)
    if m:
        return "city-" + slug(m.group(2))
    if text.startswith("Proposed Municipality of"):
        return "city-" + slug(text.split("Proposed Municipality of ")[1].split(" - ")[0])
    m = re.match(r"^Regional Transportation District Director - District (\w+)", text)
    if m:
        return f"rtd-{m.group(1).lower()}"
    if text.startswith(("Boulder County", "County", "Larimer County")) or "Judicial District" in text:
        return None
    m = re.search(r"SHALL ([A-Z][A-Z ]+? DISTRICT)\b", text.upper())
    if m:
        return slug(m.group(1))
    if re.match(r"^[A-Z][A-Za-z ]+ District$", text):
        return slug(text)
    if text:
        return "CHECK: " + slug(text)
    return None


def districts(ballot: list[dict]) -> list[dict]:
    """One entry per local district, named as the ballot names it."""
    out: dict[str, dict] = {}
    for b in ballot:
        did = b.get("district_id")
        if not did or did in out or did.startswith("CHECK"):
            continue
        title = b["title"]
        m = re.match(r"^((?:City|Town) of [A-Za-z ]+?|Proposed Municipality of \w+)(?: Ballot| Mayor| Council| Town| -|$)",
                     title)
        if m:
            out[did] = {"id": did, "type": "city", "name": m.group(1)}
        elif did.startswith("rtd-"):
            out[did] = {"id": did, "type": "special_district",
                        "name": f"Regional Transportation District, Director District {did[4:].upper()}"}
        else:
            nm = re.sub(r" (of \w+ County )?Ballot (Issue|Question) \w+$", "", title)
            out[did] = {"id": did, "type": "special_district", "name": nm}
    return list(out.values())


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print(__doc__)
        return 2
    _, txt, statewide, fips, name, url, out = argv
    sw = yaml.safe_load(open(statewide, encoding="utf-8"))["items"]
    ballot = extract(lines_of(txt), sw, fips, url)
    doc = {"county_fips": fips, "name": name, "districts": districts(ballot), "ballot": ballot}
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# {name} County, November 3, 2026: every contest and question on any ballot in the county,\n"
                f"# in printed order. Drafted by pipeline/extract_sample_ballot.py from the compiled sample ballot\n"
                f"# ({url}), then corrected by a person. Search for CHECK.\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=110)
    refs = sum(1 for b in ballot if "statewide" in b)
    print(f"Wrote {out}: {refs} statewide references, {len(ballot) - refs} local items")
    for n in notes:
        print(f"NOTE  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
