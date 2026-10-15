// S2 Ballot and S3 Narrow my ballot.
import { useState } from "preact/hooks";
import { LINKS } from "../links";
import { countsTowardProgress, narrowingOptions, yesNoLabels } from "../resolve";
import { useApp } from "../state";
import type { Choice, Group, Item, Narrowing } from "../types";
import { CoverageLabel, ProgressBar, go } from "./parts";

export const GROUP_HEADINGS: Record<Group, string> = {
  federal: "Federal", state: "State", legislature: "Legislature", special_districts: "Special districts",
  county: "County", city: "City and town", judges: "Judges", measures: "Measures",
};

/** The current choice as text, never color alone (design: Accessibility). */
export function choiceSummary(item: Item, choice: Choice | undefined): string {
  if (item.kind === "candidate_contest") {
    if (item.ranked) return "Ranked choice: mark rankings on your paper ballot";
    if (!choice || !("selected" in choice)) return "Undecided";
    const names = choice.selected.map((id) => item.candidates.find((c) => c.id === id)?.name).filter(Boolean) as string[];
    if (choice.write_in?.trim()) names.push(`Write-in: ${choice.write_in.trim()}`);
    return names.length ? names.join(", ") : "Undecided";
  }
  if (item.kind === "measure" && item.choices && item.choices.length > 2) {
    return choice && "pick" in choice && choice.pick !== null ? item.choices[choice.pick] : "Undecided";
  }
  const labels = yesNoLabels(item)!;
  if (!choice || !("vote" in choice) || choice.vote === "undecided") return "Undecided";
  return choice.vote === "yes" ? labels[0] : labels[1];
}

export function Ballot() {
  const app = useApp();
  const [narrowing, setNarrowing] = useState(false);
  const lookup = app.lookup;
  if (!app.data) return <main><p>Loading the ballot…</p></main>;
  if (!lookup || lookup.kind !== "ballot") {
    return <main><p>No ballot yet. <a href="#/">Enter a ZIP code</a>.</p></main>;
  }
  const n = app.user.scope.narrowing;
  const narrowed = n.county !== null || Object.values(n.picks).some(Boolean) || Object.values(n.special).some((v) => v !== null);
  let group: Group | null = null;

  return (
    <>
      <ProgressBar back="#/" backLabel={lookup.zip} />
      <main class="ballot">
        <section class="research">
          <p><strong>{narrowed ? "Narrowed ballot." : "Research mode:"}</strong>{" "}
            {narrowed ? `Showing ${app.rows.length} of ${lookup.rows.length} items.` : "items for everywhere in this ZIP."}</p>
          <button onClick={() => setNarrowing(true)}>Narrow my ballot</button>
        </section>
        {lookup.counties.map((c) => <CoverageLabel key={c.county_fips} county={c} />)}

        <ol class="items">
          {app.rows.map(({ item, conditional }) => {
            const heading = item.group !== group ? (group = item.group, GROUP_HEADINGS[item.group]) : null;
            return (
              <li key={item.id}>
                {heading && <h2 class="group">{heading}</h2>}
                <a class="item-row" href={`#/item/${encodeURIComponent(item.id)}`}>
                  <span class="item-title">{item.title}</span>
                  {conditional && <span class="tag">Depends on your district: {conditional}</span>}
                  <span class={`item-choice ${countsTowardProgress(item) ? "" : "muted"}`}>
                    {choiceSummary(item, app.user.choices[item.id])}
                  </span>
                  <span class="chevron" aria-hidden="true">›</span>
                </a>
              </li>
            );
          })}
        </ol>

        <p><a class="button" href="#/write-out">Write out my ballot</a></p>
        <p class="small">Ballots must be received by 7 p.m. on Election Day.{" "}
          <a href={LINKS.whereToVote.url} target="_blank" rel="noopener noreferrer">{LINKS.whereToVote.label} ↗</a></p>
        <nav class="menu"><a href="#/data">Your data</a> · <a href="#/privacy">Privacy</a> · <a href="#/basics">Voting basics</a></nav>
      </main>
      {narrowing && <NarrowSheet onClose={() => setNarrowing(false)} />}
    </>
  );
}

const TYPE_LABELS: Record<string, string> = {
  congressional: "Congressional district", state_senate: "State Senate district",
  state_house: "State House district", place: "City or town",
};

function NarrowSheet({ onClose }: { onClose: () => void }) {
  const app = useApp();
  const lookup = app.lookup;
  if (!lookup || lookup.kind !== "ballot") return null;
  const n = app.user.scope.narrowing;
  const opts = narrowingOptions(lookup.rows, lookup.counties);
  const set = (next: Partial<Narrowing>) => app.setNarrowing({ ...n, ...next });

  return (
    <div class="sheet-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="narrow-title">
        <h2 id="narrow-title">Narrow my ballot</h2>
        <p class="muted">Pick what you know. Leave "Not sure" for the rest. Nothing you pick leaves this device.</p>

        {opts.counties.length > 0 && (
          <label>County
            <select value={n.county ?? ""} onChange={(e) => set({ county: (e.target as HTMLSelectElement).value || null })}>
              <option value="">Not sure</option>
              {opts.counties.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        )}

        {opts.types.map(({ type, options }) => (
          <label key={type}>{TYPE_LABELS[type] ?? type}
            <select value={n.picks[type] ?? ""}
                    onChange={(e) => set({ picks: { ...n.picks, [type]: (e.target as HTMLSelectElement).value || null } })}>
              <option value="">Not sure</option>
              {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              {type === "place" && <option value="none">Not in any of these</option>}
            </select>
          </label>
        ))}

        {opts.special.length > 0 && (
          <fieldset>
            <legend>Special districts</legend>
            {opts.special.map((d) => (
              <label key={d.id}>{d.name}
                <select value={n.special[d.id] === undefined || n.special[d.id] === null ? "" : String(n.special[d.id])}
                        onChange={(e) => {
                          const v = (e.target as HTMLSelectElement).value;
                          set({ special: { ...n.special, [d.id]: v === "" ? null : v === "true" } });
                        }}>
                  <option value="">Not sure</option>
                  <option value="true">I live in it</option>
                  <option value="false">I don't live in it</option>
                </select>
              </label>
            ))}
          </fieldset>
        )}

        <p aria-live="polite"><strong>Showing {app.rows.length} of {lookup.rows.length} items</strong></p>
        <div class="sheet-actions">
          <button class="secondary" onClick={() => app.setNarrowing({ county: null, picks: {}, special: {} })}>Reset</button>
          <button onClick={onClose}>Done</button>
        </div>
      </section>
    </div>
  );
}

export function goBallot() {
  go("/ballot");
}
