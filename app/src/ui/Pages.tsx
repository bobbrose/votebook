// S7 Your data, S8 Privacy and Voting basics.
import { useState } from "preact/hooks";
import { ELECTION_DAY, LINKS } from "../links";
import { useApp } from "../state";
import { ExternalLink, go } from "./parts";

function PageHeader({ title }: { title: string }) {
  const { lookup } = useApp();
  return (
    <header class="page-header">
      <a class="back" href={lookup ? "#/ballot" : "#/"}>← {lookup ? "Ballot" : "Home"}</a>
      <h1>{title}</h1>
    </header>
  );
}

export function YourData() {
  const app = useApp();
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);
  const choices = Object.keys(app.user.choices).length;
  const notes = Object.values(app.user.notes).filter((n) => n.trim()).length;

  return (
    <>
      <PageHeader title="Your data" />
      <main>
        <p>{app.isPrivate ? "Kept for this session only:" : "Saved on this device:"}</p>
        <ul>
          <li>{choices} {choices === 1 ? "choice" : "choices"}</li>
          <li>{notes} {notes === 1 ? "note" : "notes"}</li>
          <li>ZIP code and narrowing: {app.user.scope.zip ?? "none"}</li>
        </ul>
        <p class="small">None of this is ever sent anywhere. Saving to a file and sending to another device come in a later version.</p>

        <section>
          <h2>Private session</h2>
          {app.isPrivate ? (
            <>
              <p>On. Nothing is kept on this computer, and closing the tab erases your choices.</p>
              <button class="secondary" onClick={app.stopPrivate}>Turn off and save on this device</button>
            </>
          ) : (
            <>
              <p>For a shared or public computer. Turning it on removes anything already saved here and keeps your ballot only until you close the tab.</p>
              <button class="secondary" onClick={app.startPrivate}>Turn on private session</button>
            </>
          )}
        </section>

        <section>
          <h2>Clear everything</h2>
          {done && <p role="status">Everything was cleared from this device.</p>}
          {!confirming ? (
            <button class="danger" onClick={() => { setDone(false); setConfirming(true); }}>Clear everything</button>
          ) : (
            <div class="confirm" role="alertdialog" aria-labelledby="confirm-title">
              <p id="confirm-title"><strong>Delete all of this from this device?</strong></p>
              <ul><li>Your {choices} choices</li><li>Your {notes} notes</li><li>Your ZIP code and narrowing</li></ul>
              <button class="danger" onClick={async () => { await app.clearEverything(); setConfirming(false); setDone(true); go("/"); }}>Delete</button>{" "}
              <button class="secondary" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          )}
        </section>
      </main>
    </>
  );
}

export function Privacy() {
  return (
    <>
      <PageHeader title="Privacy" />
      <main class="prose">
        <h2>What stays on your device</h2>
        <p>Your ZIP code, your choices and your notes are saved only in this browser on this device, so they are still here when you come back. They are never sent to us or anyone else. "Clear everything" in Your data deletes them.</p>
        <p>In a private session nothing is saved at all; closing the tab erases everything.</p>

        <h2>What this site downloads</h2>
        <p>Every visitor's browser downloads the same ballot files: every county's ballot and a ZIP code table for the whole state. Your browser picks out your ballot itself, so this site never learns which ZIP code, county or districts you looked up, or what you chose.</p>

        <h2>What the host can see</h2>
        <p>This site is hosted by Vercel. Like any web host, Vercel's servers see that a device at your internet address loaded the site. Vercel keeps request logs: which file was requested, when, the browser type, and the internet address. The project can view those logs for one day; how long Vercel itself keeps them is set by Vercel's own privacy policy. Because everyone downloads the same files, the logs cannot show which ZIP code you looked up or anything you chose. We use no analytics, no cookies, no ads and no third-party scripts or fonts.</p>

        <h2>Working offline</h2>
        <p>After your first visit, your browser keeps a copy of this site's own files and the ballot data so it works without a connection, for example in a vote center. That copy holds nothing you entered. It updates itself the next time you're online.</p>

        <h2>Links to other sites</h2>
        <p>Links to official and campaign sites open those sites, which have their own privacy practices. This site tells them nothing about you, not even which page you came from.</p>

        <h2>Write-out files</h2>
        <p>"Save" on the write-out page creates a plain text file. Anyone who opens that file can read it.</p>
      </main>
    </>
  );
}

export function Basics() {
  return (
    <>
      <PageHeader title="Voting basics" />
      <main class="prose">
        <p><strong>{ELECTION_DAY}</strong> is Election Day.</p>
        <p>Mail ballots must be <strong>received</strong> by 7 p.m. on Election Day. A postmark is not enough. Close to Election Day, use a drop box or vote center instead of the mail.</p>
        <ul class="links">
          <li><ExternalLink link={LINKS.whereToVote} /></li>
          <li><ExternalLink link={LINKS.ballotTrax} /></li>
          <li><ExternalLink link={LINKS.goVoteColorado} /></li>
          <li><ExternalLink link={LINKS.blueBook} /></li>
        </ul>
        <p class="small">This site shows what is on the ballot and keeps your own plan. Your plan is not a ballot.</p>
      </main>
    </>
  );
}
