import "fake-indexeddb/auto";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { beforeEach, describe, expect, it } from "vitest";
import { AppProvider, useApp } from "../src/state";
import { App } from "../src/ui/App";
import { writeOutLines } from "../src/ui/WriteOut";
import { fixture } from "./data";

let api: ReturnType<typeof useApp>;
function Spy() { api = useApp(); return null; }

async function open(zip: string, route: string, data = fixture()) {
  location.hash = "#/";
  render(<AppProvider initialData={data}><Spy /><App /></AppProvider>);
  await act(() => api.setZip(zip));
  await act(() => { location.hash = route; window.dispatchEvent(new HashChangeEvent("hashchange")); });
}

beforeEach(() => { location.hash = "#/"; });

describe("measure detail (REQ-06 to REQ-09)", () => {
  it("shows certified text, official links first, and both campaign sides (AC-08 to AC-10)", async () => {
    await open("80001", "#/item/amendment-1");
    expect(screen.getByText("Shall there be an amendment to the example constitution?")).toBeTruthy();
    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings.indexOf("Official sources")).toBeLessThan(headings.indexOf("Campaigns"));
    expect(screen.getByText("Yes on 1 ↗")).toBeTruthy();
    expect(screen.getByText("No organized campaign found")).toBeTruthy();
  });

  it("starts Undecided and updates the count when a choice is made (AC-12, AC-16)", async () => {
    await open("80001", "#/item/amendment-1");
    expect((screen.getByLabelText("Undecided") as HTMLInputElement).checked).toBe(true);
    const count = () => document.querySelector(".progress-count")!.textContent;
    expect(count()).toBe("0 of 10 decided");
    await act(() => void fireEvent.click(screen.getByLabelText("Yes")));
    expect(count()).toBe("1 of 10 decided");
    expect(document.querySelector("[aria-live=polite].visually-hidden")!.textContent).toBe("1 of 10 decided");
  });

  it("uses printed labels and offers pick-one questions (AC-51, AC-52)", async () => {
    await open("80001", "#/item/alpha-2a");
    expect(screen.getByLabelText("For the Measure")).toBeTruthy();
    expect(screen.getByLabelText("Against the Measure")).toBeTruthy();
    await act(() => { location.hash = "#/item/alpha-200"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    const radios = screen.getAllByRole("radio").map((r) => r.parentElement!.textContent);
    expect(radios).toEqual(["Undecided", "By districts", "At large", "Half and half"]);
  });
});

describe("retention detail (REQ-06, D4)", () => {
  it("links the evaluation first and shows no finding (AC-41)", async () => {
    await open("80001", "#/item/retain-supreme-jordan-doe");
    const links = screen.getAllByRole("link").map((a) => a.textContent);
    expect(links.find((t) => t?.includes("Judicial performance evaluation"))).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/meets performance standard|does not meet/i);
  });
});

describe("candidate contests (REQ-10)", () => {
  it("keeps the selection and explains the limit (AC-13)", async () => {
    await open("80001", "#/item/alpha-council");
    for (const n of ["Finley Sample", "Gray Sample"]) await act(() => void fireEvent.click(screen.getByLabelText(new RegExp(n))));
    await act(() => void fireEvent.click(screen.getByLabelText(/Harper Sample/)));
    expect((screen.getByLabelText(/Harper Sample/) as HTMLInputElement).checked).toBe(false);
    expect(screen.getByText("You can choose up to 2. Unselect one first.")).toBeTruthy();
  });

  it("shows official instructions and a rank dropdown per candidate; a used rank is disabled elsewhere (AC-47)", async () => {
    await open("80001", "#/item/alpha-mayor");
    expect(screen.getByText("Rank candidates in order of preference.")).toBeTruthy();
    const indy = screen.getByLabelText("Rank for Indy Sample") as HTMLSelectElement;
    await act(() => void fireEvent.change(indy, { target: { value: "1" } }));
    const jules = screen.getByLabelText("Rank for Jules Sample") as HTMLSelectElement;
    expect((jules.querySelector('option[value="1"]') as HTMLOptionElement).disabled).toBe(true);
    expect((jules.querySelector('option[value="2"]') as HTMLOptionElement).disabled).toBe(false);
  });
});

describe("write-out (REQ-13)", () => {
  it("lists decided items in printed order, one line each, with toggles (AC-17, AC-18, AC-51)", async () => {
    await open("80001", "#/ballot");
    const choices = { "amendment-1": { vote: "no" as const }, "us-senate": { selected: ["cand-blake-sample"] },
                      "alpha-2a": { vote: "yes" as const } };
    const lines = writeOutLines(api.rows, choices, { "us-senate": "check debate" }, { notes: true, undecided: false });
    expect(lines).toEqual([
      "FEDERAL", "United States Senator ... Blake Sample", "    Note: check debate", "",
      "MEASURES", "Amendment 1 ... No", "City of Alpha Ballot Question 2A ... For the Measure",
    ]);
    expect(writeOutLines(api.rows, choices, {}, { notes: false, undecided: true }).filter((l) => l.includes("..."))).toHaveLength(10);
  });
});

describe("ballot and home", () => {
  it("shows the received-by reminder and official locator link (AC-20)", async () => {
    await open("80001", "#/ballot");
    expect(screen.getByText(/received by 7 p.m. on Election Day/)).toBeTruthy();
    expect(screen.getByText(/Where to return your ballot or vote in person/)).toBeTruthy();
  });

  it("shows Statewide items only for an unverified county (AC-27)", async () => {
    await open("80003", "#/ballot");
    expect(screen.getByText(/Statewide items only/)).toBeTruthy();
  });

  it("sends a non-Colorado ZIP to that state's site with no ballot (AC-03)", async () => {
    location.hash = "#/";
    render(<AppProvider initialData={fixture()}><App /></AppProvider>);
    fireEvent.input(screen.getByLabelText("ZIP code"), { target: { value: "84105" } });
    await act(() => void fireEvent.submit(screen.getByLabelText("ZIP code").closest("form")!));
    expect(screen.getByText(/covers Colorado ballots only/)).toBeTruthy();
    expect(screen.queryByText(/decided/)).toBeNull();
  });

  it("Clear everything returns to an empty ballot (AC-22)", async () => {
    await open("80001", "#/data");
    await act(() => api.setChoice("amendment-1", { vote: "yes" }));
    await act(() => void fireEvent.click(screen.getByText("Clear everything", { selector: "button" })));
    await act(() => void fireEvent.click(screen.getByText("Delete")));
    await waitFor(() => expect(api.user.choices).toEqual({}));
    expect(api.user.scope.zip).toBeNull();
  });
});

describe("data published before it is verified (AC-27)", () => {
  it("labels an unverified county and unverified statewide items, and says not verified on each item", async () => {
    const data = fixture();
    data.counties.counties["08001"].coverage = { status: "unverified", source: "https://example.org/alpha.pdf" };
    for (const it of data.statewide.items) it.provenance.verified_at = "0000-00-00";
    await open("80001", "#/ballot", data);
    expect(screen.getByText("Not yet checked against the official sample ballot.")).toBeTruthy();
    expect(screen.getByText("Statewide items are not yet checked against official sources.")).toBeTruthy();
    expect(screen.queryByText(/Verified complete/)).toBeNull();
    await act(() => { location.hash = "#/item/amendment-1"; window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(screen.getByText(/not verified yet/)).toBeTruthy();
  });
});
