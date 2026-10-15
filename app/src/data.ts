// Loads the three ballot data files. Every visitor fetches the same files from this site's
// own origin, and no request carries the ZIP (NFR-01, AC-40).
import type { BallotData, CountiesFile, StatewideFile, ZipIndexFile } from "./types";

export const ELECTION_DATE = "2026-11-03";
export const ELECTION_ID = `co-${ELECTION_DATE}`;
export const DATA_FILES = ["zip-index.json", "statewide.json", "counties.json"] as const;

async function get<T>(name: string): Promise<T> {
  const r = await fetch(`/data/${ELECTION_DATE}/${name}`, { credentials: "omit", cache: "default" });
  if (!r.ok) throw new Error(`Could not load ${name} (${r.status})`);
  return (await r.json()) as T;
}

let cached: Promise<BallotData> | null = null;

export function loadData(): Promise<BallotData> {
  cached ??= Promise.all([
    get<ZipIndexFile>("zip-index.json"),
    get<StatewideFile>("statewide.json"),
    get<CountiesFile>("counties.json"),
  ]).then(([zipIndex, statewide, counties]) => ({ zipIndex, statewide, counties }));
  cached.catch(() => { cached = null; });
  return cached;
}
