"""Writes tests/fixtures/data/2026-11-03/: a small FICTIONAL ballot for app tests (not Colorado data).

    python3 tests/fixtures/make_fixture.py
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "data" / "2026-11-03"
H = {"schema_version": 1, "data_version": "2026.10.15-1", "election_id": "co-2026-11-03"}
P = {"source": "https://example.org/sample.pdf", "verified_at": "2026-10-10"}
L = lambda **kw: {"official": [{"label": "Official candidate list", "url": "https://example.org/list"}], "explainers": [],
                  "support": None, "oppose": None, **kw}


def contest(id, title, group, order, district, names, vote_for=1, write_in=False, **extra):
    c = {"id": id, "kind": "candidate_contest", "group": group, "ballot_order": order, "district_id": district,
         "title": title, "ranked": False, "vote_for": vote_for, "write_in": write_in, "links": L(), "provenance": P,
         "candidates": [{"id": f"cand-{n.lower().replace(' ', '-')}", "name": n, "party": p, "order": i + 1, "links": []}
                        for i, (n, p) in enumerate(names)]}
    c.update(extra)
    return c


def measure(id, title, order, district, text, **extra):
    m = {"id": id, "kind": "measure", "group": "measures", "ballot_order": order, "district_id": district, "title": title,
         "ballot_text": {"text": text, "source": "https://example.org/bluebook"}, "links": L(), "provenance": P}
    m.update(extra)
    return m


statewide = {**H, "districts": [], "items": [
    contest("us-senate", "United States Senator", "federal", 1000, None,
            [("Avery Sample", "Party A"), ("Blake Sample", "Party B"), ("Casey Sample", None)], write_in=True),
    contest("state-house-1", "State Representative - District 1", "legislature", 2000, "co-house-1", [("Drew Sample", "Party A")]),
    contest("state-house-2", "State Representative - District 2", "legislature", 3000, "co-house-2", [("Emery Sample", "Party B")]),
    {"id": "retain-supreme-jordan-doe", "kind": "retention", "group": "judges", "ballot_order": 4000, "district_id": None,
     "title": "Colorado Supreme Court Justice Jordan Doe", "judge": "Jordan Doe", "court": "Colorado Supreme Court",
     "links": {"official": [{"label": "Judicial performance evaluation", "url": "https://example.org/jpe"}],
               "explainers": [], "support": None, "oppose": None}, "provenance": P},
    measure("amendment-1", "Amendment 1", 5000, None, "Shall there be an amendment to the example constitution?",
            links=L(support={"label": "Yes on 1", "url": "https://example.org/yes"})),
]}

county_a = {"county_fips": "08001", "name": "Alpha",
            "coverage": {"status": "verified_complete", "source": "https://example.org/alpha.pdf",
                         "verified_at": "2026-10-10", "verified_by": "Checker"},
            "statewide_order": ["us-senate", "state-house-1", "state-house-2", "retain-supreme-jordan-doe", "amendment-1"],
            "districts": [{"id": "city-alpha", "type": "city", "name": "City of Alpha"},
                          {"id": "alpha-fire-district", "type": "special_district", "name": "Alpha Fire District"}],
            "items": [
                contest("alpha-council", "City of Alpha Council", "city", 3010, "city-alpha",
                        [("Finley Sample", None), ("Gray Sample", None), ("Harper Sample", None)], vote_for=2),
                {**contest("alpha-mayor", "City of Alpha Mayor", "city", 3020, "city-alpha",
                           [("Indy Sample", None), ("Jules Sample", None)]),
                 "ranked": True, "max_ranks": 2, "seats": 1,
                 "rcv_instructions": {"text": "Rank candidates in order of preference.", "source": "https://example.org/alpha.pdf"}},
                measure("alpha-2a", "City of Alpha Ballot Question 2A", 5010, "city-alpha", "Shall the charter be amended?",
                        choices=["For the Measure", "Against the Measure"]),
                measure("alpha-200", "Alpha County Ballot Question 200", 5020, None, "By what method shall the board be elected?",
                        choices=["By districts", "At large", "Half and half"]),
                measure("alpha-fire-7a", "Alpha Fire District Ballot Issue 7A", 5030, "alpha-fire-district",
                        "Shall the district taxes be increased?"),
            ]}
del county_a["items"][1]["vote_for"]
county_b = {"county_fips": "08003", "name": "Beta", "coverage": {"status": "statewide_only"},
            "statewide_order": ["us-senate", "state-house-2", "retain-supreme-jordan-doe", "amendment-1"],
            "districts": [], "items": []}
counties = {**H, "counties": {"08001": county_a, "08003": county_b}}
zip_index = {**H, "zips": {
    "80001": {"counties": ["08001"], "districts": {"state_house": ["co-house-1", "co-house-2"], "place": ["city-alpha"]}},
    "80002": {"counties": ["08001", "08003"], "districts": {"state_house": ["co-house-2"]}},
    "80003": {"counties": ["08003"], "districts": {"state_house": ["co-house-2"]}},
}, "other_states": {"841": "UT"}, "states": {"UT": {"name": "Utah", "election_site": "https://vote.gov/register/utah"}}}

OUT.mkdir(parents=True, exist_ok=True)
for name, doc in [("statewide.json", statewide), ("counties.json", counties), ("zip-index.json", zip_index)]:
    (OUT / name).write_text(json.dumps(doc, indent=1) + "\n")
print("wrote", OUT)
