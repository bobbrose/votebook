// S1 Home and S9 Not in Colorado.
import { useState } from "preact/hooks";
import { LINKS, ELECTION_DAY } from "../links";
import { isValidZip, itemsForZip, progress } from "../resolve";
import { useApp } from "../state";
import { go } from "./parts";

export function Home() {
  const app = useApp();
  const [zip, setZip] = useState("");
  const [error, setError] = useState("");
  const [outside, setOutside] = useState<{ name: string; site: string } | null>(null);
  const [notFound, setNotFound] = useState(false);

  const submit = (e: Event) => {
    e.preventDefault();
    setOutside(null);
    setNotFound(false);
    const z = zip.trim();
    if (!isValidZip(z)) { setError("Enter a 5-digit ZIP code"); return; }
    setError("");
    if (!app.data) return;
    const result = itemsForZip(app.data, z);
    if (result.kind === "other_state") { setOutside({ name: result.name, site: result.site }); return; }
    if (result.kind === "unknown") { setNotFound(true); return; }
    app.setZip(z);
    go("/ballot");
  };

  const returning = app.user.scope.zip && app.data;
  const done = returning ? progress(app.rows, app.user.choices) : null;

  return (
    <main class="home">
      <h1>Colorado Ballot Explorer</h1>
      <p class="lead">See everything on your ballot. Nothing leaves this device.</p>

      {returning && done && (
        <p><a class="button secondary" href="#/ballot">Continue your ballot, {done.decided} of {done.total} decided</a></p>
      )}

      <form onSubmit={submit} class="zip-form" noValidate>
        <label for="zip">ZIP code</label>
        <div class="zip-row">
          <input id="zip" inputMode="numeric" autoComplete="off" maxLength={5} value={zip}
                 aria-invalid={!!error} aria-describedby={error ? "zip-error" : undefined}
                 onInput={(e) => setZip((e.target as HTMLInputElement).value.replace(/\D/g, ""))} />
          <button type="submit" disabled={!app.data}>{app.data ? "Look up" : "Loading…"}</button>
        </div>
        {error && <p id="zip-error" class="error" role="alert">{error}</p>}
      </form>

      {app.loadError && (
        <p class="error" role="alert">{app.loadError} <button class="link" onClick={app.retryLoad}>Try again</button></p>
      )}

      {outside && (
        <section class="notice" role="status" aria-live="polite">
          <p>This site covers Colorado ballots only. {outside.name}'s official election information:</p>
          <p><a href={outside.site} target="_blank" rel="noopener noreferrer">{outside.name} voter information ↗</a></p>
        </section>
      )}
      {notFound && (
        <p class="notice" role="status">We don't have that ZIP code. Check it, or try a nearby ZIP.</p>
      )}

      <ul class="home-links">
        {!app.isPrivate && (
          <li><button class="link" onClick={() => { app.startPrivate(); }}>Using a shared computer? Turn on private session ›</button></li>
        )}
        <li><a href="#/privacy">How this site handles your data ›</a></li>
        <li><a href="#/basics">Voting basics ›</a></li>
      </ul>
      {app.isPrivate && <p class="privacy-strip">Private session: nothing is kept on this computer.</p>}

      <footer class="election">
        <p><strong>{ELECTION_DAY} general election</strong></p>
        <p>Ballots must be <strong>received</strong> by 7 p.m. on Election Day. A postmark is not enough.</p>
        <p><a href={LINKS.whereToVote.url} target="_blank" rel="noopener noreferrer">{LINKS.whereToVote.label} ↗</a></p>
      </footer>
    </main>
  );
}
