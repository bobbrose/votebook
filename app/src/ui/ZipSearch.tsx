// ZIP lookup, shared by Home and the top of the Ballot (REQ-01, REQ-02).
import { useState } from "preact/hooks";
import { isValidZip, itemsForZip } from "../resolve";
import { useApp } from "../state";
import { go } from "./parts";

export function ZipSearch({ compact = false }: { compact?: boolean }) {
  const app = useApp();
  const [zip, setZip] = useState(compact ? app.user.scope.zip ?? "" : "");
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
    if (compact) window.scrollTo(0, 0);
    go("/ballot");
  };

  const id = compact ? "zip-search" : "zip";
  return (
    <>
      <form onSubmit={submit} class={`zip-form ${compact ? "compact" : ""}`} role="search" noValidate>
        <label for={id} class={compact ? "visually-hidden" : ""}>ZIP code</label>
        <div class="zip-row">
          <input id={id} type="search" inputMode="numeric" autoComplete="off" maxLength={5} value={zip}
                 placeholder={compact ? "ZIP code" : undefined}
                 aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined}
                 onInput={(e) => setZip((e.target as HTMLInputElement).value.replace(/\D/g, ""))} />
          <button type="submit" disabled={!app.data}>{app.data ? "Look up" : "Loading…"}</button>
        </div>
        {error && <p id={`${id}-error`} class="error" role="alert">{error}</p>}
      </form>
      {outside && (
        <section class="notice" role="status" aria-live="polite">
          <p>This site covers Colorado ballots only. {outside.name}'s official election information:</p>
          <p><a href={outside.site} target="_blank" rel="noopener noreferrer">{outside.name} voter information ↗</a></p>
        </section>
      )}
      {notFound && <p class="notice" role="status">We don't have that ZIP code. Check it, or try a nearby ZIP.</p>}
    </>
  );
}
