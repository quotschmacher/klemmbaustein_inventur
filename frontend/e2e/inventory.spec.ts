import { expect, test } from "@playwright/test";

test("importiert ein synthetisches Inventar und zeigt die Zähloberfläche", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "LEGO Inventur" })).toBeVisible();

  await page.getByLabel("CSV-Inventar").setInputFiles("public/synthetic_inventory.csv");
  await page.getByRole("button", { name: "Inventar importieren" }).click();

  await expect(page.getByRole("heading", { name: "Gesamtübersicht" })).toBeVisible();
  await expect(page.getByText("Noch offene Zählbereiche")).toBeVisible();

  await page.getByRole("button", { name: "Zählen" }).click();
  await expect(page.getByRole("heading", { name: "Bereich auswählen" })).toBeVisible();
  await expect(page.getByText("Brick 2 x 4").first()).toBeVisible();
});
