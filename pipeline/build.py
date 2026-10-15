"""Build or check the published data for one election.

    python -m pipeline.build --election co-2026-11-03           # compile and write data/2026-11-03/
    python -m pipeline.build --election co-2026-11-03 --check   # compile, run every check, and fail
                                                                # if data/ is not what sources compile to

Writes zip-index.json, statewide.json, counties.json, manifest.json, hashes.txt,
CHANGELOG.md and schema/*.json. Exit code 0 = success, 1 = any check failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import schemas
from .compile import Result, compile_election

ROOT = Path(__file__).resolve().parent.parent
# Compressed size budget for counties.json (tech-spec, critique D2).
COUNTIES_BUDGET_BYTES = 1_500_000
DATA_FILES = ["zip-index.json", "statewide.json", "counties.json"]
PLACEHOLDER_VERSION = "0000.00.00-0"


def dumps(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def gz_size(text: str) -> int:
    # mtime=0 keeps the measurement deterministic.
    return len(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))


def out_dir(root: Path, election_id: str) -> Path:
    return root / "data" / election_id.removeprefix("co-")


def strip_version(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "data_version"}


def load_existing(out: Path) -> dict[str, Any]:
    docs = {}
    for name in DATA_FILES:
        p = out / name
        if p.exists():
            docs[name] = json.loads(p.read_text(encoding="utf-8"))
    return docs


def next_version(existing: dict[str, Any], today: dt.date) -> str:
    prefix = today.strftime("%Y.%m.%d")
    old = next(iter(existing.values()), {}).get("data_version", "")
    if old.startswith(prefix + "-"):
        return f"{prefix}-{int(old.rsplit('-', 1)[1]) + 1}"
    return f"{prefix}-1"


def items_by_id(statewide: dict[str, Any], counties: dict[str, Any]) -> dict[str, Any]:
    out = {it["id"]: it for it in statewide.get("items", [])}
    for c in counties.get("counties", {}).values():
        for it in c.get("items", []):
            out[it["id"]] = it
    return out


def changelog_entries(old: dict[str, Any], new: Result, today: dt.date) -> list[str]:
    """One line per added, removed or changed item since the last build (AC-30)."""
    if "statewide.json" not in old:
        return []
    before = items_by_id(old.get("statewide.json", {}), old.get("counties.json", {}))
    after = items_by_id(new.statewide or {}, new.counties or {})
    lines = []
    for iid in sorted(set(before) | set(after)):
        if iid not in before:
            lines.append(f"- {today}: {iid} ({after[iid]['title']}): added")
        elif iid not in after:
            lines.append(f"- {today}: {iid} ({before[iid]['title']}): removed")
        elif before[iid] != after[iid]:
            fields = sorted(k for k in set(before[iid]) | set(after[iid]) if before[iid].get(k) != after[iid].get(k))
            lines.append(f"- {today}: {iid} ({after[iid]['title']}): changed {', '.join(fields)}")
    old_cov = {f: c["coverage"]["status"] for f, c in old.get("counties.json", {}).get("counties", {}).items()}
    for fips, c in sorted((new.counties or {}).get("counties", {}).items()):
        if old_cov.get(fips) != c["coverage"]["status"]:
            lines.append(f"- {today}: {c['name']} County coverage: {old_cov.get(fips, 'none')} to {c['coverage']['status']}")
    return lines


def render(res: Result, version: str) -> dict[str, str]:
    files = {
        "zip-index.json": dumps(res.zip_index),
        "statewide.json": dumps(res.statewide),
        "counties.json": dumps(res.counties),
    }
    files["manifest.json"] = dumps({"schema_version": schemas.SCHEMA_VERSION, "data_version": version,
                                    "files": DATA_FILES})
    for name, schema in schemas.PUBLISHED.items():
        files[f"schema/{name}"] = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    files["hashes.txt"] = "".join(f"{sha256(files[n])}  {n}\n" for n in sorted(files))
    return files


def check_hashes(files: dict[str, str], errors: list[str]) -> None:
    """Every published file must have a matching hash (AC-37)."""
    listed = {}
    for line in files.get("hashes.txt", "").splitlines():
        h, _, name = line.partition("  ")
        listed[name] = h
    for name, text in files.items():
        if name == "hashes.txt" or name == "CHANGELOG.md":
            continue
        if listed.get(name) != sha256(text):
            errors.append(f"hashes.txt: missing or wrong hash for {name} (AC-37)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--election", required=True, help="election id, e.g. co-2026-11-03")
    ap.add_argument("--check", action="store_true", help="check only; fail if data/ is out of date")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    today = args.today or dt.date.today()

    out = out_dir(args.root, args.election)
    existing = load_existing(out)
    res = compile_election(args.root, args.election, PLACEHOLDER_VERSION)
    if res.errors:
        report(res.errors)
        return 1
    errors: list[str] = []

    # Keep the existing data_version when only the version would change; otherwise bump it.
    new_docs = {"zip-index.json": res.zip_index, "statewide.json": res.statewide, "counties.json": res.counties}
    unchanged = len(existing) == len(DATA_FILES) and all(
        strip_version(existing[n]) == strip_version(d) for n, d in new_docs.items())
    version = existing["statewide.json"]["data_version"] if unchanged else next_version(existing, today)
    for d in new_docs.values():
        d["data_version"] = version

    final_version = res.statewide["data_version"]
    files = render(res, final_version)
    size = gz_size(files["counties.json"])
    if size > COUNTIES_BUDGET_BYTES:
        errors.append(f"counties.json is {size:,} bytes compressed; budget is {COUNTIES_BUDGET_BYTES:,} (critique D2)")
    check_hashes(files, errors)

    if args.check:
        on_disk = {}
        for name in files:
            p = out / name
            on_disk[name] = p.read_text(encoding="utf-8") if p.exists() else None
        stale = [n for n, text in files.items() if on_disk[n] != text]
        if stale:
            errors.append(f"data/ is out of date ({', '.join(stale)}); run without --check to rebuild")
    if errors:
        report(errors)
        return 1

    counties = res.counties["counties"]
    verified = sorted(c["name"] for c in counties.values() if c["coverage"]["status"] == "verified_complete")
    summary = (f"{args.election} data {final_version}: {len(res.statewide['items'])} statewide items, "
               f"{len(counties)} counties ({len(verified)} verified: {', '.join(verified) or 'none'}), "
               f"{len(res.zip_index['zips'])} ZIPs, counties.json {size:,} bytes compressed")
    if args.check:
        print(f"OK  {summary}")
        return 0

    entries = changelog_entries(existing, res, today) if not unchanged else []
    log_path = out / "CHANGELOG.md"
    log = log_path.read_text(encoding="utf-8") if log_path.exists() else (
        f"# Data changelog: {args.election}\n\nCorrections and changes to published ballot data, newest first.\n")
    if entries:
        # Newest first: new entries go between the header and the older entries.
        head, sep, older = log.partition("\n- ")
        log = head.rstrip("\n") + "\n\n" + "\n".join(entries) + "\n" + (sep.lstrip("\n") + older if sep else "")
    files["CHANGELOG.md"] = log
    for name, text in files.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"Wrote {out}: {summary}" + (f"; {len(entries)} changelog entries" if entries else ""))
    return 0


def report(errors: list[str]) -> None:
    for e in errors:
        print(f"FAIL  {e}")
    print(f"\nBUILD FAILED: {len(errors)} problem(s)")


if __name__ == "__main__":
    sys.exit(main())
