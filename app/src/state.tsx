// App state: ballot data, the voter's choices and notes, and where they are saved.
import { createContext, type ComponentChildren } from "preact";
import { useContext, useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ELECTION_ID, loadData } from "./data";
import { NARROWING_IN_PILOT, emptyNarrowing, itemsForZip, narrow, type Lookup, type Row } from "./resolve";
import { createStore, emptyUserData, type Store } from "./store";
import type { BallotData, Choice, Narrowing, UserData } from "./types";

interface AppState {
  data: BallotData | null;
  loadError: string | null;
  user: UserData;
  isPrivate: boolean;
  hasStarted: boolean;               // true once anything has been chosen, noted or looked up
  lookup: Lookup | null;
  rows: Row[];                       // after narrowing
  setZip(zip: string | null): void;
  setNarrowing(n: Narrowing): void;
  setChoice(id: string, c: Choice): void;
  setChoices(changes: Record<string, Choice>): void;
  setNote(id: string, text: string): void;
  startPrivate(): void;
  stopPrivate(): void;
  clearEverything(): Promise<void>;
  retryLoad(): void;
}

const Ctx = createContext<AppState | null>(null);

// Private session survives a reload of the same tab (otherwise a reload would silently start saving).
// Only this flag goes in sessionStorage, which the browser clears when the tab closes; no ballot data.
const PRIVATE_FLAG = "ballot-explorer-private";
function privateFlag(): boolean {
  try { return sessionStorage.getItem(PRIVATE_FLAG) === "1"; } catch { return false; }
}
function setPrivateFlag(on: boolean) {
  try { if (on) sessionStorage.setItem(PRIVATE_FLAG, "1"); else sessionStorage.removeItem(PRIVATE_FLAG); } catch { /* blocked */ }
}

export function useApp(): AppState {
  const s = useContext(Ctx);
  if (!s) throw new Error("useApp outside AppProvider");
  return s;
}

async function hasSavedData(): Promise<boolean> {
  try {
    if (!("indexedDB" in globalThis)) return false;
    if (typeof indexedDB.databases !== "function") return true;
    return (await indexedDB.databases()).some((d) => d.name === "ballot-explorer");
  } catch {
    return false;
  }
}

export function AppProvider({ children, initialData }: { children: ComponentChildren; initialData?: BallotData }) {
  const [data, setData] = useState<BallotData | null>(initialData ?? null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [user, setUser] = useState<UserData>(() => emptyUserData(ELECTION_ID));
  const [isPrivate, setPrivate] = useState(privateFlag);
  const store = useRef<Store | null>(null);

  const load = () => {
    setLoadError(null);
    loadData().then(setData, () =>
      setLoadError(navigator.onLine === false
        ? "You're offline. Connect once to load the ballot data."
        : "The ballot data didn't load. Try again."));
  };

  useEffect(() => {
    if (!initialData) load();
    // A returning voter: open saved data only if some exists, so a first visit stores nothing.
    if (privateFlag()) return;
    hasSavedData().then(async (yes) => {
      if (!yes) return;
      const s = createStore({ private: false });
      const saved = await s.load();
      if (saved && saved.election_id === ELECTION_ID) {
        store.current = s;
        setUser(saved);
      }
    });
  }, []);

  const update = (fn: (u: UserData) => UserData) => {
    setUser((prev) => {
      const next = fn(prev);
      store.current ??= createStore({ private: isPrivate });
      store.current.save(next);
      return next;
    });
  };

  const lookup = useMemo(() => (data && user.scope.zip ? itemsForZip(data, user.scope.zip) : null), [data, user.scope.zip]);
  const rows = useMemo(
    () => (lookup?.kind !== "ballot" ? []
      : NARROWING_IN_PILOT ? narrow(lookup.rows, user.scope.narrowing, lookup.counties) : lookup.rows),
    [lookup, user.scope.narrowing],
  );

  const hasStarted = Object.keys(user.choices).length > 0 || Object.values(user.notes).some((n) => n.trim());

  // AC-46: in private session, closing the tab erases work, so ask the browser to confirm.
  useEffect(() => {
    if (!isPrivate || !hasStarted) return;
    const onLeave = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    addEventListener("beforeunload", onLeave);
    return () => removeEventListener("beforeunload", onLeave);
  }, [isPrivate, hasStarted]);

  const value: AppState = {
    data, loadError, user, isPrivate, hasStarted, lookup, rows,
    setZip: (zip) => update((u) => ({ ...u, scope: { zip, narrowing: emptyNarrowing() } })),
    setNarrowing: (n) => update((u) => ({ ...u, scope: { ...u.scope, narrowing: n } })),
    setChoice: (id, c) => update((u) => ({ ...u, choices: { ...u.choices, [id]: c } })),
    setChoices: (changes) => update((u) => ({ ...u, choices: { ...u.choices, ...changes } })),
    setNote: (id, text) => update((u) => ({ ...u, notes: { ...u.notes, [id]: text } })),
    startPrivate: () => {
      // Anything already on this device is wiped; the current ballot moves to memory.
      const old = store.current;
      store.current = createStore({ private: true });
      store.current.save(user);
      setPrivate(true);
      setPrivateFlag(true);
      if (old && !old.isPrivate) void old.clearAll();
      else void createStore({ private: false }).clearAll();
    },
    stopPrivate: () => {
      store.current = createStore({ private: false });
      store.current.save(user);
      setPrivate(false);
      setPrivateFlag(false);
    },
    clearEverything: async () => {
      await (store.current ?? createStore({ private: false })).clearAll();
      await createStore({ private: false }).clearAll();
      store.current = null;
      setUser(emptyUserData(ELECTION_ID));
    },
    retryLoad: load,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
