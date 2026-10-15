# Data pipeline

Turns human-checked source files into the published ballot data in `data/`. See tech-spec C1 and C2.

## Setup

```
uv sync                      # Python 3.12 and dependencies into .venv
source .venv/bin/activate    # so the plan's commands work as written
```

## Commands

| Command | What it does |
|---|---|
| `python -m pytest pipeline` | Tests, including one failing fixture per data check |
| `python -m pipeline.zip_index --election co-2026-11-03` | Downloads Census boundaries to `.cache/geo/` and writes `sources/<election>/geo.json` |
| `python -I pipeline/import_sos.py CANDIDATES.xlsx DRAWING.xlsx MEASURES.html OUT.yaml` | Drafts `statewide.yaml` from the Secretary of State's files |
| `python -m pipeline.build --election co-2026-11-03` | Compiles and writes `data/2026-11-03/` |
| `python -m pipeline.build --election co-2026-11-03 --check` | Runs every check and fails if `data/` is not what the sources compile to |

## Files

```
sources/states.yaml                     election sites for ZIPs outside Colorado (REQ-02)
sources/<election>/geo.json             ZIP and county district intersections (generated, committed)
sources/<election>/statewide.yaml       statewide items in printed order
sources/<election>/<fips>.yaml          one county's full ballot in printed order
verification/statewide.yaml             human verification record for statewide items
verification/<fips>.yaml                human verification record for one county
data/<date>/                            build output, committed for transparency
```

### Statewide source

`items` in printed order. Each item has `id`, `kind` (`candidate_contest`, `retention`, `measure`), `group`, `title`, `district_id` (null when on every ballot), `links` and `provenance.source`. Candidate order is the list order. The compiler fills `ballot_order`, candidate `order` and `id`, and `provenance.verified_at` (from the verification record, never from the source).

### County source

```yaml
county_fips: "08013"
name: Boulder
districts: [{id: city-boulder, type: city, name: City of Boulder}]
ballot:                          # everything on any ballot in the county, in printed order
  - statewide: us-senate         # a statewide item that appears here
  - id: boulder-commissioner-1   # a local item, same fields as statewide items
    kind: candidate_contest
    ...
```

Statewide references must appear in statewide order. Local items get a `ballot_order` between the statewide items around them.

### Verification record

Filled in by people only. The build fails until it is complete.

```yaml
scope: "08013"                   # or statewide
sample_ballot: https://...       # county records
checked_by: Name
checked_at: 2026-10-15
groups:                          # group runs in printed order, with counts
  - {group: federal, count: 2}
measures:                        # certified ballot text, copied from a different official source
  boulder-city-2c: "Shall ..."
spot_check: {by: Second Person, at: 2026-10-15, items_checked: 3}   # at least 10 percent, different person
```

## Checks (each fails the build)

| Check | Requirement |
|---|---|
| Item and file schemas | NFR-07, AC-37 |
| Group order and counts match the verification record; statewide references in order | REQ-05, AC-07 |
| Measure text matches certified text | REQ-08, AC-11 |
| Retentions link to the judicial performance evaluation first | REQ-06, AC-41 |
| Ranked contests have instructions, ranking limit and seats | REQ-10, AC-50 |
| Every county with local items has a complete verification record and second-person spot check | REQ-20, AC-27 |
| Every published file has a matching hash | NFR-07, AC-37 |
| `counties.json` under 1.5 MB compressed | NFR-01, critique D2 |

## Known approximations

- ZIP codes are Census ZCTAs. A ZIP touches a district when the overlap is at least 0.5 percent of the ZIP or 20 percent of the district. This errs toward including districts, which only adds items labeled "Depends on your district".
- `sources/states.yaml` links to vote.gov state pages, generated from the Census state list. vote.gov blocks automated checks, so a person must click through them.
