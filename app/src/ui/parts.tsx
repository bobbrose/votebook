// Shared components from design.md "Components".
import { useEffect, useRef, useState } from "preact/hooks";
import { progress } from "../resolve";
import { useApp } from "../state";
import type { County, Link, Links, Provenance, Vote } from "../types";

export function go(path: string) {
  location.hash = path;
}

export function formatDate(iso?: string): string {
  if (!iso || iso.startsWith("0000")) return "";
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Sticky header with back link and the "X of Y decided" count and bar (REQ-12, AC-16, AC-42). */
export function ProgressBar({ back, backLabel, title }: { back: string; backLabel: string; title?: string }) {
  const { rows, user } = useApp();
  const { decided, total } = progress(rows, user.choices);
  const [announce, setAnnounce] = useState("");
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setAnnounce(`${decided} of ${total} decided`);
  }, [decided]);
  return (
    <header class="progress">
      <div class="progress-row">
        <a href={back} class="back">← {backLabel}</a>
        {title && <span class="progress-title">{title}</span>}
        <span class="progress-count">{decided} of {total} decided</span>
      </div>
      <progress max={Math.max(total, 1)} value={decided} aria-label={`Ballot progress: ${decided} of ${total} decided`} />
      <span class="visually-hidden" aria-live="polite">{announce}</span>
      <PrivacyStrip />
    </header>
  );
}

/** Shown only in private session mode, with the erase warning once there is work (REQ-17). */
export function PrivacyStrip() {
  const { isPrivate, hasStarted } = useApp();
  if (!isPrivate) return null;
  return (
    <div class="privacy-strip" role="status">
      <strong>Private session: nothing is kept on this computer.</strong>
      {hasStarted && <span> Closing this tab erases your choices. <a href="#/write-out">Write out your ballot</a> first.</span>}
    </div>
  );
}

export function CoverageLabel({ county }: { county: County }) {
  const c = county.coverage;
  if (c.status === "verified_complete") {
    return (
      <p class="coverage verified">
        {county.name} County · Verified complete · {formatDate(c.verified_at)} ·{" "}
        <a href={c.source} target="_blank" rel="noopener noreferrer">source</a>
      </p>
    );
  }
  if (c.status === "draft") {
    return <p class="coverage draft">{county.name} County · DRAFT: local items not verified yet (development data)</p>;
  }
  return (
    <p class="coverage partial">
      {county.name} County · Statewide items only. Local items for this county aren't verified yet. Check your
      county clerk's sample ballot for local races and questions.
    </p>
  );
}

export function ProvenanceLine({ p }: { p: Provenance }) {
  const date = formatDate(p.verified_at);
  return (
    <p class="provenance">
      Source: <a href={p.source} target="_blank" rel="noopener noreferrer">{sourceName(p.source)}</a>
      {date ? ` · verified ${date}` : " · not verified yet"}
    </p>
  );
}

function sourceName(url: string): string {
  if (url.includes("sample-ballot") || url.includes("Sample-Ballot") || url.includes("larimer.gov")) return "county sample ballot";
  if (url.includes("coloradosos.gov")) return "Colorado Secretary of State";
  if (url.includes("leg.colorado.gov")) return "Colorado Legislative Council";
  return new URL(url).hostname;
}

export function ExternalLink({ link }: { link: Link }) {
  return <a href={link.url} target="_blank" rel="noopener noreferrer">{link.label} ↗</a>;
}

export function LinkList({ title, links }: { title: string; links: Link[] }) {
  if (!links.length) return null;
  return (
    <section>
      <h3>{title}</h3>
      <ul class="links">{links.map((l) => <li key={l.url + l.label}><ExternalLink link={l} /></li>)}</ul>
    </section>
  );
}

/** Support and opposition always together, equal width (REQ-07, AC-09). */
export function SidesRow({ links }: { links: Links }) {
  if (!links.support && !links.oppose) return null;
  const side = (label: string, l: Link | null) => (
    <div class="side">
      <span class="side-label">{label}</span>
      {l ? <ExternalLink link={l} /> : <span class="muted">No organized campaign found</span>}
    </div>
  );
  return (
    <section>
      <h3>Campaigns</h3>
      <div class="sides">{side("For", links.support)}{side("Against", links.oppose)}</div>
    </section>
  );
}

/** Autosaving note (REQ-11, AC-15). */
export function NoteField({ id }: { id: string }) {
  const { user, setNote, isPrivate } = useApp();
  const [status, setStatus] = useState("");
  return (
    <section>
      <label for={`note-${id}`}><h3>My note</h3></label>
      <textarea
        id={`note-${id}`}
        rows={3}
        value={user.notes[id] ?? ""}
        onInput={(e) => { setNote(id, (e.target as HTMLTextAreaElement).value); setStatus(isPrivate ? "Kept for this session only" : "Saved on this device"); }}
      />
      <p class="muted small" aria-live="polite">{status}</p>
    </section>
  );
}

/** Yes / Undecided / No as a radio group styled as a segmented control (REQ-09). */
export function TriState({ name, labels, value, onChange }: {
  name: string; labels: [string, string]; value: Vote; onChange: (v: Vote) => void;
}) {
  const opts: [Vote, string][] = [["yes", labels[0]], ["undecided", "Undecided"], ["no", labels[1]]];
  // Long printed labels (a sentence each) read better stacked, with Undecided first.
  const stacked = labels.some((l) => l.length > 20);
  const shown: [Vote, string][] = stacked ? [opts[1], opts[0], opts[2]] : opts;
  return (
    <fieldset class={stacked ? "pick-one" : "segmented"}>
      <legend class={stacked ? "" : "visually-hidden"}>{stacked ? "Choose one" : "Your choice"}</legend>
      {shown.map(([v, label]) => (
        <label key={v} class={value === v ? "selected" : ""}>
          <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />
          <span>{label}</span>
        </label>
      ))}
    </fieldset>
  );
}

/** A question with more than two printed options (REQ-09, AC-52). */
export function PickOne({ name, options, value, onChange }: {
  name: string; options: string[]; value: number | null; onChange: (v: number | null) => void;
}) {
  return (
    <fieldset class="pick-one">
      <legend>Choose one</legend>
      <label class={value === null ? "selected" : ""}>
        <input type="radio" name={name} checked={value === null} onChange={() => onChange(null)} />
        <span>Undecided</span>
      </label>
      {options.map((o, i) => (
        <label key={i} class={value === i ? "selected" : ""}>
          <input type="radio" name={name} checked={value === i} onChange={() => onChange(i)} />
          <span>{o}</span>
        </label>
      ))}
    </fieldset>
  );
}
