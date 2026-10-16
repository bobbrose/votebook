// S1 Home and S9 Not in Colorado.
import { LINKS, ELECTION_DAY } from "../links";
import { progress } from "../resolve";
import { useApp } from "../state";
import { ZipSearch } from "./ZipSearch";

export function Home() {
  const app = useApp();
  const returning = app.user.scope.zip && app.data;
  const done = returning ? progress(app.rows, app.user.choices) : null;

  return (
    <main class="home">
      <h1>Colorado Ballot Explorer</h1>
      <p class="lead">See everything on your ballot. Nothing leaves this device.</p>

      {returning && done && (
        <p><a class="button secondary" href="#/ballot">Continue your ballot, {done.decided} of {done.total} decided</a></p>
      )}

      <ZipSearch />

      {app.loadError && (
        <p class="error" role="alert">{app.loadError} <button class="link" onClick={app.retryLoad}>Try again</button></p>
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
