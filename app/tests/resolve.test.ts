import { describe, expect, it } from "vitest";
import {
  clearCandidates, emptyNarrowing, ordinal, setRank, skippedRanks, fillByParty, isDecided, partiesOnBallot, itemsForZip, narrow, narrowingOptions, progress, toggleCandidate, yesNoLabels,
} from "../src/resolve";
import type { Contest, Measure } from "../src/types";
import { fixture } from "./data";

const data = fixture();
const ballot = (zip: string) => {
  const r = itemsForZip(data, zip);
  if (r.kind !== "ballot") throw new Error(r.kind);
  return r;
};
const ids = (rows: { item: { id: string } }[]) => rows.map((r) => r.item.id);
const item = (id: string) => ballot("80001").rows.find((r) => r.item.id === id)!.item;

describe("itemsForZip (REQ-01, REQ-05)", () => {
  it("shows every item for the ZIP in printed order (AC-01, AC-07)", () => {
    expect(ids(ballot("80001").rows)).toEqual([
      "us-senate", "state-house-1", "state-house-2", "alpha-council", "alpha-mayor", "retain-supreme-jordan-doe",
      "amendment-1", "alpha-2a", "alpha-200", "alpha-fire-7a",
    ]);
  });

  it("labels items that depend on location with their district (AC-02)", () => {
    const rows = ballot("80001").rows;
    const cond = Object.fromEntries(rows.map((r) => [r.item.id, r.conditional]));
    expect(cond["us-senate"]).toBeNull();
    expect(cond["state-house-1"]).toBe("State House District 1");
    expect(cond["alpha-council"]).toBe("City of Alpha");
    expect(cond["alpha-fire-7a"]).toBe("Alpha Fire District");
  });

  it("does not label a district item when the ZIP sits in only one district of that type", () => {
    const rows = ballot("80003").rows;
    expect(rows.find((r) => r.item.id === "state-house-2")!.conditional).toBeNull();
  });

  it("shows no local items for a statewide-only county (AC-27)", () => {
    expect(ids(ballot("80003").rows)).toEqual(["us-senate", "state-house-2", "retain-supreme-jordan-doe", "amendment-1"]);
  });

  it("marks a county's local items as conditional when the ZIP spans two counties", () => {
    const rows = ballot("80002").rows;
    expect(rows.find((r) => r.item.id === "alpha-200")!.conditional).toBe("Alpha County");
    expect(ids(rows)).not.toContain("state-house-1");
  });

  it("recognizes ZIPs outside Colorado (REQ-02, AC-03)", () => {
    expect(itemsForZip(data, "84101")).toMatchObject({ kind: "other_state", name: "Utah" });
    expect(itemsForZip(data, "99999")).toMatchObject({ kind: "unknown" });
  });
});

describe("narrow (REQ-04, AC-06)", () => {
  const { rows, counties } = ballot("80001");

  it("removes items for other districts and settles the picked one", () => {
    const out = narrow(rows, { ...emptyNarrowing(), picks: { state_house: "co-house-1" } }, counties);
    expect(ids(out)).not.toContain("state-house-2");
    expect(out.find((r) => r.item.id === "state-house-1")!.conditional).toBeNull();
  });

  it("removes city items when the voter is not in a city", () => {
    const out = narrow(rows, { ...emptyNarrowing(), picks: { place: "none" } }, counties);
    expect(ids(out)).not.toContain("alpha-council");
    expect(ids(out)).not.toContain("alpha-2a");
  });

  it("handles special districts as in, out or not sure", () => {
    expect(ids(narrow(rows, { ...emptyNarrowing(), special: { "alpha-fire-district": false } }, counties))).not.toContain("alpha-fire-7a");
    const inIt = narrow(rows, { ...emptyNarrowing(), special: { "alpha-fire-district": true } }, counties);
    expect(inIt.find((r) => r.item.id === "alpha-fire-7a")!.conditional).toBeNull();
  });

  it("picking a county keeps only that county's ballot", () => {
    const two = ballot("80002");
    const out = narrow(two.rows, { ...emptyNarrowing(), county: "08003" }, two.counties);
    expect(ids(out)).toEqual(["us-senate", "state-house-2", "retain-supreme-jordan-doe", "amendment-1"]);
  });

  it("offers pickers built from the ballot", () => {
    const o = narrowingOptions(rows, counties);
    expect(o.types.map((t) => t.type).sort()).toEqual(["place", "state_house"]);
    expect(o.special).toEqual([{ id: "alpha-fire-district", name: "Alpha Fire District" }]);
  });
});

