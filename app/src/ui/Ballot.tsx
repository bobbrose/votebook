// S2 Ballot and S3 Narrow my ballot.
import { useEffect, useState } from "preact/hooks";
import { LINKS } from "../links";
import { clearCandidates, ordinal, countsTowardProgress, fillByParty, isDecided, partiesOnBallot, yesNoLabels } from "../resolve";
import { useApp } from "../state";
import type { Choice, Group, Item } from "../types";
import { CandidateChooser, RankedChooser, VoteControl, retentionQuestion } from "./ItemDetail";
import { CoverageLabel, NoteField, ProgressBar, go } from "./parts";

export const GROUP_HEADINGS: Record<Group, string> = {
  federal: "Federal", state: "State", legislature: "Legislature", special_districts: "Special districts",
  county: "County", city: "City and town", judges: "Judges", measures: "Measures",
};

/** The current choice as text, never color alone (design: Accessibility). */
export function choiceSummary(item: Item, choice: Choice | undefined): string {
  if (item.kind === "candidate_contest") {
    if (item.ranked) {
      const ranking = choice && "ranking" in choice ? choice.ranking : [];
      const named = ranking.flatMap((id, i) => (id ? [`${ordinal(i + 1)} ${item.candidates.find((c) => c.id === id)?.name}`] : []));
      return named.length ? named.join(", ") : "Undecided";
    }
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

// Which rows are open, and where to return after "Learn more". Memory only: never stored.
let expanded = new Set<string>();
let returnTo: string | null = null;
let filter = "";

/** Ballot search: every word must appear somewhere in the item's title, text, candidates, parties, choices or note. */
export function matches(item: Item, query: string, note = ""): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const parts: string[] = [item.title, note, GROUP_HEADINGS[item.group]];
  if (item.kind === "measure") parts.push(item.ballot_text.text, ...(item.choices ?? []));
  if (item.kind === "retention") parts.push(item.judge, item.court);
  if (item.kind === "candidate_contest") for (const c of item.candidates) parts.push(c.name, c.party ?? "", c.incumbent ? "incumbent" : "");
  const text = parts.join(" ").toLowerCase();
  return words.every((w) => text.includes(w));
}

/** One ballot item: a collapsed summary line that opens to decide in place (design S2). */
function BallotRow({ item, conditional, open, onToggle }: {
  item: Item; conditional: string | null; open: boolean; onToggle: () => void;
}) {
  const app = useApp();
  const choice = app.user.choices[item.id];
  const decided = countsTowardProgress(item) && isDecided(item, choice);
  const panel = `panel-${item.id}`;
  return (
    <div class={`ballot-item ${open ? "open" : ""}`}>
      <button type="button" class="item-row" aria-expanded={open} aria-controls={panel} onClick={onToggle}>
        <span class="item-title">{item.title}</span>
        {conditional && <span class="tag">Depends on your district: {conditional}</span>}
        <span class={`item-choice ${decided ? "decided" : ""} ${countsTowardProgress(item) ? "" : "muted"}`}>
          <RowChoice item={item} choice={choice} />
        </span>
        <span class="row-status" aria-hidden="true">
          {decided && <span class="check">✓</span>}
          <span class="chevron">›</span>
        </span>
      </button>
      {open && (
        <div class="item-panel" id={panel}>
          <ItemSummary item={item} />
          <p class="learn-more">
            <a href={`#/item/${encodeURIComponent(item.id)}`} onClick={() => { returnTo = item.id; }}>
              Learn more: {item.kind === "measure" ? "full ballot text, sources and campaigns"
                : item.kind === "candidate_contest" && item.ranked ? "how ranked choice works, sources and links" : "sources and links"} ›
            </a>
          </p>
          <NoteField id={item.id} />
        </div>
      )}
    </div>
  );
}

/** The collapsed row's choice; chosen candidates also show their party and incumbency. */
function RowChoice({ item, choice }: { item: Item; choice: Choice | undefined }) {
  if (item.kind !== "candidate_contest" || !isDecided(item, choice)) return <>{choiceSummary(item, choice)}</>;
  const picked = choice && "ranking" in choice
    ? choice.ranking.flatMap((id, i) => (id ? [{ id, rank: ordinal(i + 1) }] : []))
    : choice && "selected" in choice ? choice.selected.map((id) => ({ id, rank: "" })) : [];
  const writeIn = choice && "selected" in choice ? choice.write_in?.trim() : "";
  return (
    <span class="picks">
      {picked.map(({ id, rank }) => {
        const c = item.candidates.find((x) => x.id === id);
        if (!c) return null;
        const meta = [c.party ?? "No party", c.incumbent ? "Incumbent" : ""].filter(Boolean).join(" · ");
        return <span key={id} class="pick">{rank && `${rank} `}{c.name} <span class="pick-meta">{meta}</span></span>;
      })}
      {writeIn && <span class="pick">Write-in: {writeIn}</span>}
    </span>
  );
}

/** What the voter needs to decide in place: the official title or the candidates, and the vote control. */
function ItemSummary({ item }: { item: Item }) {
  if (item.kind === "measure") {
    return (
      <>
        <blockquote class="ballot-text"><span class="clamp">{item.ballot_text.text}</span></blockquote>
        <VoteControl item={item} />
      </>
    );
  }
  if (item.kind === "retention") {
    return (
      <>
        <p class="ballot-text">{retentionQuestion(item)}</p>
        <VoteControl item={item} />
      </>
    );
  }
  return item.ranked ? <RankedChooser item={item} /> : <CandidateChooser item={item} />;
}

/** Select all from one party, or clear all candidates. Every party on the ballot is offered, alphabetically (NFR-06). */
function PartyFillBar() {
  const app = useApp();
  const parties = partiesOnBallot(app.rows);
  const [party, setParty] = useState("");
  const [status, setStatus] = useState("");
  if (!parties.length) return null;
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

  const select = () => {
    if (!party) { setStatus("Choose a party first."); return; }
    const r = fillByParty(app.rows, app.user.choices, party);
    app.setChoices(r.choices);
    setStatus(`Selected ${party} candidates in ${plural(r.filled, "race", "races")}.`);
  };
  const clear = () => {
    const changes = clearCandidates(app.rows, app.user.choices);
    const n = Object.keys(changes).length;
    if (!n) return;
    if (!confirm(`Clear your candidates in ${plural(n, "race", "races")}? Measures, judges and notes are kept.`)) return;
    app.setChoices(changes);
    setStatus(`Cleared candidates in ${plural(n, "race", "races")}.`);
  };

  return (
    <div class="party-fill">
      <select aria-label="Party" value={party} onChange={(e) => { setParty((e.target as HTMLSelectElement).value); setStatus(""); }}>
        <option value="">Party</option>
        {parties.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <button type="button" class="small-button" onClick={select}>Select all</button>
      <button type="button" class="small-button secondary" onClick={clear}>Clear</button>
      <span class="visually-hidden" aria-live="polite">{status}</span>
    </div>
  );
}

export function Ballot() {
  const app = useApp();
  const [open, setOpen] = useState(expanded);
  const [query, setQuery] = useState(filter);
  const toggle = (id: string) => {
    const next = new Set(open);
    if (next.has(id)) next.delete(id); else next.add(id);
    expanded = next;
    setOpen(next);
  };
  // Coming back from "Learn more", return to the row the voter left from, not the top.
  useEffect(() => {
    if (!returnTo) return;
    document.getElementById(`row-${returnTo}`)?.scrollIntoView({ block: "start" });
    returnTo = null;
  }, []);
  const lookup = app.lookup;
  if (!app.data) return <main><p>Loading the ballot…</p></main>;
  if (!lookup || lookup.kind !== "ballot") {
    return <main><p>No ballot yet. <a href="#/">Enter a ZIP code</a>.</p></main>;
  }
  const shown = query.trim() ? app.rows.filter((r) => matches(r.item, query, app.user.notes[r.item.id])) : app.rows;
  let group: Group | null = null;

  return (
    <>
      <ProgressBar back="#/" backLabel={lookup.zip} />
      <main class="ballot">
        <section class="research">
          <p><strong>Researching ZIP {lookup.zip}.</strong> This shows every race and question that could be on a ballot
            anywhere in this ZIP. Your own ballot will have some of them, not all.</p>
        </section>
        {lookup.counties.map((c) => <CoverageLabel key={c.county_fips} county={c} />)}
        <PartyFillBar />
        <input type="search" class="ballot-filter" placeholder="Search the ballot" aria-label="Search the ballot"
               value={query} onInput={(e) => { filter = (e.target as HTMLInputElement).value; setQuery(filter); }} />
        {query.trim() && (
          <p class="small muted" aria-live="polite">
            {shown.length ? `Showing ${shown.length} of ${app.rows.length} items` : `Nothing on this ballot matches "${query.trim()}".`}
          </p>
        )}

        <ol class="items">
          {shown.map(({ item, conditional }) => {
            const heading = item.group !== group ? (group = item.group, GROUP_HEADINGS[item.group]) : null;
            return (
              <li key={item.id} id={`row-${item.id}`}>
                {heading && <h2 class="group">{heading}</h2>}
                <BallotRow item={item} conditional={conditional} open={open.has(item.id)} onToggle={() => toggle(item.id)} />
              </li>
            );
          })}
        </ol>

        <p><a class="button" href="#/write-out">Write out my ballot</a></p>
        <p class="small">Ballots must be received by 7 p.m. on Election Day.{" "}
          <a href={LINKS.whereToVote.url} target="_blank" rel="noopener noreferrer">{LINKS.whereToVote.label} ↗</a></p>
        <nav class="menu"><a href="#/data">Your data</a> · <a href="#/privacy">Privacy</a> · <a href="#/basics">Voting basics</a></nav>
      </main>
    </>
  );
}

export function goBallot() {
  go("/ballot");
}
