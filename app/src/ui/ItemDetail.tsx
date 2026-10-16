// S4 Item detail (measure, retention, choices variants) and S5 (candidate contest, ranked fallback).
import { useState } from "preact/hooks";
import { ordinal, setRank, skippedRanks, toggleCandidate, yesNoLabels } from "../resolve";
import { useApp } from "../state";
import type { BallotTable, Contest, Measure, Retention, Vote } from "../types";
import { ExternalLink, LinkList, NoteField, PickOne, ProgressBar, ProvenanceLine, SidesRow, TriState } from "./parts";

export function ItemDetail({ id }: { id: string }) {
  const app = useApp();
  const row = app.rows.find((r) => r.item.id === id) ?? (app.lookup?.kind === "ballot" ? app.lookup.rows.find((r) => r.item.id === id) : undefined);
  if (!row) return <main><p>That item isn't on this ballot. <a href="#/ballot">Back to the ballot</a></p></main>;
  const item = row.item;
  return (
    <>
      <ProgressBar back="#/ballot" backLabel="Ballot" />
      <main class="detail">
        <h1>{item.title}</h1>
        {row.conditional && <p class="tag">Depends on your district: {row.conditional}</p>}
        {item.kind === "measure" && <MeasureBody item={item} />}
        {item.kind === "retention" && <RetentionBody item={item} />}
        {item.kind === "candidate_contest" && <ContestBody item={item} />}
        <LinkList title="Explainers" links={item.links.explainers} />
        <NoteField id={item.id} />
        <ProvenanceLine p={item.provenance} />
      </main>
    </>
  );
}

/** The voter's choice for a measure or retention; shared with the expanded Ballot row. */
export function VoteControl({ item }: { item: Measure | Retention }) {
  const app = useApp();
  const choice = app.user.choices[item.id];
  if (item.kind === "measure" && item.choices && item.choices.length > 2) {
    const pick = choice && "pick" in choice ? choice.pick : null;
    return <PickOne name={item.id} options={item.choices} value={pick} onChange={(v) => app.setChoice(item.id, { pick: v })} />;
  }
  const vote: Vote = choice && "vote" in choice ? choice.vote : "undecided";
  return <TriState name={item.id} labels={yesNoLabels(item)!} value={vote} onChange={(v) => app.setChoice(item.id, { vote: v })} />;
}

