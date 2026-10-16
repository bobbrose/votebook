"""JSON Schemas for the published data files (NFR-07).

The schemas are the contract between the pipeline and the app. They are written
to data/<election>/schema/ on every build so anyone can validate the files.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

GROUPS = ["federal", "state", "legislature", "judges", "county", "city", "special_districts", "measures"]

_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
_URL = {"type": "string", "pattern": r"^https://"}
_ID = {"type": "string", "pattern": r"^[a-z0-9][a-z0-9-]*$"}

DEFS = {
    "link": {
        "type": "object",
        "required": ["label", "url"],
        "additionalProperties": False,
        "properties": {"label": {"type": "string", "minLength": 1}, "url": _URL},
    },
    "provenance": {
        "type": "object",
        "required": ["source", "verified_at"],
        "additionalProperties": False,
        "properties": {"source": _URL, "verified_at": _DATE},
    },
    "links": {
        "type": "object",
        "required": ["official", "explainers", "support", "oppose"],
        "additionalProperties": False,
        "properties": {
            "official": {"type": "array", "items": {"$ref": "#/$defs/link"}},
            "explainers": {"type": "array", "items": {"$ref": "#/$defs/link"}},
            "support": {"oneOf": [{"type": "null"}, {"$ref": "#/$defs/link"}]},
            "oppose": {"oneOf": [{"type": "null"}, {"$ref": "#/$defs/link"}]},
        },
    },
    "candidate": {
        "type": "object",
        "required": ["id", "name", "party", "order", "links"],
        "additionalProperties": False,
        "properties": {
            "id": _ID,
            "name": {"type": "string", "minLength": 1},
            "party": {"type": ["string", "null"]},
            "order": {"type": "integer", "minimum": 1},
            "links": {"type": "array", "items": {"$ref": "#/$defs/link"}},
            "incumbent": {"type": "boolean"},
        },
    },
    "item": {
        "type": "object",
        "required": ["id", "kind", "group", "ballot_order", "district_id", "title", "links", "provenance"],
        "properties": {
            "id": _ID,
            "kind": {"enum": ["measure", "retention", "candidate_contest"]},
            "group": {"enum": GROUPS},
            "ballot_order": {"type": "integer", "minimum": 1},
            # null means the item is on every ballot in the file's area (statewide or countywide).
            "district_id": {"oneOf": [{"type": "null"}, _ID]},
            "title": {"type": "string", "minLength": 1},
            "links": {"$ref": "#/$defs/links"},
            "provenance": {"$ref": "#/$defs/provenance"},
            "ballot_text": {
                "type": "object",
                "required": ["text", "source"],
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "source": _URL,
                    # Tables that are part of the certified title, e.g. Colorado's required income tax table.
                    "table": {
                        "type": "object",
                        "required": ["caption", "header", "rows", "note"],
                        "additionalProperties": False,
                        "properties": {
                            "caption": {"type": "string"},
                            "header": {"type": "array", "items": {"type": "string"}},
                            "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                            "note": {"type": ["string", "null"]},
                        },
                    },
                },
            },
            # Measure choices when the ballot prints something other than Yes/For and No/Against.
            # Two labels map to the yes and no positions; more than two is a pick-one question.
            "choices": {"type": "array", "minItems": 2, "items": {"type": "string", "minLength": 1}},
            "judge": {"type": "string"},
            "court": {"type": "string"},
            "vote_for": {"type": "integer", "minimum": 1},
            "ranked": {"type": "boolean"},
            "max_ranks": {"type": "integer", "minimum": 1},
            "seats": {"type": "integer", "minimum": 1},
            "rcv_instructions": {
                "type": "object",
                "required": ["text", "source"],
                "additionalProperties": False,
                "properties": {"text": {"type": "string", "minLength": 1}, "source": _URL},
            },
            "candidates": {"type": "array", "items": {"$ref": "#/$defs/candidate"}},
            "write_in": {"type": "boolean"},
        },
        "additionalProperties": False,
        "allOf": [
            {"if": {"properties": {"kind": {"const": "measure"}}},
             "then": {"required": ["ballot_text"]}},
            {"if": {"properties": {"kind": {"const": "retention"}}},
             "then": {"required": ["judge", "court"]}},
            {"if": {"properties": {"kind": {"const": "candidate_contest"}}},
             "then": {"required": ["ranked", "candidates", "write_in"]}},
            {"if": {"properties": {"kind": {"const": "candidate_contest"}, "ranked": {"const": False}}},
             "then": {"required": ["vote_for"]}},
            {"if": {"properties": {"kind": {"const": "candidate_contest"}, "ranked": {"const": True}}},
             "then": {"required": ["max_ranks", "seats", "rcv_instructions"], "not": {"required": ["vote_for"]}}},
        ],
    },
    "district": {
        "type": "object",
        "required": ["id", "type", "name"],
        "additionalProperties": False,
        "properties": {"id": _ID, "type": {"type": "string"}, "name": {"type": "string"}},
    },
    "coverage": {
        "type": "object",
        "required": ["status"],
        "additionalProperties": False,
        "properties": {
            "status": {"enum": ["verified_complete", "statewide_only"]},
            "source": _URL,
            "verified_at": _DATE,
            "verified_by": {"type": "string"},
        },
        "if": {"properties": {"status": {"const": "verified_complete"}}},
        "then": {"required": ["source", "verified_at", "verified_by"]},
    },
    "county": {
        "type": "object",
        "required": ["county_fips", "name", "coverage", "districts", "items", "statewide_order"],
        "additionalProperties": False,
        "properties": {
            "county_fips": {"type": "string", "pattern": r"^08\d{3}$"},
            "name": {"type": "string"},
            "coverage": {"$ref": "#/$defs/coverage"},
            "districts": {"type": "array", "items": {"$ref": "#/$defs/district"}},
            "items": {"type": "array", "items": {"$ref": "#/$defs/item"}},
            # Statewide item ids that appear on this county's ballots, in printed order.
            "statewide_order": {"type": "array", "items": _ID},
        },
    },
}

_HEADER = {
    "schema_version": {"const": SCHEMA_VERSION},
    "data_version": {"type": "string", "pattern": r"^\d{4}\.\d{2}\.\d{2}-\d+$"},
    "election_id": {"type": "string", "pattern": r"^co-\d{4}-\d{2}-\d{2}$"},
}


def _file(props: dict, required: list[str]) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["schema_version", "data_version", "election_id", *required],
        "additionalProperties": False,
        "properties": {**_HEADER, **props},
        "$defs": DEFS,
    }


STATEWIDE = _file(
    {
        "districts": {"type": "array", "items": {"$ref": "#/$defs/district"}},
        "items": {"type": "array", "items": {"$ref": "#/$defs/item"}},
    },
    ["districts", "items"],
)

COUNTIES = _file(
    {"counties": {"type": "object", "patternProperties": {r"^08\d{3}$": {"$ref": "#/$defs/county"}},
                  "additionalProperties": False}},
    ["counties"],
)

ZIP_INDEX = _file(
    {
        "zips": {
            "type": "object",
            "patternProperties": {
                r"^\d{5}$": {
                    "type": "object",
                    "required": ["counties", "districts"],
                    "additionalProperties": False,
                    "properties": {
                        "counties": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "districts": {"type": "object", "additionalProperties": {
                            "type": "array", "items": {"type": "string"}}},
                    },
                }
            },
            "additionalProperties": False,
        },
        # First three ZIP digits -> state, for ZIPs outside Colorado (REQ-02).
        "other_states": {"type": "object", "patternProperties": {r"^\d{3}$": {"type": "string"}},
                         "additionalProperties": False},
        "states": {"type": "object", "additionalProperties": {
            "type": "object", "required": ["name", "election_site"], "additionalProperties": False,
            "properties": {"name": {"type": "string"}, "election_site": _URL}}},
    },
    ["zips", "other_states", "states"],
)

PUBLISHED = {
    "statewide.schema.json": STATEWIDE,
    "counties.schema.json": COUNTIES,
    "zip-index.schema.json": ZIP_INDEX,
}
