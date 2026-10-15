// Ballot resolution on the device (tech-spec C3). Pure functions: no network, no storage.
import type { BallotData, Choice, Contest, County, Item, Narrowing } from "./types";

export interface Row {
  item: Item;
  county: string;                  // FIPS of the county whose ballot carries this row
  districtType: string | null;     // congressional, state_senate, state_house, place, special, county
  conditional: string | null;      // name of what it depends on, or null if it is on every ballot here
}

export type Lookup =
  | { kind: "ballot"; zip: string; counties: County[]; rows: Row[] }
  | { kind: "other_state"; zip: string; state: string; name: string; site: string }
  | { kind: "unknown"; zip: string };

const STATEWIDE_TYPES: [string, string, string][] = [
  ["co-cd-", "congressional", "Congressional District "],
  ["co-senate-", "state_senate", "State Senate District "],
  ["co-house-", "state_house", "State House District "],
];

export function districtType(id: string): string {
  for (const [prefix, type] of STATEWIDE_TYPES) if (id.startsWith(prefix)) return type;
  return id.startsWith("city-") ? "place" : "special";
}

export function districtName(id: string, counties: County[]): string {
  for (const c of counties) {
    const d = c.districts.find((x) => x.id === id);
    if (d) return d.name;
  }
  for (const [prefix, , label] of STATEWIDE_TYPES) if (id.startsWith(prefix)) return label + id.slice(prefix.length);
  return id;
}

export function isValidZip(zip: string): boolean {
  return /^\d{5}$/.test(zip);
}

/** Every item that could be on a ballot in this ZIP (REQ-01), in printed order (REQ-05). */
export function itemsForZip(data: BallotData, zip: string): Lookup {
  const entry = data.zipIndex.zips[zip];
  if (!entry) {
    const code = data.zipIndex.other_states[zip.slice(0, 3)];
    const st = code ? data.zipIndex.states[code] : undefined;
    return st ? { kind: "other_state", zip, state: code, name: st.name, site: st.election_site } : { kind: "unknown", zip };
  }
  const counties = entry.counties.map((f) => data.counties.counties[f]).filter(Boolean);
  const touched = new Set(Object.values(entry.districts).flat());
  const perType = (type: string) => (entry.districts[type] ?? []).length;
  const statewide = new Map(data.statewide.items.map((it) => [it.id, it]));
  const multiCounty = counties.length > 1;
  const seen = new Set<string>();
  const rows: Row[] = [];

  for (const county of counties) {
    const local = county.coverage.status === "statewide_only" ? [] : county.items; // AC-27
    const items = [...county.statewide_order.map((id) => statewide.get(id)!).filter(Boolean), ...local];
    for (const item of items) {
      if (seen.has(item.id)) continue;
      const did = item.district_id;
      const isLocal = !statewide.has(item.id);
      let type: string | null = null;
      let conditional: string | null = null;
      if (did === null) {
        if (isLocal && multiCounty) { type = "county"; conditional = `${county.name} County`; }
      } else {
        type = districtType(did);
        if (type !== "special" && !touched.has(did)) continue; // a district this ZIP does not touch
        const certain = type !== "place" && type !== "special" && perType(type) === 1;
        conditional = certain ? null : districtName(did, counties);
      }
      seen.add(item.id);
      rows.push({ item, county: county.county_fips, districtType: type, conditional });
    }
  }
  rows.sort((a, b) => a.item.ballot_order - b.item.ballot_order);
  return { kind: "ballot", zip, counties, rows };
}

export function emptyNarrowing(): Narrowing {
  return { county: null, picks: {}, special: {} };
}

/** Guided narrowing (REQ-04, AC-06): drop rows that cannot apply; settled rows lose their tag. */
export function narrow(rows: Row[], n: Narrowing, counties: County[]): Row[] {
  const out: Row[] = [];
  for (const row of rows) {
    const did = row.item.district_id;
    if (n.county) {
      const picked = counties.find((c) => c.county_fips === n.county);
      const onPickedBallot = picked && (row.county === n.county || picked.statewide_order.includes(row.item.id));
      if (!onPickedBallot) continue;
    }
    if (row.districtType === "county") {
      out.push(n.county ? { ...row, conditional: null } : row);
      continue;
    }
    if (did && row.districtType && row.districtType !== "special") {
      const pick = n.picks[row.districtType];
      if (pick && pick !== did) continue;
      out.push(pick === did ? { ...row, conditional: null } : row);
      continue;
    }
    if (did && row.districtType === "special") {
      const inIt = n.special[did];
      if (inIt === false) continue;
      out.push(inIt === true ? { ...row, conditional: null } : row);
      continue;
    }
    out.push(row);
  }
  return out;
}

/** District choices offered by the narrowing sheet (design S3), built from the rows themselves. */
export function narrowingOptions(rows: Row[], counties: County[]) {
  const byType = new Map<string, Map<string, string>>();
  const special = new Map<string, string>();
  for (const r of rows) {
    const did = r.item.district_id;
    if (!did || !r.conditional || !r.districtType || r.districtType === "county") continue;
    if (r.districtType === "special") special.set(did, r.conditional);
    else {
      if (!byType.has(r.districtType)) byType.set(r.districtType, new Map());
      byType.get(r.districtType)!.set(did, r.conditional);
    }
  }
  return {
    counties: counties.length > 1 ? counties.map((c) => ({ id: c.county_fips, name: `${c.name} County` })) : [],
    types: [...byType.entries()].map(([type, m]) => ({ type, options: [...m.entries()].map(([id, name]) => ({ id, name })) })),
    special: [...special.entries()].map(([id, name]) => ({ id, name })),
  };
}

/** Ranked contests are shown with official instructions only in the pilot (PRD Release scope). */
export const RANKED_IN_PILOT = false;

export function countsTowardProgress(item: Item): boolean {
  return !(item.kind === "candidate_contest" && item.ranked && !RANKED_IN_PILOT);
}

/** REQ-12: Yes/No (or a printed label, or a pick) for measures and retentions; a candidate for contests. */
export function isDecided(_item: Item, choice: Choice | undefined): boolean {
  if (!choice) return false;
  if ("vote" in choice) return choice.vote !== "undecided";
  if ("pick" in choice) return choice.pick !== null;
  if ("selected" in choice) return choice.selected.length > 0 || !!choice.write_in?.trim();
  if ("ranking" in choice) return choice.ranking.length > 0;
  return false;
}

export function progress(rows: Row[], choices: Record<string, Choice>): { decided: number; total: number } {
  const counted = rows.filter((r) => countsTowardProgress(r.item));
  return { decided: counted.filter((r) => isDecided(r.item, choices[r.item.id])).length, total: counted.length };
}

/** AC-13: selecting beyond the vote limit is refused, not silently trimmed. */
export function toggleCandidate(contest: Contest, selected: string[], id: string, writeIn = ""): string[] | null {
  if (selected.includes(id)) return selected.filter((x) => x !== id);
  const used = selected.length + (writeIn.trim() ? 1 : 0);
  if (used >= (contest.vote_for ?? 1)) return null;
  return [...selected, id];
}

/** Two-choice labels for a measure or retention: the printed ones when present (REQ-09, AC-51). */
export function yesNoLabels(item: Item): [string, string] | null {
  if (item.kind === "retention") return ["Yes", "No"];
  if (item.kind !== "measure") return null;
  if (!item.choices) return ["Yes", "No"];
  return item.choices.length === 2 ? [item.choices[0], item.choices[1]] : null;
}
