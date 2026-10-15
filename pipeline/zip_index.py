"""Build sources/<election>/geo.json: which counties and districts each Colorado ZIP touches.

    python -m pipeline.zip_index --election co-2026-11-03

Downloads Census cartographic boundary files into .cache/geo/ (not committed) and
writes geo.json, which is committed so builds do not need the network.

ZIP codes are approximated by Census ZCTAs (tech-spec C2). A ZCTA "touches" a county
or district when the overlap is at least MIN_SHARE_OF_ZIP of the ZCTA's area, or at
least MIN_SHARE_OF_DISTRICT of the district's area (so a small town inside a large
rural ZCTA still counts). The thresholds absorb slivers from generalized boundaries.
Erring toward inclusion only adds items labeled "Depends on your district".
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import shapefile
from shapely.geometry import shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "geo"
BASE = "https://www2.census.gov/geo/tiger/"
FILES = {
    "zcta": "GENZ2020/shp/cb_2020_us_zcta520_500k.zip",
    "state": "GENZ2024/shp/cb_2024_us_state_500k.zip",
    "county": "GENZ2024/shp/cb_2024_us_county_500k.zip",
    "congressional": "GENZ2024/shp/cb_2024_us_cd119_500k.zip",
    "state_senate": "GENZ2024/shp/cb_2024_08_sldu_500k.zip",
    "state_house": "GENZ2024/shp/cb_2024_08_sldl_500k.zip",
    "place": "GENZ2024/shp/cb_2024_08_place_500k.zip",
}
CO = "08"
MIN_SHARE_OF_ZIP = 0.005
MIN_SHARE_OF_DISTRICT = 0.2


def fetch(key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / Path(FILES[key]).name
    if not path.exists():
        print(f"Downloading {FILES[key]} ...", file=sys.stderr)
        with urllib.request.urlopen(BASE + FILES[key], timeout=300) as r:
            path.write_bytes(r.read())
    return path


def read(key: str) -> list[tuple[dict, object]]:
    """(attributes, shapely geometry) for every record in a zipped shapefile."""
    with zipfile.ZipFile(fetch(key)) as z:
        stem = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        sf = shapefile.Reader(shp=io.BytesIO(z.read(stem + ".shp")), dbf=io.BytesIO(z.read(stem + ".dbf")),
                              shx=io.BytesIO(z.read(stem + ".shx")))
        fields = [f[0] for f in sf.fields[1:]]
        out = []
        for rec in sf.iterShapeRecords():
            geom = shape(rec.shape.__geo_interface__)
            if not geom.is_valid:
                geom = geom.buffer(0)
            out.append((dict(zip(fields, rec.record)), geom))
        return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def district_id(kind: str, attrs: dict) -> tuple[str, str]:
    """Ids match the district_id values used in source YAML."""
    if kind == "congressional":
        n = int(attrs["CD119FP"])
        return f"co-cd-{n}", f"Congressional District {n}"
    if kind == "state_senate":
        n = int(attrs["SLDUST"])
        return f"co-senate-{n}", f"State Senate District {n}"
    if kind == "state_house":
        n = int(attrs["SLDLST"])
        return f"co-house-{n}", f"State House District {n}"
    if kind == "place":
        return f"city-{slug(attrs['NAME'])}", attrs["NAMELSAD"]
    raise ValueError(kind)


def touches(a, b) -> bool:
    if not a.intersects(b):
        return False
    overlap = a.intersection(b).area
    return overlap >= MIN_SHARE_OF_ZIP * a.area or overlap >= MIN_SHARE_OF_DISTRICT * b.area


def build_geo() -> dict:
    state_rows = read("state")
    colorado = next(g for a, g in state_rows if a["STATEFP"] == CO)
    counties = [(a, g) for a, g in read("county") if a["STATEFP"] == CO]
    layers = {
        "congressional": [(a, g) for a, g in read("congressional") if a["STATEFP"] == CO],
        "state_senate": read("state_senate"),
        "state_house": read("state_house"),
        "place": read("place"),
    }

    # Counties: which statewide districts touch each county.
    geo_counties = {}
    for attrs, cg in counties:
        touching = []
        for kind in ("congressional", "state_senate", "state_house"):
            for a, g in layers[kind]:
                if cg.intersects(g) and cg.intersection(g).area >= MIN_SHARE_OF_ZIP * min(cg.area, g.area):
                    touching.append(district_id(kind, a)[0])
        geo_counties[CO + attrs["COUNTYFP"]] = {"name": attrs["NAME"], "districts": sorted(touching)}

    # ZCTAs: Colorado ZIPs get counties and districts; the rest feed the ZIP-prefix-to-state table.
    states_by_fp = {a["STATEFP"]: a["STUSPS"] for a, _ in state_rows}
    state_geoms = [g for _, g in state_rows]
    state_fps = [a["STATEFP"] for a, _ in state_rows]
    state_tree = STRtree(state_geoms)
    zips: dict[str, dict] = {}
    prefix_votes: dict[str, Counter] = defaultdict(Counter)
    for attrs, zg in read("zcta"):
        z = attrs["ZCTA5CE20"]
        in_co = zg.intersects(colorado) and zg.intersection(colorado).area >= MIN_SHARE_OF_ZIP * zg.area
        if not in_co:
            pt = zg.representative_point()
            for i in state_tree.query(pt, predicate="within"):
                prefix_votes[z[:3]][states_by_fp[state_fps[int(i)]]] += 1
            continue
        entry = {"counties": sorted(CO + a["COUNTYFP"] for a, g in counties if touches(zg, g)),
                 "districts": {}}
        for kind, rows in layers.items():
            ids = sorted({district_id(kind, a)[0] for a, g in rows if touches(zg, g)})
            if ids:
                entry["districts"][kind] = ids
        if entry["counties"]:
            zips[z] = entry
    co_prefixes = {z[:3] for z in zips}
    other = {p: votes.most_common(1)[0][0] for p, votes in sorted(prefix_votes.items())
             if p not in co_prefixes and votes.most_common(1)[0][0] != "CO"}
    return {
        "generated_from": [BASE + FILES[k] for k in sorted(FILES)],
        "thresholds": {"min_share_of_zip": MIN_SHARE_OF_ZIP, "min_share_of_district": MIN_SHARE_OF_DISTRICT},
        "counties": dict(sorted(geo_counties.items())),
        "zips": dict(sorted(zips.items())),
        "other_states": other,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--election", required=True, help="election id, e.g. co-2026-11-03")
    args = ap.parse_args(argv)
    geo = build_geo()
    out = ROOT / "sources" / args.election / "geo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(geo, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}: {len(geo['counties'])} counties, {len(geo['zips'])} Colorado ZIPs, "
          f"{len(geo['other_states'])} other-state ZIP prefixes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
