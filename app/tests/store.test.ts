import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { createStore, emptyUserData } from "../src/store";

const withChoice = () => ({ ...emptyUserData("co-2026-11-03"), choices: { "amendment-1": { vote: "yes" as const } } });

describe("store (REQ-15 to REQ-17)", () => {
  it("restores choices after a reload (AC-21)", async () => {
    const s = createStore({ private: false });
    s.save(withChoice());
    await s.flush();
    const again = await createStore({ private: false }).load();
    expect(again?.choices["amendment-1"]).toEqual({ vote: "yes" });
  });

  it("autosaves within a second without a save button (AC-15)", async () => {
    const s = createStore({ private: false });
    s.save({ ...withChoice(), notes: { x: "a note" } });
    await new Promise((r) => setTimeout(r, 400));
    expect((await createStore({ private: false }).load())?.notes.x).toBe("a note");
  });

  it("Clear everything deletes stored data (AC-22)", async () => {
    const s = createStore({ private: false });
    s.save(withChoice());
    await s.flush();
    await s.clearAll();
    expect((await indexedDB.databases()).map((d) => d.name)).not.toContain("ballot-explorer");
    expect(await createStore({ private: false }).load()).toBeNull();
  });

  it("private session writes nothing to persistent storage (AC-23)", async () => {
    await createStore({ private: false }).clearAll();
    const s = createStore({ private: true });
    s.save(withChoice());
    await s.flush();
    expect(await s.load()).not.toBeNull();
    expect((await indexedDB.databases()).map((d) => d.name)).not.toContain("ballot-explorer");
  });
});