function Table({ t }: { t: BallotTable }) {
  return (
    <div class="table-wrap">
      <table>
        <caption>{t.caption}</caption>
        <thead><tr>{t.header.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>{t.rows.map((r) => <tr key={r[0]}>{r.map((c, i) => (i === 0 ? <th key={i} scope="row">{c}</th> : <td key={i}>{c}</td>))}</tr>)}</tbody>
      </table>
      {t.note && <p class="small">{t.note}</p>}
    </div>
  );
}

function MeasureBody({ item }: { item: Measure }) {
  return (
    <>
      <h2 class="sub">Ballot text as certified</h2>
      <blockquote class="ballot-text">{item.ballot_text.text}</blockquote>
      {item.ballot_text.table && <Table t={item.ballot_text.table} />}
      <VoteControl item={item} />
      <LinkList title="Official sources" links={item.links.official} />
      <SidesRow links={item.links} />
    </>
  );
}

export function retentionQuestion(item: Retention): string {
  return `Shall ${item.court === "Colorado Supreme Court" ? "Justice" : "Judge"} ${item.judge} of the ${item.court} be retained in office?`;
}

function RetentionBody({ item }: { item: Retention }) {
  return (
    <>
      <p class="ballot-text">{retentionQuestion(item)}</p>
      <VoteControl item={item} />
      <LinkList title="Official sources" links={item.links.official} />
    </>
  );
}

function ContestBody({ item }: { item: Contest }) {
  if (item.ranked) {
    return (
      <>
        {item.rcv_instructions && (
          <section>
            <h2 class="sub">How ranked choice works here (official instructions)</h2>
            <blockquote class="ballot-text">{item.rcv_instructions.text}</blockquote>
            <p class="small"><ExternalLink link={{ label: "Source", url: item.rcv_instructions.source }} /></p>
          </section>
        )}
        <RankedChooser item={item} />
        <LinkList title="Official sources" links={item.links.official} />
      </>
    );
  }
  return (
    <>
      <CandidateChooser item={item} />
      <LinkList title="Official sources" links={item.links.official} />
      {item.candidates.some((c) => c.links.length) && (
        <section>
          <h3>Candidates' own sites</h3>
          <ul class="links">{item.candidates.flatMap((c) => c.links.map((l) => <li key={c.id + l.url}>{c.name}: <ExternalLink link={l} /></li>))}</ul>
        </section>
      )}
    </>
  );
}

/** Candidate checkboxes with the vote limit (REQ-10, AC-13); shared with the expanded Ballot row. */
export function CandidateChooser({ item }: { item: Contest }) {
  const app = useApp();
  const [message, setMessage] = useState("");
  const limit = item.vote_for ?? 1;
  const choice = app.user.choices[item.id];
  const selected = choice && "selected" in choice ? choice.selected : [];
  const writeIn = choice && "selected" in choice ? choice.write_in ?? "" : "";
  const limitText = `You can choose ${limit === 1 ? "one" : `up to ${limit}`}.`;

  const toggle = (id: string) => {
    const next = toggleCandidate(item, selected, id, writeIn);
    if (next === null) { setMessage(`${limitText} Unselect one first.`); return; }
    setMessage("");
    app.setChoice(item.id, { selected: next, write_in: writeIn });
  };

  return (
    <>
      <p><strong>Vote for {limit === 1 ? "one" : `up to ${limit}`}</strong></p>
      <fieldset class="candidates">
        <legend class="visually-hidden">Candidates for {item.title}</legend>
        {item.candidates.map((c) => (
          <label key={c.id} class="candidate">
            <span class="candidate-name">{c.name}<span class="party">{c.party ?? "No party"}{c.incumbent ? " · Incumbent" : ""}</span></span>
            <input type="checkbox" checked={selected.includes(c.id)} onChange={(e) => {
              (e.target as HTMLInputElement).checked = selected.includes(c.id);
              toggle(c.id);
            }} />
          </label>
        ))}
        {item.write_in && (
          <label class="candidate write-in">
            <span>Write-in</span>
            <input type="text" value={writeIn} placeholder="Name"
                   onInput={(e) => {
                     const v = (e.target as HTMLInputElement).value;
                     if (v.trim() && !writeIn.trim() && selected.length >= limit) { setMessage(`${limitText} Unselect one first.`); return; }
                     app.setChoice(item.id, { selected, write_in: v });
                   }} />
          </label>
        )}
      </fieldset>
      <p class="limit-message" aria-live="polite">{message}</p>
    </>
  );
}

/** Ranked contest: one rank dropdown per candidate; a rank held by another candidate can't be picked twice (REQ-10). */
export function RankedChooser({ item }: { item: Contest }) {
  const app = useApp();
  const choice = app.user.choices[item.id];
  const ranking = choice && "ranking" in choice ? choice.ranking : [];
  const max = item.max_ranks ?? item.candidates.length;
  const ranks = Array.from({ length: max }, (_, i) => i + 1);
  const skipped = skippedRanks(ranking);

  const change = (id: string, value: string) => {
    const next = setRank(ranking, id, value ? Number(value) : null);
    if (next) app.setChoice(item.id, { ranking: next });
  };

  return (
    <>
      <p><strong>Rank up to {max}{item.seats && item.seats > 1 ? `, ${item.seats} to be elected` : ""}. 1st is the one you want most.</strong></p>
      <div class="candidates">
        {item.candidates.map((c) => {
          const mine = ranking.indexOf(c.id) + 1;
          return (
            <label key={c.id} class={`candidate ranked ${mine ? "is-ranked" : ""}`}>
              <span class="candidate-name">{c.name}<span class="party">{c.party ?? "No party"}{c.incumbent ? " · Incumbent" : ""}</span></span>
              <select aria-label={`Rank for ${c.name}`} value={mine ? String(mine) : ""}
                      onChange={(e) => change(c.id, (e.target as HTMLSelectElement).value)}>
                <option value="">Not ranked</option>
                {ranks.map((r) => (
                  <option key={r} value={r} disabled={!!ranking[r - 1] && ranking[r - 1] !== c.id}>{ordinal(r)}</option>
                ))}
              </select>
            </label>
          );
        })}
      </div>
      <p class="limit-message" aria-live="polite">
        {skipped.length ? `You skipped ${skipped.map(ordinal).join(" and ")}. Check the official instructions for what a skipped rank means.` : ""}
      </p>
    </>
  );
}