describe("decisions and progress (REQ-09, REQ-10, REQ-12)", () => {
  it("counts only decided items, ranked contests included (AC-16)", () => {
    const rows = ballot("80001").rows;
    expect(progress(rows, {})).toEqual({ decided: 0, total: 10 });
    expect(progress(rows, { "amendment-1": { vote: "yes" }, "alpha-200": { pick: 1 }, "us-senate": { selected: [] },
                            "alpha-mayor": { ranking: ["", "cand-indy-sample"] } }))
      .toEqual({ decided: 3, total: 10 });
  });

  it("treats Undecided and empty selections as undecided", () => {
    const m = item("amendment-1");
    expect(isDecided(m, { vote: "undecided" })).toBe(false);
    expect(isDecided(m, { selected: [], write_in: "  " })).toBe(false);
    expect(isDecided(m, { selected: [], write_in: "Someone" })).toBe(true);
  });

  it("refuses a selection over the vote limit (AC-13)", () => {
    const c = item("alpha-council") as Contest;
    expect(toggleCandidate(c, ["cand-finley-sample", "cand-gray-sample"], "cand-harper-sample")).toBeNull();
    expect(toggleCandidate(c, ["cand-finley-sample"], "cand-harper-sample")).toEqual(["cand-finley-sample", "cand-harper-sample"]);
    expect(toggleCandidate(c, ["cand-finley-sample"], "cand-finley-sample")).toEqual([]);
    expect(toggleCandidate(c, ["cand-finley-sample"], "cand-gray-sample", "Write In")).toBeNull();
  });

  it("uses printed choice labels (AC-51)", () => {
    expect(yesNoLabels(item("amendment-1"))).toEqual(["Yes", "No"]);
    expect(yesNoLabels(item("alpha-2a"))).toEqual(["For the Measure", "Against the Measure"]);
    expect(yesNoLabels(item("alpha-200") as Measure)).toBeNull();
  });
});

describe("select all from a party, unselect all", () => {
  const rows = ballot("80001").rows;
  it("offers every party on the ballot, alphabetically (NFR-06)", () => {
    expect(partiesOnBallot(rows)).toEqual(["Party A", "Party B"]);
  });
  it("sets every race where the party has a candidate and counts the picks it replaces", () => {
    const r = fillByParty(rows, { "us-senate": { selected: ["cand-casey-sample"] } }, "Party A");
    expect(r.choices).toEqual({
      "us-senate": { selected: ["cand-avery-sample"], write_in: "" },
      "state-house-1": { selected: ["cand-drew-sample"], write_in: "" },
    });
    expect(r.filled).toBe(2);
    expect(r.replaced).toBe(1);
  });
  it("skips a race where the party has more candidates than the vote limit (AC-13)", () => {
    const senate = item("us-senate") as Contest;
    const crowded = { ...senate, candidates: senate.candidates.map((c) => ({ ...c, party: "Party A" })) };
    const r = fillByParty([{ item: crowded, county: "08001", districtType: null, conditional: null }], {}, "Party A");
    expect(r.tooMany).toBe(1);
    expect(r.choices).toEqual({});
  });
  it("unselect all clears candidates and keeps measures", () => {
    const changes = clearCandidates(rows, { "us-senate": { selected: ["cand-avery-sample"] }, "amendment-1": { vote: "yes" } });
    expect(changes).toEqual({ "us-senate": { selected: [], write_in: "" } });
  });
});

describe("ranked contests (REQ-10)", () => {
  it("never lets two candidates hold the same rank", () => {
    const r = setRank([], "a", 1)!;
    expect(r).toEqual(["a"]);
    expect(setRank(r, "b", 1)).toBeNull();
    expect(setRank(r, "b", 2)).toEqual(["a", "b"]);
  });
  it("moves a candidate to a new rank and clears the old one", () => {
    expect(setRank(["a", "b"], "a", 3)).toEqual(["", "b", "a"]);
    expect(setRank(["a", "b"], "b", null)).toEqual(["a"]);
  });
  it("reports skipped ranks", () => {
    expect(skippedRanks(["", "b", "", "c"])).toEqual([1, 3]);
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]);
  });
});
