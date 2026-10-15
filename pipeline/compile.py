"""Compile source YAML into published ballot data, enforcing every data check.

Inputs for one election (see pipeline/README.md for the formats):
    sources/<election>/statewide.yaml        statewide items in printed order
    sources/<election>/<fips>.yaml           a county's full ballot in printed order
    sources/<election>/geo.json              ZIP and county district intersections (from zip_index.py)
    sources/states.yaml                      state election sites for non-Colorado ZIPs
    verification/statewide.yaml              human verification record for statewide items
    verification/<fips>.yaml                 human verification record for a county

Every check adds an error instead of raising, so one run reports every problem.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from . import schemas

# Statewide items are spaced this far apart so a county's local items fit between them.
STATEWIDE_STEP = 1000
LOCAL_STEP = 10
JPE_LABEL = "Judicial performance evaluation"
SPOT_CHECK_SHARE = 0.10
UNVERIFIED_DATE = "0000-00-00"


class BuildError(Exception):
    pass


@dataclass
class Result:
    statewide: dict[str, Any] | None = None
    counties: dict[str, Any] | None = None
    zip_index: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")


class _Loader(yaml.SafeLoader):
    """Safe loader that keeps dates as strings, since the published files use ISO date strings."""


_Loader.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def norm_text(text: str) -> str:
    return " ".join(text.split())


def normalize_item(raw: dict[str, Any], verified_at: str | None) -> dict[str, Any]:
    """Fill defaults so source YAML can stay short; the schema then checks the result.

    An item's verified date comes from the human verification record that covers it,
    never from the source file, so nothing looks verified before a person has checked it.
    """
    item = dict(raw)
    if isinstance(item.get("provenance"), dict):
        # Placeholder when unsigned: the build already fails on the unsigned record, so it is never published.
        item["provenance"] = {**item["provenance"], "verified_at": verified_at or UNVERIFIED_DATE}
    links = dict(item.get("links") or {})
    links.setdefault("official", [])
    links.setdefault("explainers", [])
    links.setdefault("support", None)
    links.setdefault("oppose", None)
    item["links"] = links
    item.setdefault("district_id", None)
    if item.get("kind") == "candidate_contest":
        item.setdefault("ranked", False)
        item.setdefault("write_in", False)
        cands = []
        for i, c in enumerate(item.get("candidates") or [], start=1):
            c = dict(c)
            c.setdefault("id", "cand-" + slug(c.get("name", str(i))))
            c.setdefault("party", None)
            c.setdefault("order", i)
            c.setdefault("links", [])
            cands.append(c)
        item["candidates"] = cands
    return item


# ---------- checks shared by statewide and county ballots ----------

def check_items(where: str, items: list[dict[str, Any]], res: Result) -> None:
    validator = jsonschema.Draft202012Validator({"$defs": schemas.DEFS, "$ref": "#/$defs/item"})
    seen: set[str] = set()
    for it in items:
        iid = it.get("id", "?")
        for e in sorted(validator.iter_errors(it), key=lambda e: list(e.path)):
            path = "/".join(str(p) for p in e.path)
            res.err(f"{where} {iid}", f"schema: {path + ': ' if path else ''}{e.message}")
        if iid in seen:
            res.err(f"{where} {iid}", "duplicate item id")
        seen.add(iid)
        if it.get("kind") == "retention":
            labels = [l.get("label") for l in it.get("links", {}).get("official", [])]
            if not labels or labels[0] != JPE_LABEL:
                res.err(f"{where} {iid}", f'retention needs "{JPE_LABEL}" as its first official link (AC-41)')
        if it.get("kind") == "candidate_contest":
            orders = [c.get("order") for c in it.get("candidates", [])]
            if orders != list(range(1, len(orders) + 1)):
                res.err(f"{where} {iid}", "candidate order must be 1..n in ballot order")
            cids = [c.get("id") for c in it.get("candidates", [])]
            if len(set(cids)) != len(cids):
                res.err(f"{where} {iid}", "duplicate candidate id")
            if it.get("ranked"):
                options = len(cids) + (1 if it.get("write_in") else 0)
                if it.get("max_ranks", 0) > options:
                    res.err(f"{where} {iid}", "max_ranks is more than the candidates and write-in on the ballot")


def check_verification(where: str, printed: list[dict[str, Any]], record: dict[str, Any] | None,
                       res: Result) -> None:
    """Compare a ballot in printed order with its human verification record (AC-07, AC-11)."""
    if record is None:
        res.err(where, "no verification record; unverified items cannot be published (AC-27)")
        return
    for key in ("checked_by", "checked_at", "groups", "spot_check"):
        if not record.get(key):
            res.err(where, f"verification record is missing {key}")
    # Group sequence and counts as printed.
    runs: list[list[Any]] = []
    for it in printed:
        if runs and runs[-1][0] == it.get("group"):
            runs[-1][1] += 1
        else:
            runs.append([it.get("group"), 1])
    expected = [[g.get("group"), g.get("count")] for g in record.get("groups") or []]
    if runs != expected:
        res.err(where, "ballot order or counts differ from the verification record (AC-07). "
                f"Built: {fmt_runs(runs)}. Record: {fmt_runs(expected)}")
    # Certified measure text.
    certified = record.get("measures") or {}
    measures = {it["id"]: it for it in printed if it.get("kind") == "measure"}
    for mid, it in measures.items():
        if mid not in certified:
            res.err(where, f"{mid}: no certified text in the verification record (AC-11)")
        elif norm_text(it.get("ballot_text", {}).get("text", "")) != norm_text(certified[mid]):
            res.err(where, f"{mid}: ballot text does not match the certified text (AC-11)")
    for mid in certified:
        if mid not in measures:
            res.err(where, f"{mid}: in the verification record but not on the ballot")
    # Spot check by a second person.
    spot = record.get("spot_check") or {}
    need = math.ceil(SPOT_CHECK_SHARE * len(printed))
    if spot:
        if spot.get("by") == record.get("checked_by"):
            res.err(where, "spot check must be done by a second person")
        if (spot.get("items_checked") or 0) < need:
            res.err(where, f"spot check covered {spot.get('items_checked', 0)} items; needs at least {need}")


def checked_at(record: dict[str, Any] | None) -> str | None:
    return str(record["checked_at"]) if record and record.get("checked_at") else None


def fmt_runs(runs: list[list[Any]]) -> str:
    return ", ".join(f"{g} {n}" for g, n in runs) or "nothing"


# ---------- compile ----------

def compile_election(root: Path, election_id: str, data_version: str) -> Result:
    res = Result()
    src = root / "sources" / election_id
    ver = root / "verification"
    if not src.is_dir():
        res.err("sources", f"{src} not found")
        return res

    # Statewide
    sw_raw = load_yaml(src / "statewide.yaml") or {}
    sw_record = load_yaml(ver / "statewide.yaml") if (ver / "statewide.yaml").exists() else None
    sw_items = [normalize_item(i, checked_at(sw_record)) for i in sw_raw.get("items") or []]
    for n, it in enumerate(sw_items, start=1):
        it["ballot_order"] = n * STATEWIDE_STEP
    check_items("statewide", sw_items, res)
    check_verification("statewide", sw_items, sw_record, res)
    sw_by_id = {it["id"]: it for it in sw_items}
    res.statewide = {
        "schema_version": schemas.SCHEMA_VERSION, "data_version": data_version, "election_id": election_id,
        "districts": sw_raw.get("districts") or [], "items": sw_items,
    }

    # Geography: which statewide districts touch each county, and the ZIP index.
    geo_path = src / "geo.json"
    geo = json.loads(geo_path.read_text(encoding="utf-8")) if geo_path.exists() else None
    if geo is None:
        res.err("geo", f"{geo_path} not found; run python -m pipeline.zip_index first")
        geo = {"counties": {}, "zips": {}, "other_states": {}}
    states_path = root / "sources" / "states.yaml"
    states = load_yaml(states_path) if states_path.exists() else {}

    # Counties
    counties: dict[str, Any] = {}
    for fips, cgeo in sorted(geo.get("counties", {}).items()):
        county_src = src / f"{fips}.yaml"
        if county_src.exists():
            counties[fips] = compile_county(fips, load_yaml(county_src), sw_by_id, ver, res)
        else:
            counties[fips] = statewide_only_county(fips, cgeo, sw_items)
    for path in sorted(src.glob("08???.yaml")):
        if path.stem not in counties:
            res.err(path.stem, "county source has no entry in geo.json")
    res.counties = {
        "schema_version": schemas.SCHEMA_VERSION, "data_version": data_version, "election_id": election_id,
        "counties": counties,
    }
    res.zip_index = {
        "schema_version": schemas.SCHEMA_VERSION, "data_version": data_version, "election_id": election_id,
        "zips": geo.get("zips", {}), "other_states": geo.get("other_states", {}), "states": states or {},
    }

    for name, schema, doc in (("statewide.json", schemas.STATEWIDE, res.statewide),
                              ("counties.json", schemas.COUNTIES, res.counties),
                              ("zip-index.json", schemas.ZIP_INDEX, res.zip_index)):
        for e in jsonschema.Draft202012Validator(schema).iter_errors(doc):
            res.err(name, f"schema: {'/'.join(str(p) for p in e.path)}: {e.message}")
    return res


def statewide_only_county(fips: str, cgeo: dict[str, Any], sw_items: list[dict[str, Any]]) -> dict[str, Any]:
    touching = set(cgeo.get("districts", []))
    order = [it["id"] for it in sw_items if it["district_id"] is None or it["district_id"] in touching]
    return {
        "county_fips": fips, "name": cgeo["name"], "coverage": {"status": "statewide_only"},
        "districts": [], "items": [], "statewide_order": order,
    }


def compile_county(fips: str, raw: dict[str, Any], sw_by_id: dict[str, dict[str, Any]], ver: Path,
                   res: Result) -> dict[str, Any]:
    where = f"county {fips}"
    rec_path = ver / f"{fips}.yaml"
    record = load_yaml(rec_path) if rec_path.exists() else None
    if str(raw.get("county_fips")) != fips:
        res.err(where, "county_fips in the file does not match its file name")
    local: list[dict[str, Any]] = []
    printed: list[dict[str, Any]] = []
    statewide_order: list[str] = []
    last_sw, offset = 0, 0
    for entry in raw.get("ballot") or []:
        if "statewide" in entry:
            sid = entry["statewide"]
            if sid not in sw_by_id:
                res.err(where, f"refers to unknown statewide item {sid}")
                continue
            order = sw_by_id[sid]["ballot_order"]
            if order <= last_sw:
                res.err(where, f"statewide item {sid} is out of statewide order (AC-07)")
            last_sw, offset = order, 0
            statewide_order.append(sid)
            printed.append(sw_by_id[sid])
        else:
            it = normalize_item(entry, checked_at(record))
            offset += LOCAL_STEP
            if offset >= STATEWIDE_STEP:
                res.err(where, "too many local items between two statewide items")
            it["ballot_order"] = last_sw + offset
            local.append(it)
            printed.append(it)
    check_items(where, local, res)
    for it in local:
        if it["id"] in sw_by_id:
            res.err(where, f"local item id {it['id']} collides with a statewide item")

    check_verification(where, printed, record, res)
    coverage: dict[str, Any] = {"status": "statewide_only"}
    if record:
        coverage = {"status": "verified_complete", "source": record.get("sample_ballot", ""),
                    "verified_at": str(record.get("checked_at", "")), "verified_by": str(record.get("checked_by", ""))}
    return {
        "county_fips": fips, "name": raw.get("name", ""), "coverage": coverage,
        "districts": raw.get("districts") or [], "items": local, "statewide_order": statewide_order,
    }
