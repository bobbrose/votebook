import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { BallotData } from "../src/types";

const dir = join(__dirname, "fixtures", "data", "2026-11-03");
const read = (f: string) => JSON.parse(readFileSync(join(dir, f), "utf8"));

/** The fictional fixture ballot (tests/fixtures/make_fixture.py). */
export function fixture(): BallotData {
  return { zipIndex: read("zip-index.json"), statewide: read("statewide.json"), counties: read("counties.json") };
}
