// S6 Write out my ballot (REQ-13, REQ-14).
import { useState } from "preact/hooks";
import { ELECTION_DAY, LINKS } from "../links";
import { countsTowardProgress, isDecided, type Row } from "../resolve";
import { useApp } from "../state";
import { GROUP_HEADINGS, choiceSummary } from "./Ballot";
import { ProgressBar } from "./parts";
import type { Choice, Group } from "../types";

/** One line per item in printed ballot order (AC-17, AC-18). */
export function writeOutLines(rows: Row[], choices: Record<string, Choice>, notes: Record<string, string>,
                              opts: { notes: boolean; undecided: boolean }): string[] {
  const lines: string[] = [];
  let group: Group | null = null;
  for (const { item } of rows) {
    const choice = choices[item.id];
    const decided = isDecided(item, choice);
    if (!decided && !opts.undecided) continue;
    if (!countsTowardProgress(item) && !opts.undecided) continue;
    if (item.group !== group) { group = item.group; lines.push("", GROUP_HEADINGS[group].toUpperCase()); }
    lines.push(`${item.title} ... ${choiceSummary(item, choice)}`);
    const note = notes[item.id]?.trim();
    if (opts.notes && note) lines.push(`    Note: ${note}`);
  }
  return lines.slice(lines[0] === "" ? 1 : 0);
}

export function WriteOut() {
  const app = useApp();
  const [notes, setNotes] = useState(true);
  const [undecided, setUndecided] = useState(false);
  const [status, setStatus] = useState("");
  const lines = writeOutLines(app.rows, app.user.choices, app.user.notes, { notes, undecided });
  const text = ["My ballot plan", `${ELECTION_DAY} general election`, "", ...lines, "",
    "This is your private plan, not a ballot or a record of how you voted."].join("\n");

  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setStatus("Copied."); } catch { setStatus("Copy didn't work. Select the text and copy it."); }
  };
  const save = () => {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "my-ballot-plan.txt" });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <>
      <div class="no-print"><ProgressBar back="#/ballot" backLabel="Ballot" title="My ballot plan" /></div>
      <main class="write-out">
        <h1 class="print-only">My ballot plan</h1>
        <div class="no-print toggles">
          <label><input type="checkbox" checked={notes} onChange={() => setNotes(!notes)} /> Include notes</label>
          <label><input type="checkbox" checked={undecided} onChange={() => setUndecided(!undecided)} /> Include undecided</label>
        </div>
        {lines.length ? <pre class="plan">{lines.join("\n")}</pre> : <p>Nothing decided yet. Decided items show up here in ballot order.</p>}
        <div class="no-print actions">
          <button onClick={copy}>Copy</button>
          <button onClick={() => print()}>Print</button>
          <button onClick={save}>Save</button>
        </div>
        <p class="no-print small">Anyone who opens a saved file can read it.</p>
        <p aria-live="polite" class="small">{status}</p>
        <p>This is your private plan, not a ballot or a record of how you voted.</p>
        <p>Ballots must be <strong>received</strong> by 7 p.m. on {ELECTION_DAY}.</p>
        <p class="no-print"><a href={LINKS.whereToVote.url} target="_blank" rel="noopener noreferrer">{LINKS.whereToVote.label} ↗</a></p>
      </main>
    </>
  );
}
