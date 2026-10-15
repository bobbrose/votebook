// The voter's data, on this device only (tech-spec C5). Two backends behind one interface:
// IndexedDB (via this small wrapper, no dependency) and memory for private session mode.
import type { Narrowing, UserData } from "./types";
import { emptyNarrowing } from "./resolve";

const DB = "ballot-explorer";
const STORE = "kv";
const KEY = "user";
export const AUTOSAVE_MS = 300;

export function emptyUserData(electionId: string): UserData {
  return {
    format: "ballot-explorer-choices", version: 1, election_id: electionId,
    scope: { zip: null, narrowing: emptyNarrowing() as Narrowing },
    choices: {}, notes: {}, updated_at: new Date(0).toISOString(),
  };
}

interface Backend {
  get(): Promise<UserData | null>;
  put(data: UserData): Promise<void>;
  destroy(): Promise<void>;
}

function memoryBackend(): Backend {
  let held: UserData | null = null;
  return {
    async get() { return held; },
    async put(d) { held = d; },
    async destroy() { held = null; },
  };
}

function req<T>(r: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}

function idbBackend(): Backend {
  let db: Promise<IDBDatabase> | null = null;
  const open = () => (db ??= new Promise((resolve, reject) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE);
    r.onsuccess = () => {
      // Close when another connection deletes the database, so "Clear everything" is never blocked.
      r.result.onversionchange = () => { r.result.close(); db = null; };
      resolve(r.result);
    };
    r.onerror = () => reject(r.error);
  }));
  const tx = async (mode: IDBTransactionMode) => (await open()).transaction(STORE, mode).objectStore(STORE);
  return {
    async get() { return ((await req((await tx("readonly")).get(KEY))) as UserData | undefined) ?? null; },
    async put(d) { await req((await tx("readwrite")).put(d, KEY)); },
    async destroy() {
      if (db) (await db).close();
      db = null;
      await new Promise<void>((resolve) => {
        const r = indexedDB.deleteDatabase(DB);
        r.onsuccess = r.onerror = r.onblocked = () => resolve();
      });
    },
  };
}

export interface Store {
  readonly isPrivate: boolean;
  load(): Promise<UserData | null>;
  save(data: UserData): void;          // debounced autosave (AC-15: within 1 second)
  flush(): Promise<void>;
  clearAll(): Promise<void>;           // REQ-16, AC-22
}

/** Private session (REQ-17) must be chosen before anything is stored, so it is fixed per store. */
export function createStore(opts: { private: boolean }): Store {
  const backend = opts.private ? memoryBackend() : idbBackend();
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pending: UserData | null = null;
  let writing: Promise<void> = Promise.resolve();

  const write = () => {
    timer = null;
    if (!pending) return writing;
    const d = { ...pending, updated_at: new Date().toISOString() };
    pending = null;
    writing = writing.then(() => backend.put(d)).catch(() => undefined);
    return writing;
  };

  return {
    isPrivate: opts.private,
    async load() {
      try { return await backend.get(); } catch { return null; }
    },
    save(data) {
      pending = data;
      if (timer) clearTimeout(timer);
      timer = setTimeout(write, AUTOSAVE_MS);
    },
    async flush() {
      if (timer) clearTimeout(timer);
      await write();
    },
    async clearAll() {
      if (timer) clearTimeout(timer);
      timer = null;
      pending = null;
      await writing;
      await backend.destroy();
      try {
        for (const k of Object.keys(localStorage)) if (k.startsWith("ballot-explorer")) localStorage.removeItem(k);
      } catch { /* storage blocked: nothing to remove */ }
    },
  };
}
