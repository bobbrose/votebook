// Shapes of the published data files (pipeline/schemas.py) and of the voter's own data.

export type Group =
  | "federal" | "state" | "legislature" | "judges" | "county" | "city" | "special_districts" | "measures";

export interface Link { label: string; url: string }

export interface Links {
  official: Link[];
  explainers: Link[];
  support: Link | null;
  oppose: Link | null;
}

export interface Provenance { source: string; verified_at: string }

export interface Candidate { id: string; name: string; party: string | null; order: number; links: Link[]; incumbent?: boolean }

export interface BallotTable { caption: string; header: string[]; rows: string[][]; note: string | null }

interface ItemBase {
  id: string;
  group: Group;
  ballot_order: number;
  district_id: string | null;
  title: string;
  links: Links;
  provenance: Provenance;
}

export interface Measure extends ItemBase {
  kind: "measure";
  ballot_text: { text: string; source: string; table?: BallotTable };
  choices?: string[];
}

export interface Retention extends ItemBase { kind: "retention"; judge: string; court: string }

export interface Contest extends ItemBase {
  kind: "candidate_contest";
  candidates: Candidate[];
  write_in: boolean;
  ranked: boolean;
  vote_for?: number;
  max_ranks?: number;
  seats?: number;
  rcv_instructions?: { text: string; source: string };
}

export type Item = Measure | Retention | Contest;

export interface District { id: string; type: string; name: string }

export type CoverageStatus = "verified_complete" | "statewide_only" | "draft";

export interface County {
  county_fips: string;
  name: string;
  coverage: { status: CoverageStatus; source?: string; verified_at?: string; verified_by?: string };
  statewide_order: string[];
  districts: District[];
  items: Item[];
}

interface Header { schema_version: number; data_version: string; election_id: string }

export interface StatewideFile extends Header { districts: District[]; items: Item[] }
export interface CountiesFile extends Header { counties: Record<string, County> }
export interface ZipIndexFile extends Header {
  zips: Record<string, { counties: string[]; districts: Record<string, string[]> }>;
  other_states: Record<string, string>;
  states: Record<string, { name: string; election_site: string }>;
}

export interface BallotData { statewide: StatewideFile; counties: CountiesFile; zipIndex: ZipIndexFile }

// ---------- the voter's data (device only) ----------

export type Vote = "yes" | "no" | "undecided";

export type Choice =
  | { vote: Vote }                                   // measures and retentions with two choices
  | { pick: number | null }                          // measures with more than two choices
  | { selected: string[]; write_in?: string }        // vote-for contests
  | { ranking: string[] };                           // ranked contests (Release 1)

export interface Narrowing {
  county: string | null;                             // county FIPS, or null for "Not sure"
  picks: Record<string, string | null>;              // district type -> district id, "none", or null for "Not sure"
  special: Record<string, boolean | null>;           // special district id -> in it, not in it, or not sure
}

export interface UserData {
  format: "ballot-explorer-choices";
  version: 1;
  election_id: string;
  scope: { zip: string | null; narrowing: Narrowing };
  choices: Record<string, Choice>;
  notes: Record<string, string>;
  updated_at: string;
}
