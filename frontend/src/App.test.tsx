import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import App from "./App";

test("zeigt die Startseite der LEGO-Inventur", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "LEGO Inventur" })).toBeInTheDocument();
  expect(screen.getByText("Die Anwendung wird vorbereitet.")).toBeInTheDocument();
});
