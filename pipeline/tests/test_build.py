"""Pipeline tests: a small fictional election, plus one broken variant per check.

The fixture election (co-2099-11-03) is made up. It is not Colorado ballot data.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from pipeline import build

ELECTION = "co-2099-11-03"
JPE = {"label": "Judicial performance evaluation", "url": "https://example.org/jpe/doe"}
PROV = {"source": "https://example.org/source.pdf"}


def statewide() -> dict:
    return {
        "election_id": ELECTION,
        "districts": [{"id": "co-cd-1", "type": "congressional", "name": "Congressional District 1"},
                      {"id": "co-cd-2", "type": "congressional", "name": "Congressional District 2"}],
        "items": [
            {"id": "us-senate", "kind": "candidate_contest", "group": "federal", "title": "U.S. Senator",
             "vote_for": 1, "write_in": True, "provenance": PROV,
             "candidates": [{"name": "Alex Example", "party": "Party A"}, {"name": "Blair Example"}]},
            {"id": "cd-1-rep", "kind": "candidate_contest", "group": "federal", "district_id": "co-cd-1",
             "title": "U.S. Representative, District 1", "vote_for": 1, "provenance": PROV,
             "candidates": [{"name": "Casey Example"}]},
            {"id": "cd-2-rep", "kind": "candidate_contest", "group": "federal", "district_id": "co-cd-2",
             "title": "U.S. Representative, District 2", "vote_for": 1, "provenance": PROV,
             "candidates": [{"name": "Dana Example"}]},
            {"id": "supreme-doe", "kind": "retention", "group": "judges", "title": "Supreme Court Justice Doe",
             "judge": "Jordan Doe", "court": "Colorado Supreme Court", "links": {"official": [JPE]},
             "provenance": PROV},
            {"id": "amendment-1", "kind": "measure", "group": "measures", "title": "Amendment 1",
             "ballot_text": {"text": "Shall there be an amendment  to the example constitution?",
                             "source": "https://example.org/bluebook"},
             "links": {"official": [{"label": "Blue Book analysis", "url": "https://example.org/bluebook"}]},
             "provenance": PROV},
        ],
    }


def statewide_record() -> dict:
    return {
        "scope": "statewide", "election_id": ELECTION, "checked_by": "Checker One", "checked_at": "2099-10-01",
        "groups": [{"group": "federal", "count": 3}, {"group": "judges", "count": 1},
                   {"group": "measures", "count": 1}],
        "measures": {"amendment-1": "Shall there be an amendment to the example constitution?"},
        "spot_check": {"by": "Checker Two", "at": "2099-10-02", "items_checked": 1},
    }


def county() -> dict:
    return {
        "county_fips": "08013", "name": "Boulder",
        "districts": [{"id": "city-boulder", "type": "city", "name": "City of Boulder"}],
        "ballot": [
            {"statewide": "us-senate"},
            {"statewide": "cd-2-rep"},
            {"id": "boulder-commissioner-1", "kind": "candidate_contest", "group": "county",
             "title": "County Commissioner, District 1", "vote_for": 1, "provenance": PROV,
             "candidates": [{"name": "Emery Example"}]},
            {"statewide": "supreme-doe"},
            {"statewide": "amendment-1"},
            {"id": "boulder-city-2c", "kind": "measure", "group": "measures", "district_id": "city-boulder",
             "title": "Ballot Question 2C",
             "ballot_text": {"text": "Shall the example city do the example thing?",
                             "source": "https://example.org/boulder-sample.pdf"},
             "provenance": PROV},
        ],
    }


def county_record() -> dict:
    return {
        "scope": "08013", "election_id": ELECTION, "sample_ballot": "https://example.org/boulder-sample.pdf",
        "checked_by": "Checker One", "checked_at": "2099-10-01",
        "groups": [{"group": "federal", "count": 2}, {"group": "county", "count": 1},
                   {"group": "judges", "count": 1}, {"group": "measures", "count": 2}],
        "measures": {"amendment-1": "Shall there be an amendment to the example constitution?",
                     "boulder-city-2c": "Shall the example city do the example thing?"},
        "spot_check": {"by": "Checker Two", "at": "2099-10-02", "items_checked": 1},
    }


def geo() -> dict:
    return {
        "counties": {"08013": {"name": "Boulder", "districts": ["co-cd-2"]},
                     "08001": {"name": "Adams", "districts": ["co-cd-1", "co-cd-2"]}},
        "zips": {"80302": {"counties": ["08013"], "districts": {"congressional": ["co-cd-2"]}},
                 "80022": {"counties": ["08001"], "districts": {"congressional": ["co-cd-1", "co-cd-2"]}}},
        "other_states": {"840": "UT"},
    }


class World:
    def __init__(self, root: Path):
        self.root = root
        self.parts = {
            f"sources/{ELECTION}/statewide.yaml": statewide(),
            f"sources/{ELECTION}/08013.yaml": county(),
            "verification/statewide.yaml": statewide_record(),
            "verification/08013.yaml": county_record(),
            "sources/states.yaml": {"UT": {"name": "Utah", "election_site": "https://vote.utah.gov"}},
        }
        self.geo = geo()
        self.write()

    def write(self) -> None:
        for rel, doc in self.parts.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        (self.root / f"sources/{ELECTION}/geo.json").write_text(json.dumps(self.geo), encoding="utf-8")

    def remove(self, rel: str) -> None:
        del self.parts[rel]
        (self.root / rel).unlink()

    def build(self, *extra: str, today: str = "2099-10-05") -> int:
        return build.main(["--election", ELECTION, "--root", str(self.root), "--today", today, *extra])

    def data(self, name: str) -> dict:
        return json.loads((self.root / "data/2099-11-03" / name).read_text(encoding="utf-8"))


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def fails_with(world: World, capsys, text: str) -> None:
    assert world.build("--check") == 1
    out = capsys.readouterr().out
    assert text in out, out


# ---------- the happy path ----------

def test_builds_all_files(world: World, capsys) -> None:
    assert world.build() == 0
    for name in ["zip-index.json", "statewide.json", "counties.json", "manifest.json", "hashes.txt",
                 "CHANGELOG.md", "schema/statewide.schema.json"]:
        assert (world.root / "data/2099-11-03" / name).exists(), name
    assert world.data("statewide.json")["data_version"] == "2099.10.05-1"


def test_order_places_local_items_between_statewide_items(world: World) -> None:
    assert world.build() == 0
    sw = {i["id"]: i["ballot_order"] for i in world.data("statewide.json")["items"]}
    boulder = world.data("counties.json")["counties"]["08013"]
    local = {i["id"]: i["ballot_order"] for i in boulder["items"]}
    assert sw["cd-2-rep"] < local["boulder-commissioner-1"] < sw["supreme-doe"]
    assert sw["amendment-1"] < local["boulder-city-2c"]
    assert boulder["statewide_order"] == ["us-senate", "cd-2-rep", "supreme-doe", "amendment-1"]
    assert boulder["coverage"]["status"] == "verified_complete"


def test_unverified_county_gets_statewide_items_for_its_districts(world: World) -> None:
    world.geo["counties"]["08013"]["districts"] = ["co-cd-2"]
    world.write()
    assert world.build() == 0
    adams = world.data("counties.json")["counties"]["08001"]
    assert adams["coverage"] == {"status": "statewide_only"}
    assert adams["items"] == []
    assert adams["statewide_order"] == ["us-senate", "cd-1-rep", "cd-2-rep", "supreme-doe", "amendment-1"]


def test_zip_index_has_colorado_zips_and_other_states(world: World) -> None:
    assert world.build() == 0
    z = world.data("zip-index.json")
    assert z["zips"]["80302"]["counties"] == ["08013"]
    assert z["other_states"]["840"] == "UT"
    assert z["states"]["UT"]["election_site"].startswith("https://")


def test_every_published_file_is_hashed(world: World) -> None:
    assert world.build() == 0
    listed = (world.root / "data/2099-11-03/hashes.txt").read_text().split("\n")
    names = {l.split("  ")[1] for l in listed if l}
    assert {"zip-index.json", "statewide.json", "counties.json", "manifest.json"} <= names


def test_check_passes_when_data_is_current(world: World, capsys) -> None:
    assert world.build() == 0
    assert world.build("--check") == 0
    assert "OK" in capsys.readouterr().out


# ---------- versioning and changelog ----------

def test_rebuild_without_changes_keeps_version(world: World) -> None:
    assert world.build() == 0
    assert world.build(today="2099-10-06") == 0
    assert world.data("statewide.json")["data_version"] == "2099.10.05-1"


def test_change_bumps_version_and_writes_changelog(world: World) -> None:
    assert world.build() == 0
    world.parts[f"sources/{ELECTION}/statewide.yaml"]["items"][0]["candidates"][1]["name"] = "Blair Corrected"
    world.write()
    assert world.build(today="2099-10-07") == 0
    assert world.data("statewide.json")["data_version"] == "2099.10.07-1"
    log = (world.root / "data/2099-11-03/CHANGELOG.md").read_text()
    assert "- 2099-10-07: us-senate (U.S. Senator): changed candidates" in log


def test_check_fails_when_sources_changed_but_data_not_rebuilt(world: World, capsys) -> None:
    assert world.build() == 0
    world.parts[f"sources/{ELECTION}/statewide.yaml"]["items"][0]["title"] = "U.S. Senator (changed)"
    world.write()
    fails_with(world, capsys, "data/ is out of date")


# ---------- one failing fixture per check ----------

def test_fails_when_county_order_differs_from_record(world: World, capsys) -> None:
    ballot = world.parts[f"sources/{ELECTION}/08013.yaml"]["ballot"]
    ballot[2], ballot[3] = ballot[3], ballot[2]  # judges printed before the county race
    world.write()
    fails_with(world, capsys, "ballot order or counts differ from the verification record (AC-07)")


def test_fails_when_statewide_items_out_of_order_in_county(world: World, capsys) -> None:
    ballot = world.parts[f"sources/{ELECTION}/08013.yaml"]["ballot"]
    ballot[0], ballot[1] = ballot[1], ballot[0]
    world.write()
    fails_with(world, capsys, "statewide item us-senate is out of statewide order (AC-07)")


def test_fails_when_counts_differ(world: World, capsys) -> None:
    world.parts["verification/statewide.yaml"]["groups"][0]["count"] = 4
    world.write()
    fails_with(world, capsys, "statewide: ballot order or counts differ")


def test_fails_when_ballot_text_does_not_match_certified_text(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"]["measures"]["boulder-city-2c"] = "Shall the city do something else?"
    world.write()
    fails_with(world, capsys, "boulder-city-2c: ballot text does not match the certified text (AC-11)")


def test_fails_when_measure_has_no_certified_text(world: World, capsys) -> None:
    del world.parts["verification/statewide.yaml"]["measures"]["amendment-1"]
    world.write()
    fails_with(world, capsys, "amendment-1: no certified text in the verification record (AC-11)")


def test_fails_when_retention_has_no_evaluation_link(world: World, capsys) -> None:
    world.parts[f"sources/{ELECTION}/statewide.yaml"]["items"][3]["links"] = {"official": []}
    world.write()
    fails_with(world, capsys, "Judicial performance evaluation")


def test_fails_when_ranked_contest_has_no_instructions(world: World, capsys) -> None:
    ballot = world.parts[f"sources/{ELECTION}/08013.yaml"]["ballot"]
    contest = ballot[2]
    del contest["vote_for"]
    contest.update({"ranked": True, "max_ranks": 1, "seats": 1})
    world.write()
    fails_with(world, capsys, "'rcv_instructions' is a required property")


def test_fails_when_county_has_no_verification_record(world: World, capsys) -> None:
    world.remove("verification/08013.yaml")
    fails_with(world, capsys, "no verification record; unverified items cannot be published (AC-27)")


def test_fails_when_spot_check_is_by_the_same_person(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"]["spot_check"]["by"] = "Checker One"
    world.write()
    fails_with(world, capsys, "spot check must be done by a second person")


def test_fails_when_spot_check_too_small(world: World, capsys) -> None:
    world.parts["verification/statewide.yaml"]["spot_check"]["items_checked"] = 0
    world.write()
    fails_with(world, capsys, "needs at least 1")


def test_builds_when_spot_check_skipped_with_reason(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"]["spot_check"] = {"skipped": "pilot, no second checker"}
    world.write()
    assert world.build() == 0
    assert "SKIPPED  county 08013: spot check skipped: pilot, no second checker" in capsys.readouterr().out


def test_fails_when_spot_check_skipped_without_reason(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"]["spot_check"] = {"skipped": ""}
    world.write()
    fails_with(world, capsys, "spot check skipped with no reason")


def test_fails_on_schema_error(world: World, capsys) -> None:
    world.parts[f"sources/{ELECTION}/statewide.yaml"]["items"][0]["group"] = "galactic"
    world.write()
    fails_with(world, capsys, "schema: group")


def test_fails_over_size_budget(world: World, capsys, monkeypatch) -> None:
    monkeypatch.setattr(build, "COUNTIES_BUDGET_BYTES", 10)
    assert world.build() == 1
    assert "budget is 10" in capsys.readouterr().out


def test_fails_on_missing_hash(capsys) -> None:
    files = {"statewide.json": "{}\n", "hashes.txt": ""}
    errors: list[str] = []
    build.check_hashes(files, errors)
    assert errors == ["hashes.txt: missing or wrong hash for statewide.json (AC-37)"]


def test_verified_date_comes_from_the_verification_record(world: World) -> None:
    world.parts["verification/08013.yaml"]["checked_at"] = "2099-10-03"
    world.write()
    assert world.build() == 0
    sw = world.data("statewide.json")["items"][0]
    local = world.data("counties.json")["counties"]["08013"]["items"][0]
    assert sw["provenance"]["verified_at"] == "2099-10-01"
    assert local["provenance"]["verified_at"] == "2099-10-03"


def test_draft_mode_writes_data_marked_draft_even_when_checks_fail(world: World, tmp_path: Path) -> None:
    world.remove("verification/08013.yaml")
    out = tmp_path / "draft"
    assert build.main(["--election", ELECTION, "--root", str(world.root), "--draft-out", str(out)]) == 0
    counties = json.loads((out / "2099-11-03" / "counties.json").read_text())
    assert counties["counties"]["08013"]["coverage"] == {"status": "draft"}
    assert counties["data_version"] == "draft"
    assert not (world.root / "data").exists()  # the real output is untouched


def unsigned(record: dict) -> dict:
    return {**record, "checked_by": None, "checked_at": None, "groups": [], "measures": {}, "spot_check": {}}


def test_publish_unverified_builds_and_labels_the_scope_unverified(world: World, capsys) -> None:
    decision = {"by": "Owner", "reason": "pilot testers review it"}
    world.parts["verification/08013.yaml"] = {**unsigned(county_record()), "publish_unverified": decision}
    world.parts["verification/statewide.yaml"] = {**unsigned(statewide_record()), "publish_unverified": decision}
    world.write()
    assert world.build() == 0
    out = capsys.readouterr().out
    assert "UNVERIFIED  county 08013: published unverified by Owner: pilot testers review it" in out
    assert "UNVERIFIED    county 08013: verification record is missing checked_by" in out
    boulder = world.data("counties.json")["counties"]["08013"]
    assert boulder["coverage"] == {"status": "unverified", "source": "https://example.org/boulder-sample.pdf"}
    assert boulder["items"][0]["provenance"]["verified_at"] == "0000-00-00"
    assert world.data("statewide.json")["items"][0]["provenance"]["verified_at"] == "0000-00-00"


def test_publish_unverified_needs_a_name_and_reason(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"] = {**unsigned(county_record()), "publish_unverified": {"by": "Owner"}}
    world.write()
    fails_with(world, capsys, "publish_unverified needs both by and reason")


def test_publish_unverified_does_not_hide_data_errors(world: World, capsys) -> None:
    world.parts["verification/08013.yaml"] = {**unsigned(county_record()),
                                              "publish_unverified": {"by": "Owner", "reason": "pilot"}}
    world.parts[f"sources/{ELECTION}/08013.yaml"]["ballot"][2]["group"] = "galactic"
    world.write()
    fails_with(world, capsys, "schema: ")


def test_a_verified_scope_ignores_publish_unverified(world: World) -> None:
    world.parts["verification/08013.yaml"]["publish_unverified"] = {"by": "Owner", "reason": "not needed"}
    world.write()
    assert world.build() == 0
    assert world.data("counties.json")["counties"]["08013"]["coverage"]["status"] == "verified_complete"
