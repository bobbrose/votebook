"""Print the ballot for a ZIP code from the current source files, verified or not.

    python -m pipeline.preview 80302            # every contest and question, grouped, in printed order
    python -m pipeline.preview 80302 --full     # also measure text and ranked-choice instructions
    python -m pipeline.preview 80302 --election co-2026-11-03

A development and verification aid, not the app. It reads sources/ directly, so it works
before the verification records are signed, and says so at the top. The selection rules
follow tech-spec C3: an item shows when it is on every ballot in the county or its district
touches the ZIP; items whose district may not cover the whole ZIP are marked "depends on".
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from .compile import compile_election

ROOT = Path(__file__).resolve().parent.parent
HEADINGS = {
    "federal": "FEDERAL", "state": "STATE", "legislature": "LEGISLATURE", "special_districts": "SPECIAL DISTRICTS",
    "county": "COUNTY", "city": "CITY AND TOWN", "judges": "JUDGES", "measures": "MEASURES",
}


def district_name(did: str, names: dict[str, str]) -> str:
    if did in names:
        return names[did]
    for prefix, label in (("co-cd-", "Congressional District "), ("co-senate-", "State Senate District "),
                          ("co-house-", "State House District ")):
        if did.startswith(prefix):
            return label + did.removeprefix(prefix)
    return did


def ballot_for(zip_code: str, res) -> list[tuple[dict, list[tuple[dict, str | None]]]]:
    """[(county, [(item, depends_on_name_or_None), ...]), ...] for each county the ZIP touches."""
    entry = res.zip_index["zips"][zip_code]
    touched = {d for ids in entry["districts"].values() for d in ids}
    types_by_district = {d: kind for kind, ids in entry["districts"].items() for d in ids}
    sw = {it["id"]: it for it in res.statewide["items"]}
    names = {d["id"]: d["name"] for d in res.statewide.get("districts", [])}
    out = []
    for fips in entry["counties"]:
        county = res.counties["counties"][fips]
        names.update({d["id"]: d["name"] for d in county["districts"]})
        rows = []
        for it in [sw[i] for i in county["statewide_order"]] + county["items"]:
            did = it.get("district_id")
            if did is None:
                rows.append((it, None))
            elif did in touched:
                same_kind = [d for d in entry["districts"].get(types_by_district[did], [])]
                certain = len(same_kind) == 1 and types_by_district[did] != "place"
                rows.append((it, None if certain else district_name(did, names)))
            elif did.startswith(("co-cd-", "co-senate-", "co-house-", "city-")):
                continue  # a district the ZIP does not touch
            else:
                rows.append((it, district_name(did, names)))  # special district: boundaries not mapped yet
        rows.sort(key=lambda r: r[0]["ballot_order"])
        out.append((county, rows))
    return out


def describe(it: dict, full: bool) -> list[str]:
    lines = []
    if it["kind"] == "candidate_contest":
        if it.get("ranked"):
            lines.append(f"Rank up to {it['max_ranks']} ({it['seats']} to be elected). Ranked choice.")
            if full:
                lines += textwrap.wrap(it["rcv_instructions"]["text"], 90)
        else:
            lines.append(f"Vote for {'up to ' if it['vote_for'] > 1 else ''}{it['vote_for']}")
        for c in it["candidates"]:
            lines.append(f"  [ ] {c['name']}" + (f"  ({c['party']})" if c.get("party") else ""))
        if it.get("write_in"):
            lines.append("  [ ] Write-in")
    elif it["kind"] == "retention":
        lines.append("Yes / Undecided / No")
    else:
        choices = it.get("choices") or ["Yes", "No"]
        if len(choices) == 2:
            lines.append(f"{choices[0]} / Undecided / {choices[1]}")
        else:
            lines.append("Pick one: " + " | ".join(choices))
        if full:
            lines += textwrap.wrap(it["ballot_text"]["text"], 90)
            table = it["ballot_text"].get("table")
            if table:
                lines.append(f"[table] {table['caption']}: {len(table['rows'])} rows")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip", help="5-digit ZIP code")
    ap.add_argument("--election", default="co-2026-11-03")
    ap.add_argument("--full", action="store_true", help="include measure text and ranked-choice instructions")
    args = ap.parse_args(argv)

    res = compile_election(ROOT, args.election, "0000.00.00-0")
    if res.zip_index is None:
        print("\n".join(res.errors))
        return 1
    z = args.zip
    if z not in res.zip_index["zips"]:
        state = res.zip_index["other_states"].get(z[:3])
        if state:
            site = res.zip_index["states"].get(state, {})
            print(f"{z} is outside Colorado ({site.get('name', state)}). This site covers Colorado ballots only.")
            print(f"Your state's official election site: {site.get('election_site', 'unknown')}")
        else:
            print(f"{z} is not a Colorado ZIP code we know.")
        return 0

    unsigned = [e for e in res.errors if "verification" in e or "certified text" in e]
    if unsigned:
        print(f"DRAFT DATA: {len(unsigned)} verification problems; nothing here is verified yet.\n")
    for county, rows in ballot_for(z, res):
        cov = county["coverage"]["status"]
        label = "Verified complete" if cov == "verified_complete" else (
            "Local items drafted, NOT VERIFIED" if county["items"] else "Statewide items only")
        print(f"=== {z} / {county['name']} County: {label} ({len(rows)} items)")
        group = None
        for it, depends in rows:
            if it["group"] != group:
                group = it["group"]
                print(f"\n-- {HEADINGS.get(group, group.upper())} " + "-" * 40)
            tag = f"   [depends on: {depends}]" if depends else ""
            print(f"\n{it['title']}{tag}")
            for line in describe(it, args.full):
                print(f"    {line}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
