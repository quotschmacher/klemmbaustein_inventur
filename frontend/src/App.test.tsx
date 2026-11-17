import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

test("zeigt die Startseite der LEGO-Inventur", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "LEGO Inventur" })).toBeInTheDocument();
  expect(screen.getByLabelText("Set-Nummer auf dem Karton")).toBeInTheDocument();
  expect(screen.getByLabelText("Set-Nummer auf dem Karton")).toHaveValue("75978");
  expect(screen.getByLabelText("Bereiche (optional, durch Komma getrennt)")).toBeInTheDocument();
  expect(screen.getByLabelText("CSV-Inventar")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Inventar importieren" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Von Rebrickable importieren" })).toBeInTheDocument();
  expect(screen.getByLabelText("Rebrickable-Anleitungssnapshots")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Anleitungssnapshots zuordnen" })).toBeInTheDocument();
  expect(screen.queryByText("Bereich auswählen")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Synthetische Test-CSV herunterladen" })).toHaveAttribute(
    "href",
    "/synthetic_inventory.csv",
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("zeigt nach dem Import die Gesamtübersicht", async () => {
  const responses = [
    { data: [] },
    { data: { id: "project-1" } },
    { data: { requirements: 1 } },
    { data: [{ id: "session-1", label: "Unsortiert", status: "in_progress", counted_positions: 0 }] },
    { data: { total: 0, items: [] } },
    { data: { required_sessions_total: 1, required_sessions_completed: 0, surplus_types: 0, provisional_gap_units: 2, confirmed_missing_units: 0 } },
    { data: { items: [] } },
    { data: { final: false, items: [] } },
    { data: [] },
    { data: [{ id: "project-1", label: "Winkelgasse", set_num: "75978", status: "in_progress" }] },
  ];
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(responses.shift()) })));
  render(<App />);

  fireEvent.change(screen.getByLabelText("CSV-Inventar"), { target: { files: [new File(["x"], "inventory.csv", { type: "text/csv" })] } });
  fireEvent.click(screen.getByRole("button", { name: "Inventar importieren" }));

  expect(await screen.findByRole("heading", { name: "Gesamtübersicht" })).toBeInTheDocument();
  expect(screen.getByText("Noch offene Zählbereiche")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Zählen" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Neues Set importieren" })).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
});
